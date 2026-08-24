"""Visit preparation agent using Ollama, Claude, or a custom provider to generate personalized questions.

This module implements DEC-006 (PII Anonymization) and DEC-008 (Intelligent Context Selection):
- All data is anonymized before sending to the LLM
- Relevant past visit context is intelligently selected
- Supports local Ollama (default), Claude API, and any custom OpenAI-compatible provider (DEC-016)
- Logs only anonymized content to ConversationLog
"""

import json
from typing import Any, Optional

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.agents.base import BaseAgent
from src.agents.llm_backend import (
    _CHARS_PER_TOKEN_ESTIMATE,
    _RESERVED_OUTPUT_TOKENS_ESTIMATE,
    ToolCallParsingError,
    get_llm_backend,
)
from src.agents.ollama_client import get_ollama_client
from src.agents.output_guardrails import apply_output_guardrails
from src.agents.tools import UnknownToolError, VisitPrepTools, get_tools_for_provider
from src.config import get_settings
from src.data.models import Appointment, FollowUp, LabOrder, Referral, Vitals
from src.services import settings_service
from src.utils.anonymization import (
    Anonymizer,
    AnonymizedAppointment,
    AnonymizedProfile,
    RedactionEvent,
    scrub_leaked_tokens,
    token_scope,
)
from src.utils.context_selection import ContextSelectionResult, ContextSelector


class AgenticLoopNotConvergedError(RuntimeError):
    """The agentic loop ran out of turns without producing a final answer.

    Subclasses RuntimeError so the existing `except (..., RuntimeError)` in
    `prepare_visit` keeps catching it, but lets non-convergence (an expected,
    benign outcome of the bounded loop — DEC-009/DEC-013) be told apart from a
    RuntimeError raised by the backend itself, which is a real defect. Issue #30
    exists because those two were indistinguishable.
    """


# Why a given prepare_visit() run did NOT come from the agentic loop. Stored on
# the ConversationLog row (see DEC-026) so a backend degrading at tool use is
# visible instead of silently downgrading every call to single-shot.
FALLBACK_TOOL_USE_DISABLED = "tool_use_disabled"   # agent_tool_use_enabled is off — not a failure
FALLBACK_NON_CONVERGENCE = "non_convergence"       # loop hit agent_max_turns; expected, benign
FALLBACK_PARSE_ERROR = "parse_error"               # backend emitted a malformed tool call
FALLBACK_UNKNOWN_TOOL = "unknown_tool"             # model called a tool that doesn't exist
FALLBACK_LOOP_ERROR = "loop_error"                 # anything else the loop raised — a real bug
FALLBACK_BACKEND_UNAVAILABLE = "backend_unavailable"  # both paths failed; placeholder returned

# Not a FALLBACK_* reason (this doesn't replace the agentic-vs-single-shot
# path, it's an extra repair step that can follow either one) — recorded
# separately on the repair call's own ConversationLog row so a JSON-repair
# retry is visible in the fallback-rate diagnostics rather than looking like
# an ordinary single-shot call.
JSON_REPAIR_RETRY = "json_repair_retry"


# Running tool-result content budget for the agentic loop (issue found via
# eval/run.py --trials against llama3.2:latest: a batch of 7-9 tool calls in
# one case's loop — several near-duplicate lookup_past_visits calls with
# slightly different keyword/specialty args — filled enough of ollama_num_ctx
# that the final answer got cut off mid-JSON; agent_max_turns had no effect,
# since the model was converging well within the turn cap already, and a
# flat per-turn call-count cap was rejected because it throttles genuinely
# distinct, necessary lookups (e.g. two different medications' details in
# one turn) exactly as hard as it throttles redundant ones.
#
# Instead this tracks actual tool-result content size against the real
# remaining context budget (ollama_num_ctx minus what the base messages
# already use minus a reserve for the response itself — the same reserve
# llm_backend._RESERVED_OUTPUT_TOKENS_ESTIMATE warns on), so any number of
# small, distinct calls are allowed through as long as they fit, and only
# calls that would actually blow the budget get held back. Exact-duplicate
# calls (same name + args) never re-execute and never replay their full
# result text into the conversation a second time — a short placeholder
# costs the budget almost nothing, whereas re-appending the same visit notes
# verbatim would burn real context for no new information.
_DUPLICATE_CALL_PLACEHOLDER = "(Same tool call as earlier in this conversation — see that result above.)"
_BUDGET_EXCEEDED_PLACEHOLDER = (
    "[Tool result budget exceeded for this response — use the results already "
    "returned above to finish your answer rather than requesting more.]"
)

# JSON Schema for the final {"questions": ..., "context_summary": ...}
# response both system prompts already ask for in prose. Passed as
# response_schema to constrain decoding (Ollama's `format` — see
# llm_backend.py) on the two calls that produce this shape without also
# requesting tools: the single-shot fallback (_call_backend) and the
# JSON-repair retry (_repair_response_via_model). Deliberately not applied
# to the agentic loop's tool-enabled calls — see LLMBackend.call's docstring.
# A loose schema on purpose: it only constrains the shape (an object of
# string arrays, plus a string summary), not category names, question count,
# or content — those stay governed by the prompt text and eval scorers, not
# by what would otherwise be a second, harder-to-change source of truth.
RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "questions": {
            "type": "object",
            "additionalProperties": {"type": "array", "items": {"type": "string"}},
        },
        "context_summary": {"type": "string"},
    },
    "required": ["questions", "context_summary"],
}


def _render_gathered_tool_results(tool_calls: list[dict[str, Any]]) -> str:
    """Render already-executed tool calls as plain text for the single-shot
    fallback path (see _prepare_visit_in_scope) — a non-convergent or parse-
    failing agentic loop still made real, already-anonymized tool calls
    before it failed, and discarding them meant the fallback answered with
    strictly less information than the agent already had.

    Concretely found via eval/run.py against granite4:3b's cold_start case:
    the loop called get_medication_details four times, every time correctly
    confirming "No matching medications found" — then non-convergence threw
    all of that away, and the single-shot fallback (told to reference actual
    medication names, given none) invented a literal unfilled template
    placeholder — "I currently take [list any known medications here]" —
    instead of a confirmed, definitive absence. Passing the real results
    forward gives the fallback the same grounding the agent already earned.
    """
    lines = []
    for call in tool_calls:
        if call.get("result") in (_DUPLICATE_CALL_PLACEHOLDER, _BUDGET_EXCEEDED_PLACEHOLDER):
            continue  # adds nothing — the real result is already included above
        lines.append(f"[{call['name']}]")
        lines.append(str(call.get("result", "")))
        lines.append("")
    return "\n".join(lines).strip()


# ICD-10 prefix → specialty mapping for tagging conditions
ICD10_SPECIALTY_MAP: dict[str, list[str]] = {
    "E00-E07": ["Endocrinology"],       # Thyroid disorders
    "E08-E13": ["Endocrinology"],       # Diabetes
    "E20-E35": ["Endocrinology"],       # Other endocrine disorders
    "E28": ["Endocrinology", "Gynecology"],  # Ovarian dysfunction (PCOS)
    "L00-L99": ["Dermatology"],         # Skin disorders
    "N80": ["Gynecology"],              # Endometriosis, adenomyosis
    "N81-N98": ["Gynecology"],          # Female genital tract
    "I00-I99": ["Cardiology"],          # Circulatory system
    "J00-J99": ["Pulmonology"],         # Respiratory system
    "K00-K95": ["Gastroenterology"],    # Digestive system
    "M00-M99": ["Rheumatology"],        # Musculoskeletal
    "G00-G99": ["Neurology"],           # Nervous system
    "C00-D49": ["Oncology"],            # Neoplasms
    "N00-N29": ["Nephrology"],          # Kidney
    "N30-N39": ["Urology"],             # Urinary
}


def _classify_agentic_failure(error: Exception) -> str:
    """Map an exception that aborted the agentic loop to a FALLBACK_* reason.

    The point of the distinction (issue #30, DEC-013): non-convergence is the
    bounded loop working as designed, while a parse error, an unknown tool, or
    an unexpected RuntimeError from the backend all mean something is actually
    broken. Collapsing them into one "fell back" counter would hide a degrading
    backend behind a number that looks normal.
    """
    if isinstance(error, AgenticLoopNotConvergedError):
        return FALLBACK_NON_CONVERGENCE
    if isinstance(error, ToolCallParsingError):
        return FALLBACK_PARSE_ERROR
    if isinstance(error, UnknownToolError):
        return FALLBACK_UNKNOWN_TOOL
    return FALLBACK_LOOP_ERROR


def _icd10_to_specialties(icd_10: Optional[str]) -> list[str]:
    """Map an ICD-10 code to likely managing specialties.

    Uses prefix matching against ICD10_SPECIALTY_MAP. Returns empty list
    if code is None or no match found.
    """
    if not icd_10:
        return []
    code = icd_10.strip().upper()

    # Try exact prefix matches first (most specific, e.g. "E28" before "E20-E35")
    for prefix_range, specialties in ICD10_SPECIALTY_MAP.items():
        if "-" not in prefix_range:
            # Exact prefix like "E28"
            if code.startswith(prefix_range):
                return specialties

    # Then try range matches
    for prefix_range, specialties in ICD10_SPECIALTY_MAP.items():
        if "-" in prefix_range:
            start, end = prefix_range.split("-")
            # Extract letter + number prefix
            code_prefix = code[:len(start)]
            if start <= code_prefix <= end:
                return specialties

    return []


# Canonical specialty name list — module-level so both clinic-name inference
# below and output_guardrails.py's referral-presupposition check (DEC-042)
# can share one source of truth instead of drifting apart.
SPECIALTY_KEYWORDS: dict[str, str] = {
    "endocrinology": "Endocrinology",
    "dermatology": "Dermatology",
    "cardiology": "Cardiology",
    "gynecology": "Gynecology",
    "ob-gyn": "Obstetrics and Gynecology",
    "obstetrics": "Obstetrics and Gynecology",
    "neurology": "Neurology",
    "orthopedic": "Orthopedics",
    "oncology": "Oncology",
    "gastroenterology": "Gastroenterology",
    "pulmonology": "Pulmonology",
    "rheumatology": "Rheumatology",
    "nephrology": "Nephrology",
    "urology": "Urology",
    "psychiatry": "Psychiatry",
    "ophthalmology": "Ophthalmology",
    "pain management": "Pain Management",
    "physical therapy": "Physical Therapy",
    "family medicine": "Family Medicine",
    "internal medicine": "Internal Medicine",
    "primary care": "Primary Care",
}


def _infer_specialty_from_clinic(clinic: Optional[str]) -> Optional[str]:
    """Infer doctor specialty from clinic name as a fallback.

    E.g. "Sutter Endocrinology - San Francisco" → "Endocrinology"
    """
    if not clinic:
        return None
    clinic_lower = clinic.lower()
    for keyword, specialty in SPECIALTY_KEYWORDS.items():
        if keyword in clinic_lower:
            return specialty
    return None


def _scrub_generated_output(result: dict[str, Any]) -> dict[str, Any]:
    """Run the token leakage guard over everything a user will read (issue #17).

    Scoped tokens (`PERSON_1`) are more useful to the model than an
    undifferentiated `[REDACTED]`, but they are input-side machinery: a model
    that echoes one into a question would show the patient something that looks
    broken. This rewrites any surviving token back to `[REDACTED]` — the marker
    the app already displays for redacted content — so the worst case is
    exactly the pre-#17 behaviour.

    Applies to the fallback response too: cheap, and it means no return path
    out of `prepare_visit` is unguarded by construction rather than by audit.
    """
    scrubbed = dict(result)
    questions = scrubbed.get("questions")
    if isinstance(questions, dict):
        scrubbed["questions"] = {
            category: [scrub_leaked_tokens(q) for q in items]
            if isinstance(items, list) else items
            for category, items in questions.items()
        }
    if isinstance(scrubbed.get("context_summary"), str):
        scrubbed["context_summary"] = scrub_leaked_tokens(scrubbed["context_summary"])
    return scrubbed


class VisitPrepAgent(BaseAgent):
    """Agent for generating AI-powered doctor visit preparation.

    Uses anonymization and intelligent context selection per DEC-006 and DEC-008.
    """

    # See docs/notes/PROMPT_CHANGELOG.md for version history/rationale —
    # bump the version and add an entry there whenever either prompt below
    # changes, per the project-wide prompt-versioning convention.
    SYSTEM_PROMPT_TEMPLATE_VERSION = "v8-2026-08-24"
    SYSTEM_PROMPT_TEMPLATE = """You are a healthcare assistant preparing a patient for a visit with their {specialty}.

Your task: generate 8-15 focused, actionable questions the patient should ask THIS doctor based on the patient data provided. This count is a hard requirement, not a suggestion, at BOTH ends — if you find yourself with fewer than 8 well-grounded questions, dig deeper into the conditions, medications, and lab data already provided for more specific angles (e.g. dosage timing, monitoring frequency, symptom tracking) rather than stopping early; if you find yourself with more than 15, cut down to the 15 most clinically useful ones rather than including every question you can think of — the goal is a focused, prioritized list a patient can actually use in a visit, not an exhaustive one.

If tools are available to you, use them before finalizing your answer whenever they would give you a more specific or more grounded question than the patient data already provided lets you write — e.g. call get_medication_details before asking anything about a specific medication's dosage, timing, or interactions rather than asking generically or guessing; call lookup_past_visits before asserting what happened at, or is due for, an earlier or upcoming visit that isn't already shown. Do not skip an available, relevant tool just because you can already produce *some* answer without it — a specific, tool-grounded question is what this task requires, not merely a plausible-sounding one.

IMPORTANT RULES:
- Only include questions relevant to this doctor's specialty ({specialty})
- Do NOT suggest discussing medications prescribed by unrelated specialists (e.g. don't ask an endocrinologist about topical dermatology creams)
- DO identify cross-condition interactions that ARE relevant to this specialty (e.g. how PCOS and Hashimoto's interact hormonally IS relevant for an endocrinologist, even if one was diagnosed by a gynecologist)
- Use the lab orders and vitals data to generate specific questions (e.g. "Your last TSH was ordered on [date] — ask about results and whether dosage adjustment is needed")
- Reference pending follow-ups if relevant to this specialty
- Note significant changes in vitals (weight, BMI, blood pressure) and ask about them if relevant
- Do NOT ask about vitals, lab results, conditions, or medications that are not explicitly listed in the patient data below — if a category of data (e.g. vitals) isn't provided, don't reference it or assume it exists
- A category needs real patient data behind it to be included: "Condition Management" needs actual conditions listed, "Medication Review" needs actual medications listed, "Lab Results & Monitoring" needs actual lab orders listed, "Follow-up Planning" needs an actual pending follow-up or referral listed if you're asking about a specific one (a generic "when should I schedule a follow-up" is fine either way). If a category has no real data behind it, omit it entirely rather than asking generically. "Lifestyle & Prevention" is the exception — general guidance tied to a real listed condition or specialty is fine even without additional data, as long as you don't assert a specific fact (a test result, a medication name, an appointment) that wasn't provided.
- If a past visit's "Planned to discuss" notes mention something its "Notes" don't show as addressed, that's a real carryover — surface it as a question. Don't assume something wasn't discussed just because it isn't repeated in the visit notes; only flag it if the notes are present and silent on it, not when notes are missing or sparse in general.
- Never include a category key with an empty question list — if a category has nothing to ask, leave the key out of the JSON entirely rather than including it as an empty array. Prioritize categories where you have real patient data (actual conditions, actual medications) over categories with none.
- Omitting empty categories does NOT lower the question-count requirement below. If dropping empty categories leaves you short of 8, go deeper within the categories that DO have real data — e.g. more angles on each condition or medication (dosage timing, monitoring frequency, symptom tracking, interactions) — rather than accepting a shorter list.

Respond with a JSON object in this exact format:
{{
    "questions": {{
        "Category Name": [
            "Question 1 text",
            "Question 2 text"
        ]
    }},
    "context_summary": "A brief 2-3 sentence summary of the patient's key health context relevant to this visit."
}}

Use these categories (omit any that have no relevant questions — do not include an empty list for a category):
- "Condition Management" — questions about conditions this specialist manages or that interact with their care
- "Medication Review" — only medications this specialist manages or that could interact with their treatments
- "Lab Results & Monitoring" — questions about recent or pending lab work relevant to this specialty
- "Lifestyle & Prevention" — actionable lifestyle questions specific to their conditions and this specialty
- "Follow-up Planning" — what to schedule next, referrals to discuss, and any carryover concern from a past visit's planned-but-unconfirmed-as-addressed topics

Before finalizing your response, count your questions. You must have between 8 and 15 total across all categories combined — if you're short, add more within your existing (non-empty) categories rather than reintroducing an empty one; if you're over 15, cut down to the 15 most clinically useful ones, not just the first 15 you generated. Be specific — reference actual condition names, medication names, and lab test names from the patient data provided."""

    # Fallback when no specialty is known
    SYSTEM_PROMPT_GENERIC_VERSION = "v8-2026-08-24"
    SYSTEM_PROMPT_GENERIC = """You are a healthcare assistant preparing a patient for an upcoming doctor visit.

Your task: generate 8-15 focused, actionable questions the patient should ask their doctor based on the patient data provided. This count is a hard requirement, not a suggestion, at BOTH ends — if you find yourself with fewer than 8 well-grounded questions, dig deeper into the conditions, medications, and lab data already provided for more specific angles (e.g. dosage timing, monitoring frequency, symptom tracking) rather than stopping early; if you find yourself with more than 15, cut down to the 15 most clinically useful ones rather than including every question you can think of — the goal is a focused, prioritized list a patient can actually use in a visit, not an exhaustive one.

If tools are available to you, use them before finalizing your answer whenever they would give you a more specific or more grounded question than the patient data already provided lets you write — e.g. call get_medication_details before asking anything about a specific medication's dosage, timing, or interactions rather than asking generically or guessing; call lookup_past_visits before asserting what happened at, or is due for, an earlier or upcoming visit that isn't already shown. Do not skip an available, relevant tool just because you can already produce *some* answer without it — a specific, tool-grounded question is what this task requires, not merely a plausible-sounding one.

IMPORTANT RULES:
- Do NOT ask about vitals, lab results, conditions, or medications that are not explicitly listed in the patient data below — if a category of data (e.g. vitals) isn't provided, don't reference it or assume it exists
- A category needs real patient data behind it to be included: "Condition Management" needs actual conditions listed, "Medication Review" needs actual medications listed, "Lab Results & Monitoring" needs actual lab orders listed, "Follow-up Planning" needs an actual pending follow-up or referral listed if you're asking about a specific one (a generic "when should I schedule a follow-up" is fine either way). If a category has no real data behind it, omit it entirely rather than asking generically. "Lifestyle & Prevention" is the exception — general guidance tied to a real listed condition is fine even without additional data, as long as you don't assert a specific fact (a test result, a medication name, an appointment) that wasn't provided.
- If a past visit's "Planned to discuss" notes mention something its "Notes" don't show as addressed, that's a real carryover — surface it as a question. Don't assume something wasn't discussed just because it isn't repeated in the visit notes; only flag it if the notes are present and silent on it, not when notes are missing or sparse in general.
- Never include a category key with an empty question list — if a category has nothing to ask, leave the key out of the JSON entirely rather than including it as an empty array. Prioritize categories where you have real patient data (actual conditions, actual medications) over categories with none.
- Omitting empty categories does NOT lower the question-count requirement below. If dropping empty categories leaves you short of 8, go deeper within the categories that DO have real data — e.g. more angles on each condition or medication (dosage timing, monitoring frequency, symptom tracking, interactions) — rather than accepting a shorter list.

Respond with a JSON object in this exact format:
{{
    "questions": {{
        "Category Name": [
            "Question 1 text",
            "Question 2 text"
        ]
    }},
    "context_summary": "A brief 2-3 sentence summary of the patient's key health context relevant to this visit."
}}

Use these categories (omit any that have no relevant questions — do not include an empty list for a category):
- "Condition Management" — questions about their active conditions
- "Medication Review" — questions about current medications
- "Lab Results & Monitoring" — questions about recent or pending lab work
- "Lifestyle & Prevention" — actionable lifestyle questions
- "Follow-up Planning" — what to schedule next, and any carryover concern from a past visit's planned-but-unconfirmed-as-addressed topics

Before finalizing your response, count your questions. You must have between 8 and 15 total across all categories combined — if you're short, add more within your existing (non-empty) categories rather than reintroducing an empty one; if you're over 15, cut down to the 15 most clinically useful ones, not just the first 15 you generated. Be specific — reference actual condition names, medication names, and lab test names from the patient data provided."""

    def __init__(self, db: AsyncSession):
        """Initialize the visit prep agent."""
        super().__init__(db)
        self.settings = get_settings()
        self.anonymizer = Anonymizer(use_ner=self.settings.use_ner_anonymization)
        self.context_selector = ContextSelector(
            anonymizer=self.anonymizer,
            stage2_threshold=self.settings.context_stage2_threshold,
            relevance_cutoff=self.settings.context_relevance_cutoff,
            stage2_max_candidates=self.settings.context_stage2_max_candidates,
        )
        # Diagnostics from the most recent prepare_visit() call — see that
        # method's docstring. None/empty until a run has actually happened.
        self.last_context_selection: Optional[ContextSelectionResult] = None
        self.last_tool_calls: list[dict[str, Any]] = []
        # Structured patient data + guardrail events from the most recent
        # call, set in _prepare_visit_in_scope and consumed by prepare_visit
        # to apply output_guardrails.py centrally at the one return point
        # every path (agentic success, fallback) already converges through —
        # see prepare_visit's docstring. Empty until a run has happened.
        self.last_clinical_data: dict[str, Any] = {}
        self.last_target_specialty: Optional[str] = None
        self.last_medication_count: int = 0
        self.last_guardrail_events: list[dict[str, Any]] = []
        # Redaction events (issue #16) aggregated across this whole
        # prepare_visit() call — profile/appointment anonymization, Stage 4
        # context selection, and any tool-result anonymization from the
        # agentic loop. Reset at the top of each prepare_visit() run.
        self.last_redaction_events: list[RedactionEvent] = []

    async def _get_past_appointments(self, profile_id: str, current_appointment_id: str) -> list[Appointment]:
        """Get past completed appointments for context."""
        result = await self.db.execute(
            select(Appointment)
            .options(selectinload(Appointment.doctor))
            .where(
                Appointment.profile_id == profile_id,
                Appointment.id != current_appointment_id,
                Appointment.status == "completed",
            )
            .order_by(Appointment.scheduled_date.desc())
        )
        return list(result.scalars().all())

    async def _get_clinical_data(self, profile_id: str) -> dict[str, Any]:
        """Load lab orders, vitals, follow-ups, and referrals for the profile."""
        lab_result = await self.db.execute(
            select(LabOrder)
            .where(LabOrder.profile_id == profile_id)
            .order_by(LabOrder.ordered_date.desc())
        )
        labs = list(lab_result.scalars().all())

        vitals_result = await self.db.execute(
            select(Vitals)
            .where(Vitals.profile_id == profile_id)
            .order_by(Vitals.measured_date.desc())
        )
        vitals = list(vitals_result.scalars().all())

        followup_result = await self.db.execute(
            select(FollowUp)
            .where(FollowUp.profile_id == profile_id)
        )
        follow_ups = list(followup_result.scalars().all())

        referral_result = await self.db.execute(
            select(Referral)
            .where(Referral.profile_id == profile_id)
        )
        referrals = list(referral_result.scalars().all())

        return {
            "lab_orders": labs,
            "vitals": vitals,
            "follow_ups": follow_ups,
            "referrals": referrals,
        }

    def _get_system_prompt(self, specialty: Optional[str]) -> str:
        """Get the system prompt, specialized for the doctor's specialty."""
        if specialty:
            return self.SYSTEM_PROMPT_TEMPLATE.format(specialty=specialty)
        return self.SYSTEM_PROMPT_GENERIC

    def _get_system_prompt_version(self, specialty: Optional[str]) -> str:
        """Version tag for whichever prompt _get_system_prompt returns —
        logged alongside the conversation so a real ConversationLog row is
        traceable to which prompt version produced it. See
        docs/notes/PROMPT_CHANGELOG.md for the project-wide convention.
        """
        return self.SYSTEM_PROMPT_TEMPLATE_VERSION if specialty else self.SYSTEM_PROMPT_GENERIC_VERSION

    async def prepare_visit(
        self,
        appointment: Appointment,
        additional_concerns: Optional[str] = None,
        temperature: float = 0.7,
    ) -> dict[str, Any]:
        """Generate visit preparation questions and context.

        Wraps the whole run in one `token_scope()` (issue #17), which is what
        makes free-text redaction relational: every `anonymize_text()` call
        below — profile, doctor, appointment, additional concerns, Stage 4
        context selection, agentic-loop tool results — resolves the same
        underlying value to the same `PERSON_1`/`MRN_1` token, so the model can
        tell two distinct redacted people apart instead of seeing one
        undifferentiated `[REDACTED]`. The map lives and dies with this call;
        nothing about one patient survives into the next request.

        The generated output is then passed through `scrub_leaked_tokens`
        before it is returned, so a model that echoes a token verbatim can't
        put an opaque `PERSON_1` in front of the user. That guard is not
        re-hydration — see `scrub_leaked_tokens` and #17's open question.
        """
        with token_scope():
            result = await self._prepare_visit_in_scope(
                appointment,
                additional_concerns=additional_concerns,
                temperature=temperature,
            )
        result = self._apply_output_guardrails(result)
        return _scrub_generated_output(result)

    def _apply_output_guardrails(self, result: dict[str, Any]) -> dict[str, Any]:
        """Strips questions presupposing a test/lab or referral relationship
        not actually on file (DEC-042) — see output_guardrails.py. Applied
        here, prepare_visit's one convergence point for every return path
        (agentic success, single-shot fallback, generic fallback), using the
        structured data _prepare_visit_in_scope already loaded and stashed
        on self.last_clinical_data/self.last_target_specialty.
        """
        questions = result.get("questions")
        if not isinstance(questions, dict):
            return result

        known_lab_names = {lab.test_name.lower() for lab in self.last_clinical_data.get("lab_orders", [])}
        referred_specialties = {r.specialty.lower() for r in self.last_clinical_data.get("referrals", [])}
        known_specialty_names = set(SPECIALTY_KEYWORDS.values())
        if self.last_target_specialty:
            known_specialty_names.add(self.last_target_specialty)

        filtered_questions, events = apply_output_guardrails(
            questions, known_lab_names, known_specialty_names, referred_specialties, self.last_medication_count
        )
        self.last_guardrail_events = events
        if events:
            logger.warning(f"Output guardrails stripped {len(events)} question(s): {events}")

        return {**result, "questions": filtered_questions}

    async def _prepare_visit_in_scope(
        self,
        appointment: Appointment,
        additional_concerns: Optional[str] = None,
        temperature: float = 0.7,
    ) -> dict[str, Any]:
        """The visit-prep pipeline itself. Always called inside a token scope.

        Uses anonymization and context selection per DEC-006 and DEC-008.

        temperature defaults to production's normal 0.7; the eval harness
        (issue #29) passes 0.0 so repeated runs of the same fixture are
        reproducible enough to diff against a prior run.

        After this returns, `self.last_context_selection` (the Phase 1
        ContextSelectionResult) and `self.last_tool_calls` (the Phase 2
        agentic-loop tool-call log, empty if the single-shot fallback ran)
        are available for callers that need run diagnostics — the eval
        harness uses both to check for redundant retrieval between the two
        phases, without duplicating this method's pipeline logic.
        """
        # Step 0: Refresh settings with any DB-persisted overrides (DEC-016) —
        # the LLM provider can be switched from the Settings UI at runtime,
        # so pull the effective settings fresh for each visit prep rather
        # than relying on the env-only settings captured in __init__.
        self.settings = await settings_service.get_effective_settings(self.db)

        # Step 1: Get past appointments for context
        past_appointments = await self._get_past_appointments(
            appointment.profile_id,
            appointment.id
        )

        # Step 2: Select relevant context (4-stage pipeline). Stage 2's local
        # relevance scoring needs a live Ollama client — this is independent
        # of settings.llm_provider (Stage 2 is always local, per DEC-008,
        # even when the agentic loop itself runs on Claude or a custom
        # provider). get_ollama_client() does its own availability check and
        # returns None if Ollama isn't reachable, which select_context()
        # already treats as "skip Stage 2" — fetched fresh each call since
        # availability can change between requests.
        self.context_selector.ollama_client = await get_ollama_client()

        context_result = await self.context_selector.select_context(
            target_appointment=appointment,
            all_past_appointments=past_appointments,
            max_tokens=self.settings.context_max_tokens,
        )
        self.last_context_selection = context_result
        self.last_tool_calls: list[dict[str, Any]] = []
        # Reset per-request redaction aggregation (issue #16); seeded with
        # Stage 4's context-selection events, extended below as later steps
        # anonymize the current profile/appointment/concerns and any
        # agentic-loop tool results.
        self.last_redaction_events = list(context_result.redaction_events)

        logger.info(
            f"Context selection: {context_result.total_visits_considered} total, "
            f"{context_result.visits_after_stage1} after rules, "
            f"selected {len(context_result.selected_visits)} visits "
            f"(dropped {context_result.visits_dropped_stage2_cap} at Stage 2 cap, "
            f"{context_result.visits_dropped_stage3_budget} at Stage 3 budget)"
        )

        # Step 3: Load clinical data (labs, vitals, follow-ups, referrals)
        clinical_data = await self._get_clinical_data(appointment.profile_id)
        self.last_clinical_data = clinical_data

        # Step 4: Anonymize current profile and appointment
        anonymized_profile, profile_events = self.anonymizer.anonymize_profile(appointment.profile)
        anonymized_appointment, appointment_events = self.anonymizer.anonymize_appointment(appointment)
        self.last_redaction_events.extend(profile_events)
        self.last_redaction_events.extend(appointment_events)

        # Step 5: Resolve medication → doctor specialty for tagging
        med_specialty_map = self._build_med_specialty_map(appointment.profile)
        self.last_medication_count = len(list(getattr(appointment.profile, "medications", []) or []))

        # Step 6: Build context message
        target_specialty = None
        if appointment.doctor:
            target_specialty = appointment.doctor.specialty or _infer_specialty_from_clinic(appointment.doctor.clinic)
        self.last_target_specialty = target_specialty
        anonymized_concerns, concerns_events = self.anonymizer.anonymize_text(
            additional_concerns,
            profile_id=appointment.profile_id,
            field_name="additional_concerns",
        )
        self.last_redaction_events.extend(concerns_events)
        context = self._build_anonymized_context(
            profile=anonymized_profile,
            appointment=anonymized_appointment,
            past_visits=context_result.selected_visits,
            clinical_data=clinical_data,
            med_specialty_map=med_specialty_map,
            conditions_raw=list(getattr(appointment.profile, 'conditions', [])),
            additional_concerns=anonymized_concerns,
        )

        system_prompt = self._get_system_prompt(target_specialty)
        system_prompt_version = self._get_system_prompt_version(target_specialty)
        messages = [{"role": "user", "content": context}]

        # Why this run didn't use the agentic loop, if it didn't. None means it
        # did (or hasn't been decided yet) — see the FALLBACK_* constants.
        fallback_reason: Optional[str] = None

        try:
            # Step 7: Call LLM — try the agentic tool-use loop first (DEC-009),
            # falling back to single-shot generation if it's disabled, the
            # backend can't do reliable tool use, or it doesn't converge.
            response = None
            if self.settings.agent_tool_use_enabled:
                try:
                    response = await self._run_agentic_loop(
                        appointment.profile_id, messages, system_prompt, temperature=temperature,
                        prompt_version=system_prompt_version,
                        exclude_appointment_ids=context_result.selected_visit_ids,
                        target_doctor_id=appointment.doctor_id,
                        current_appointment_id=appointment.id,
                    )
                except (ToolCallParsingError, UnknownToolError, RuntimeError) as e:
                    fallback_reason = _classify_agentic_failure(e)
                    logger.warning(
                        f"Agentic tool-use loop failed ({fallback_reason}), "
                        f"falling back to single-shot: {e}"
                    )
                    response = None
            else:
                fallback_reason = FALLBACK_TOOL_USE_DISABLED

            if response is None:
                # If the agentic loop made real tool calls before failing
                # (non-convergence, a parse error mid-loop, an unknown-tool
                # call), don't throw that work away — the single-shot
                # fallback would otherwise answer with strictly less
                # information than the agent already had, and can
                # hallucinate a placeholder for something already
                # definitively answered. See _render_gathered_tool_results.
                fallback_messages = messages
                gathered = _render_gathered_tool_results(self.last_tool_calls)
                if gathered:
                    fallback_messages = messages + [{
                        "role": "user",
                        "content": (
                            "Additional information already retrieved via tool calls before "
                            "this fallback — these results are real and already confirmed. "
                            "Use them, and do not invent placeholder content for anything "
                            "already answered below, including a confirmed absence (e.g. "
                            "\"No matching medications found\" means there are none — omit "
                            "that category rather than guessing at a value):\n\n" + gathered
                        ),
                    }]
                response = await self._call_backend(
                    fallback_messages, system_prompt, temperature=temperature,
                    prompt_version=system_prompt_version,
                    fallback_reason=fallback_reason,
                )

            # Step 8: Parse JSON response — _parse_json_response already tries
            # a code-level repair for a truncated-looking response (unclosed
            # brackets/quotes). If that's still not enough (content itself is
            # missing, not just closing punctuation), ask the model to finish
            # its own output once before giving up — see
            # _repair_response_via_model's docstring for why this is scoped
            # to exactly one extra call, not a retry loop.
            parsed = self._parse_json_response(response)
            if not (parsed and "questions" in parsed):
                repaired_response = await self._repair_response_via_model(
                    response, system_prompt, prompt_version=system_prompt_version,
                    temperature=temperature,
                )
                if repaired_response is not None:
                    response = repaired_response
                    parsed = self._parse_json_response(response)
                    if parsed and "questions" in parsed:
                        # warning, not info: a repair-worthy failure is
                        # diagnostically interesting even when it self-
                        # corrects — the original response still didn't
                        # parse, this just means the user never saw it.
                        logger.warning("JSON repair-via-model attempt succeeded")

            if parsed and "questions" in parsed:
                return {
                    "questions": parsed.get("questions", {}),
                    "context_summary": parsed.get("context_summary", ""),
                    "used_fallback": False,
                    "agentic_path": fallback_reason is None,
                    "fallback_reason": fallback_reason,
                }
            else:
                logger.warning("Could not parse JSON from LLM response")
                return {
                    "questions": {"General Questions": [response]},
                    "context_summary": "AI generated visit preparation (raw response).",
                    "used_fallback": False,
                    "agentic_path": fallback_reason is None,
                    "fallback_reason": fallback_reason,
                }

        except Exception as e:
            logger.error(f"Visit prep generation failed: {e}")
            # Nothing was logged on this path — the backend call raised before
            # _log_conversation ran — so record the hard failure explicitly.
            # Without this, a wholly unreachable backend would be *invisible*
            # to the fallback-rate diagnostics, which is the exact blind spot
            # issue #30 is about.
            await self._log_hard_failure(
                system_prompt_version=system_prompt_version,
                prior_agentic_failure=fallback_reason,
                error=e,
            )
            return self._get_fallback_response(prior_agentic_failure=fallback_reason)

    async def _run_agentic_loop(
        self,
        profile_id: str,
        messages: list[dict],
        system: str,
        temperature: float = 0.7,
        prompt_version: Optional[str] = None,
        exclude_appointment_ids: Optional[list[str]] = None,
        target_doctor_id: Optional[str] = None,
        current_appointment_id: Optional[str] = None,
    ) -> str:
        """Run the bounded agentic tool-use loop (DEC-009, DEC-013).

        Raises ToolCallParsingError/RuntimeError if the loop can't converge
        within settings.agent_max_turns — callers should fall back to
        single-shot generation on those exceptions.

        exclude_appointment_ids: visits already selected into the base
        context by context_selection.py's Stage 1-4 pipeline — passed
        through to VisitPrepTools so lookup_past_visits can't redundantly
        re-surface them (DEC-024).

        target_doctor_id / current_appointment_id: the provider being seen and
        the appointment being prepped — used to anchor lookup_past_visits'
        default date window to "since the patient last saw this provider"
        (issue #21). Both optional; without them the lookup stays unbounded.
        """
        backend = get_llm_backend(self.settings)
        tools = get_tools_for_provider(self.settings.llm_provider)
        tool_executor = VisitPrepTools(
            self.db, self.anonymizer, profile_id,
            exclude_appointment_ids=exclude_appointment_ids,
            target_doctor_id=target_doctor_id,
            current_appointment_id=current_appointment_id,
        )

        conversation = list(messages)
        tool_call_log: list[dict[str, Any]] = getattr(self, "last_tool_calls", [])
        # Cache of (name, canonical-args-json) -> result, shared across every
        # turn of this loop instance, not just within one turn — a call
        # repeated on turn 2 that was already answered on turn 1 is exactly
        # as wasteful as a repeat within the same turn.
        seen_calls: dict[tuple[str, str], str] = {}

        # Real remaining room for tool-result content: total context minus
        # what the base prompt (system + starting messages + tool schemas)
        # already costs, minus the same output reserve llm_backend warns on
        # — so this budget and that warning agree on what "enough room" means.
        base_chat_messages = [{"role": "system", "content": system}, *messages]
        base_chars = sum(len(json.dumps(m)) for m in base_chat_messages)
        base_chars += sum(len(json.dumps(t)) for t in tools) if tools else 0
        base_tokens = base_chars // _CHARS_PER_TOKEN_ESTIMATE
        tool_result_token_budget = max(
            0, self.settings.ollama_num_ctx - base_tokens - _RESERVED_OUTPUT_TOKENS_ESTIMATE
        )
        tool_result_chars_remaining = tool_result_token_budget * _CHARS_PER_TOKEN_ESTIMATE

        for turn in range(self.settings.agent_max_turns):
            result = await backend.call(conversation, system, tools=tools, temperature=temperature)

            if not result.tool_calls:
                self.last_redaction_events.extend(tool_executor.redaction_events)
                await self._log_conversation(
                    messages=messages,
                    response=result.text or "",
                    system=system,
                    input_tokens=result.input_tokens,
                    output_tokens=result.output_tokens,
                    model=self._model_name_for_provider(),
                    tool_calls=tool_call_log or None,
                    prompt_version=prompt_version,
                    run_diagnostics={"agentic_path": True, "fallback_reason": None},
                    redaction_events=self.last_redaction_events,
                )
                return result.text or ""

            conversation.append(backend.build_assistant_message(result))
            for tool_call in result.tool_calls:
                cache_key = (tool_call.name, json.dumps(tool_call.input, sort_keys=True, default=str))

                if cache_key in seen_calls:
                    # Exact repeat — never re-execute, and never replay the
                    # full result text again either; the model already has
                    # it in the conversation above.
                    tool_result = _DUPLICATE_CALL_PLACEHOLDER
                elif tool_result_chars_remaining <= 0:
                    tool_result = _BUDGET_EXCEEDED_PLACEHOLDER
                else:
                    tool_result = await tool_executor.execute(tool_call.name, tool_call.input)
                    seen_calls[cache_key] = tool_result
                    tool_result_chars_remaining -= len(tool_result)

                conversation.append(backend.build_tool_result_message(tool_call, tool_result))
                tool_call_log.append({
                    "name": tool_call.name,
                    "input": tool_call.input,
                    "result": tool_result,
                })

        # Even on non-convergence, any tool-result anonymization that did
        # happen is real and belongs in the per-request total (issue #16) —
        # the single-shot fallback that follows doesn't repeat these calls.
        self.last_redaction_events.extend(tool_executor.redaction_events)
        raise AgenticLoopNotConvergedError(
            f"Agentic loop did not converge within {self.settings.agent_max_turns} turns"
        )

    def _model_name_for_provider(self) -> str:
        """Model name to log against, for whichever provider is configured."""
        if self.settings.llm_provider == "ollama":
            return self.settings.ollama_model
        if self.settings.llm_provider == "custom":
            return self.settings.custom_llm_model or "custom"
        return self.settings.anthropic_model

    async def _call_backend(
        self,
        messages: list[dict],
        system: str,
        temperature: float = 0.7,
        prompt_version: Optional[str] = None,
        fallback_reason: Optional[str] = None,
    ) -> str:
        """Single-shot (non-agentic) generation via whichever backend is configured.

        fallback_reason: why the agentic loop didn't produce this response (a
        FALLBACK_* constant), recorded on the ConversationLog row. None means
        this was a direct single-shot call rather than a fallback.
        """
        backend = get_llm_backend(self.settings)
        result = await backend.call(
            messages, system, tools=None, temperature=temperature, response_schema=RESPONSE_SCHEMA,
        )
        response = result.text or ""

        await self._log_conversation(
            messages=messages,
            response=response,
            system=system,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            model=self._model_name_for_provider(),
            prompt_version=prompt_version,
            run_diagnostics={"agentic_path": False, "fallback_reason": fallback_reason},
            redaction_events=self.last_redaction_events,
        )

        return response

    async def _repair_response_via_model(
        self,
        malformed_response: str,
        system: str,
        prompt_version: Optional[str] = None,
        temperature: float = 0.7,
    ) -> Optional[str]:
        """One extra model call to finish/fix a response that didn't parse as
        JSON, even after _parse_json_response's own code-level repair attempt.

        Scoped to exactly one attempt, not a retry loop — the point (per the
        original item #4, "retry-with-repair before falling back") is a cheap
        second chance for a small model to notice and fix its own mistake,
        not an open-ended negotiation. If this attempt still doesn't parse,
        the caller falls through to the existing raw-response fallback bucket
        same as before this existed.

        Doesn't reuse the full conversation/tool history — the malformed
        response and a short, explicit instruction are the entire prompt, so
        this can't itself run into the same long-context degradation that
        plausibly caused the original truncation.

        Returns the repaired text, or None if the repair call itself failed
        (network/backend error) — that's a real failure, but not one worth
        raising past the caller, which already has a working fallback path.
        """
        repair_instruction = (
            "The following is your own previous response to a request for a JSON object "
            "with \"questions\" (grouped by category) and \"context_summary\" fields. It did "
            "not parse as valid JSON — likely cut off before the closing braces/brackets. "
            "Re-output the COMPLETE, valid JSON object only, with no other text before or "
            "after it. Keep all the same content; just make sure it is well-formed and "
            "fully closed.\n\n"
            f"Previous response:\n{malformed_response}"
        )
        try:
            backend = get_llm_backend(self.settings)
            result = await backend.call(
                [{"role": "user", "content": repair_instruction}], system,
                tools=None, temperature=temperature, response_schema=RESPONSE_SCHEMA,
            )
            response = result.text or ""
        except Exception as e:
            logger.warning(f"JSON repair-via-model attempt failed, falling back: {e}")
            return None

        await self._log_conversation(
            messages=[{"role": "user", "content": repair_instruction}],
            response=response,
            system=system,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            model=self._model_name_for_provider(),
            prompt_version=prompt_version,
            run_diagnostics={"agentic_path": False, "fallback_reason": JSON_REPAIR_RETRY},
            redaction_events=self.last_redaction_events,
        )
        return response

    async def _log_hard_failure(
        self,
        system_prompt_version: Optional[str] = None,
        prior_agentic_failure: Optional[str] = None,
        error: Optional[Exception] = None,
    ) -> None:
        """Record a run where neither the agentic loop nor single-shot produced anything.

        On this path no LLM response exists to log, so `_log_conversation`'s
        normal call sites never ran. The row written here carries no prompt or
        user content — only the diagnostics — so the fallback-rate view can
        count hard failures alongside the runs that did produce output.

        `prior_agentic_failure` preserves *why* the agentic loop was abandoned
        before single-shot also failed; without it a backend that stops
        supporting tool use and then goes down entirely would look like a plain
        outage.
        """
        diagnostics: dict[str, Any] = {
            "agentic_path": False,
            "fallback_reason": FALLBACK_BACKEND_UNAVAILABLE,
        }
        if prior_agentic_failure:
            diagnostics["prior_agentic_failure"] = prior_agentic_failure
        if error is not None:
            diagnostics["error_type"] = type(error).__name__

        await self._log_conversation(
            messages=[],
            response="",
            system=None,
            model=self._model_name_for_provider(),
            prompt_version=system_prompt_version,
            run_diagnostics=diagnostics,
            redaction_events=self.last_redaction_events or None,
        )

    def _build_med_specialty_map(self, profile) -> dict[str, str]:
        """Build a mapping of medication name → prescribing specialty.

        Matches medication.prescribing_doctor (free text) against profile's
        Doctor records to find the specialty. Returns dict like
        {"fluocinonide (LIDEX)": "Dermatology"}.
        """
        med_map: dict[str, str] = {}
        profile_doctors = list(getattr(profile, 'doctors', []))

        for med in getattr(profile, 'medications', []):
            if not med.prescribing_doctor:
                continue
            prescriber_lower = med.prescribing_doctor.lower()
            for doc in profile_doctors:
                doc_specialty = doc.specialty or _infer_specialty_from_clinic(doc.clinic)
                if not doc_specialty:
                    continue
                doc_name_lower = doc.name.lower()
                if (doc_name_lower in prescriber_lower
                        or prescriber_lower in doc_name_lower):
                    med_map[med.name] = doc_specialty
                    break

        return med_map

    def _build_anonymized_context(
        self,
        profile: AnonymizedProfile,
        appointment: AnonymizedAppointment,
        past_visits: list[AnonymizedAppointment],
        clinical_data: dict[str, Any],
        med_specialty_map: dict[str, str],
        conditions_raw: list,
        additional_concerns: Optional[str] = None,
    ) -> str:
        """Build specialty-aware context message for the LLM.

        All PII has been removed per DEC-006.
        """
        lines = [
            "Generate visit preparation questions based on the following patient data:",
            "",
            "## Patient Information",
        ]

        if profile.age_description:
            lines.append(f"- Age: {profile.age_description}")
        if profile.blood_type:
            lines.append(f"- Blood Type: {profile.blood_type}")
        if profile.allergies:
            lines.append(f"- Allergies: {profile.allergies}")

        # Upcoming appointment — use inferred specialty if doctor.specialty is None
        inferred_specialty = appointment.doctor.specialty or _infer_specialty_from_clinic(appointment.doctor.clinic)
        lines.extend(["", "## Upcoming Appointment"])
        lines.append(f"- Provider: {appointment.doctor.title}")
        if inferred_specialty:
            lines.append(f"- Specialty: {inferred_specialty}")
        if appointment.doctor.clinic:
            lines.append(f"- Clinic: {appointment.doctor.clinic}")
        lines.append(f"- Date: {appointment.scheduled_date}")
        if appointment.purpose:
            lines.append(f"- Purpose: {appointment.purpose}")
        if appointment.doctor.notes:
            lines.append(f"- Provider Notes: {appointment.doctor.notes}")

        # Medical conditions with ICD-10 and specialty tags
        if conditions_raw:
            lines.extend(["", "## Medical Conditions"])
            # profile.conditions was built from this same list, in the same
            # order (see anonymize_profile) — zip rather than re-anonymizing
            # cond.notes here, which would double the redaction events for
            # issue #16's per-request aggregation.
            for cond, anon_cond in zip(conditions_raw, profile.conditions):
                icd = getattr(cond, 'icd_10', None)
                name = cond.name
                status = cond.status or "active"
                severity = getattr(cond, 'severity', None)

                # Build condition line
                parts = [f"- {name}"]
                if icd:
                    parts.append(f"({icd})")
                parts.append(f"[{status}]")
                if severity:
                    parts.append(f"severity: {severity}")

                # Add specialty tag from ICD-10
                specialties = _icd10_to_specialties(icd)
                if specialties:
                    parts.append(f"— typically managed by: {', '.join(specialties)}")

                lines.append(" ".join(parts))

                notes = anon_cond.get('notes')
                if notes:
                    lines.append(f"  Notes: {notes}")

        # Medications with specialty tags
        if profile.medications:
            lines.extend(["", "## Current Medications"])
            for med in profile.medications:
                med_line = f"- {med['name']}"
                if med.get('dosage'):
                    med_line += f" ({med['dosage']})"
                if med.get('frequency'):
                    med_line += f" — {med['frequency']}"

                # Add specialty tag if we know who prescribed it
                specialty_tag = med_specialty_map.get(med['name'])
                if specialty_tag:
                    med_line += f" [prescribed for {specialty_tag}]"

                lines.append(med_line)
                if med.get('purpose'):
                    lines.append(f"  Purpose: {med['purpose']}")
                if med.get('side_effects'):
                    lines.append(f"  Known side effects: {med['side_effects']}")

        # Lab orders
        lab_orders = clinical_data.get("lab_orders", [])
        if lab_orders:
            lines.extend(["", "## Recent Lab Orders"])
            for lab in lab_orders:
                date_str = lab.ordered_date or "date unknown"
                lines.append(f"- {lab.test_name} (ordered: {date_str})")

        # Vitals trend
        vitals_list = clinical_data.get("vitals", [])
        if vitals_list:
            lines.extend(["", "## Vitals History (most recent first)"])
            for v in vitals_list:
                parts = []
                if v.weight:
                    parts.append(f"Weight: {v.weight}")
                if v.bmi:
                    parts.append(f"BMI: {v.bmi}")
                if v.blood_pressure:
                    parts.append(f"BP: {v.blood_pressure}")
                if v.heart_rate:
                    parts.append(f"HR: {v.heart_rate}")
                if parts:
                    date_str = v.measured_date or "date unknown"
                    lines.append(f"- {date_str}: {', '.join(parts)}")

        # Pending follow-ups
        follow_ups = clinical_data.get("follow_ups", [])
        if follow_ups:
            lines.extend(["", "## Pending Follow-ups"])
            for fu in follow_ups:
                timeframe = f" (within {fu.timeframe})" if fu.timeframe else ""
                lines.append(f"- {fu.description}{timeframe}")

        # Active referrals
        referrals = clinical_data.get("referrals", [])
        if referrals:
            lines.extend(["", "## Active Referrals"])
            for ref in referrals:
                reason = f" — {ref.reason}" if ref.reason else ""
                lines.append(f"- {ref.specialty}{reason}")

        # Past visits context (anonymized)
        if past_visits:
            lines.extend(["", "## Relevant Past Visits"])
            for visit in past_visits:
                lines.append(f"### Visit with {visit.doctor.title}")
                lines.append(f"- Date: {visit.scheduled_date}")
                if visit.purpose:
                    lines.append(f"- Purpose: {visit.purpose}")
                if visit.prep_notes:
                    lines.append(f"- Planned to discuss: {visit.prep_notes}")
                if visit.visit_notes:
                    lines.append(f"- Notes: {visit.visit_notes}")
                lines.append("")

        # Additional concerns
        if additional_concerns:
            lines.extend(["", "## Additional Patient Concerns", additional_concerns])

        return "\n".join(lines)

    def _get_fallback_response(self, prior_agentic_failure: Optional[str] = None) -> dict[str, Any]:
        """Get fallback response when LLM is unavailable.

        `used_fallback: True` is the only signal (besides a backend log)
        that this is generic placeholder content, not something the model
        actually generated — see issue #47. Callers must surface it to the
        user rather than let it look like a normal successful generation.
        """
        return {
            "questions": {
                "General Questions": [
                    "What should I know about my current medications?",
                    "Are there any lifestyle changes I should consider?",
                    "What symptoms should I watch out for?",
                    "When should I schedule a follow-up?",
                ]
            },
            "context_summary": "Default questions generated due to AI service unavailability.",
            "used_fallback": True,
            "agentic_path": False,
            "fallback_reason": FALLBACK_BACKEND_UNAVAILABLE,
            "prior_agentic_failure": prior_agentic_failure,
        }
