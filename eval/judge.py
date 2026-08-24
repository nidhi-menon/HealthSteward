"""LLM-judge factual-groundedness scorer for visit-prep generation output.

Distinct from eval/scorers.py's score_groundedness (a cheap, deterministic
entity-substring pass): that check flags a question as "ungrounded" purely
for not containing a literal entity name, even when it makes no unsupported
claim (e.g. "Are there any changes to my medication regimen?"). This module
instead asks a judge model to read each generated question, enumerate the
distinct factual claims it makes, and verdict each one against the patient's
actual fixture data — allowing paraphrase/synonym/category reference, and
only flagging a claim as unsupported if it asserts something as fact (a
specific patient detail, or a named external authority/specialty
assignment) that isn't traceable to the provided context. See DEC-042 for
the rubric design and judge-model choice.

The judge model is deliberately a different, stronger tier
(settings.anthropic_judge_model) than any Claude model used for generation,
to reduce self-grading bias (see src/config.py's comment on that field) —
and independent of this project's default local Ollama generation backend,
so there is no self-grading concern in the current default configuration
either way.
"""

import json
import re
import time
from typing import Any, Optional

from eval.fixtures import EvalCase
from src.agents.llm_backend import ClaudeBackend

# Bumped whenever this prompt's wording changes in a way that could affect
# judgments — see docs/notes/PROMPT_CHANGELOG.md.
FACTUAL_GROUNDEDNESS_JUDGE_PROMPT_VERSION = "v3"

_JUDGE_SYSTEM_PROMPT = """You are an independent fact-checking judge for an AI health-coordination \
tool. You will be shown a patient's actual medical record data and a set of \
"visit preparation" questions, and the short context summary shown alongside \
them, the tool generated for that patient's upcoming appointment. Your job is \
to check both for unsupported factual claims — the context summary is shown \
to the patient exactly like the questions are, and must be checked with the \
same rigor, not skimmed as a formality.

For EACH generated question, and separately for the context summary, first \
identify every distinct factual claim made — a question or the summary can \
contain zero, one, or more than one claim. A claim is any assertion presented \
as fact, including an assertion embedded in a question's phrasing (e.g. \
"since my Levothyroxine dose was recently increased" asserts a dose increase \
as fact, even though the sentence is a question). Purely open-ended or \
logistical questions with no factual assertion (e.g. "Do you have any other \
concerns?") have zero claims.

For each claim, give a verdict:
- "grounded": supported by the patient's provided data below. Paraphrase, \
synonyms, and category references count as grounded — do NOT require a \
literal string match. E.g. "your cholesterol medication" is grounded if the \
patient's record lists a statin, even though "cholesterol" never appears in \
the record.
- "unsupported": asserts something as a specific fact — a patient-specific \
detail, OR a named external authority/guideline (e.g. "the American Thyroid \
Association's guidelines", "per ADA recommendations"), OR an assertion of \
which specialty typically manages a condition (e.g. "which is typically \
managed by Pulmonology") — that is not present in, or contradicts, the \
patient's provided data below. A named authority/guideline or a specialty-\
management assertion is ALWAYS "unsupported", never "not_applicable", even \
when it is phrased as a general/textbook-sounding statement rather than a \
patient-specific one — being general in tone does not make it verifiable; \
this codebase has no source for external clinical guidelines or specialty-\
assignment conventions, so such a claim can never be "grounded" either \
unless the patient's own record explicitly states it.
- "not_applicable": no verifiable factual content at all (open-ended/\
logistical questions), or lifestyle guidance that recommends an action \
("try reducing sodium intake") without asserting any external authority, \
guideline, or specialty-management fact. If the sentence names or invokes \
any specific outside source, organization, or specialty-assignment \
convention, it is NOT "not_applicable" — use "unsupported" per above.

Every claim, of every verdict, MUST include a one-to-two sentence reasoning \
field explaining why. Do not skip reasoning for "grounded" claims.

Respond with ONLY a JSON object (no markdown fences, no other text) matching \
this shape:
{
  "claims": [
    {
      "category": "<the question's category>",
      "question": "<the exact question text>",
      "claim_text": "<the specific claim within the question>",
      "verdict": "grounded" | "unsupported" | "not_applicable",
      "reasoning": "<why>"
    }
  ]
}"""


def _case_context_text(case: EvalCase) -> str:
    """Render the patient's actual fixture data as text for the judge prompt.

    Deliberately includes off-scope data too (e.g. cross_specialty_scope's
    dermatology medication) — the judge is checking "is this claim true
    given the patient's real record", not "is this in scope for this visit"
    (that's score_scope's job, a separate deterministic check).
    """
    lines = [
        f"Appointment purpose: {case.appointment_purpose}",
        f"Appointment date: {case.appointment_scheduled_date}",
    ]

    target_doctor = next((d for d in case.doctors if d.key == case.target_doctor_key), None)
    if target_doctor:
        detail = f"Appointment doctor: {target_doctor.name}"
        if target_doctor.specialty:
            detail += f" ({target_doctor.specialty})"
        if target_doctor.clinic:
            detail += f", {target_doctor.clinic}"
        lines.append(detail)

    if case.conditions:
        lines.append("\nConditions:")
        for c in case.conditions:
            detail = f"- {c.name}"
            if c.icd_10:
                detail += f" ({c.icd_10})"
            detail += f" [{c.status}]"
            if c.notes:
                detail += f" — {c.notes}"
            lines.append(detail)

    if case.medications:
        lines.append("\nMedications:")
        for m in case.medications:
            detail = f"- {m.name}"
            if m.dosage:
                detail += f" {m.dosage}"
            if m.frequency:
                detail += f", {m.frequency}"
            if m.purpose:
                detail += f" (for: {m.purpose})"
            lines.append(detail)

    if case.lab_orders:
        lines.append("\nLab orders:")
        for lab in case.lab_orders:
            detail = f"- {lab.test_name}"
            if lab.ordered_date:
                detail += f" (ordered {lab.ordered_date})"
            lines.append(detail)

    if case.vitals:
        lines.append("\nVitals:")
        for v in case.vitals:
            parts = [p for p in [v.weight and f"weight {v.weight}", v.bmi and f"BMI {v.bmi}",
                                  v.blood_pressure and f"BP {v.blood_pressure}",
                                  v.heart_rate and f"HR {v.heart_rate}"] if p]
            if parts:
                lines.append(f"- {', '.join(parts)}" + (f" (measured {v.measured_date})" if v.measured_date else ""))

    if case.past_visits:
        lines.append("\nPast visits:")
        for pv in case.past_visits:
            detail = f"- {pv.scheduled_date}"
            if pv.purpose:
                detail += f": {pv.purpose}"
            lines.append(detail)

    return "\n".join(lines)


def _questions_text(result: dict[str, Any]) -> str:
    """Renders the generated questions AND the context summary — the summary
    is shown to the patient exactly like the questions are and has its own
    real hallucination history (found via DEC-042's ad hoc manual review:
    an unhedged "typically managed by Pulmonology" claim lived here, not in
    any question, and earlier judge runs silently never scored it)."""
    lines = []
    for category, questions in (result.get("questions") or {}).items():
        lines.append(f"\n{category}:")
        for q in questions or []:
            lines.append(f"- {q}")

    context_summary = result.get("context_summary")
    if context_summary:
        lines.append("\nContext Summary (shown to the patient alongside the questions above):")
        lines.append(f"- {context_summary}")

    return "\n".join(lines)


def _parse_judge_response(text: str) -> dict[str, Any]:
    """Strip markdown code fences if present, then parse as JSON. Raises
    ValueError with the raw text included on failure — a judge-parsing
    failure for one case should surface loudly in the eval report, not be
    silently swallowed or repaired (this is an eval-only path, not
    production generation, so there's no user-facing fallback to protect)."""
    stripped = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    try:
        return json.loads(stripped)
    except json.JSONDecodeError as e:
        raise ValueError(f"Judge response was not valid JSON: {e}\n\nRaw response:\n{text}") from e


async def score_factual_groundedness(
    case: EvalCase, result: dict[str, Any], judge_backend: ClaudeBackend
) -> dict[str, Any]:
    """Runs the LLM-judge factual-groundedness check for one case's generated
    output. Returns per-claim verdicts, the aggregate unsupported-claim rate,
    and cost/latency for the judge call itself (judge_model, input_tokens,
    output_tokens, duration_s) — logged per DEC-042 so a paper's methods
    section can disclose what running this eval costs, and so repeated runs
    can be sized against an actual per-call cost/latency budget.
    """
    user_message = (
        f"Patient's actual record:\n{_case_context_text(case)}\n\n"
        f"Generated visit-prep questions:\n{_questions_text(result)}"
    )

    # Bounded retries on a transient empty/malformed response — observed in
    # practice (an occasional empty turn.text from the API, unrelated to
    # prompt content or length: it has recurred on cases well under the
    # token ceiling, and twice consecutively at least once, so 2 attempts
    # wasn't always enough). This retries the API call itself, not
    # "repairs" malformed JSON content — _parse_judge_response's
    # no-silent-repair principle for genuinely malformed non-empty content
    # is unchanged; exhausting every attempt still raises loudly rather
    # than being swallowed.
    _MAX_JUDGE_ATTEMPTS = 3
    start = time.perf_counter()
    last_error: Optional[Exception] = None
    for attempt in range(_MAX_JUDGE_ATTEMPTS):
        turn = await judge_backend.call(
            messages=[{"role": "user", "content": user_message}],
            system=_JUDGE_SYSTEM_PROMPT,
            temperature=0.0,
        )
        try:
            parsed = _parse_judge_response(turn.text or "")
            last_error = None
            break
        except ValueError as e:
            last_error = e
    if last_error is not None:
        raise last_error
    duration_s = time.perf_counter() - start

    claims = parsed.get("claims", [])

    scored = [c for c in claims if c.get("verdict") in ("grounded", "unsupported")]
    unsupported = [c for c in scored if c["verdict"] == "unsupported"]
    unsupported_rate = len(unsupported) / len(scored) if scored else None

    return {
        "prompt_version": FACTUAL_GROUNDEDNESS_JUDGE_PROMPT_VERSION,
        "judge_model": judge_backend.model,
        "claims": claims,
        "unsupported_rate": unsupported_rate,
        "unsupported_claims": unsupported,
        "input_tokens": turn.input_tokens,
        "output_tokens": turn.output_tokens,
        "duration_s": duration_s,
    }
