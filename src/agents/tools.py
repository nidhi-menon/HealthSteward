"""Read-only tools available to the visit-prep agentic loop (DEC-009, DEC-013).

Two tools are implemented for v1, deliberately bounded in scope:
- get_medication_details: on-demand structured access to the patient's
  medication list, so the agent can pull details without prompt bloat.
  This is NOT a real drug-interaction checker — it exposes existing data
  for the model to reason over. A licensed interaction-checking API is a
  separate, bigger feature.
- lookup_past_visits: on-demand deeper visit history query, wrapping the
  same DB query already used for context selection.

Every tool result is anonymized before being returned to the loop, for
all backends (Ollama, Claude, or a custom provider — DEC-016) — consistent
with how prepare_visit() already anonymizes the main context regardless
of provider.
"""

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.agents.llm_backend import uses_openai_style_wire_format
from src.data.models import Appointment, Medication
from src.utils.anonymization import Anonymizer, RedactionEvent


class UnknownToolError(Exception):
    """Raised when the model calls a tool name VisitPrepTools doesn't recognize.

    Caught alongside ToolCallParsingError/RuntimeError in visit_prep.py's
    agentic loop, so a hallucinated tool name triggers the same single-shot
    fallback as other loop failures rather than being fed back into the
    conversation as if it were a real tool result.
    """

# Version tag for the model-facing text in TOOL_SPECS below (the `description`
# strings and their `parameters` descriptions). These are prompt content — the
# model reads them to decide which tool to call and with what arguments — so
# they fall under the project's prompt-versioning convention, even though they
# aren't a system prompt. Bump this and add a PROMPT_CHANGELOG.md entry for any
# wording change that could plausibly affect tool-selection behavior.
#
# Not yet carried into ConversationLog's extra_data the way the visit-prep
# system prompts' versions are — same traceability gap PROMPT_CHANGELOG.md
# already notes for the Stage 2 and AVS parser prompts.
TOOL_SPECS_VERSION = "v2-2026-08-03"

# Canonical tool specs (name, description, JSON-schema parameters).
# Adapted per-backend below since Claude and Ollama expect different shapes.
TOOL_SPECS: list[dict[str, Any]] = [
    {
        "name": "get_medication_details",
        "description": (
            "Get full details (dosage, frequency, purpose, known side effects) "
            "for the patient's current medications. Use this to check for "
            "potential interactions or overlaps before finalizing questions."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "medication_name": {
                    "type": "string",
                    "description": "Optional: a specific medication name to look up. Omit to get all current medications.",
                },
            },
            "required": [],
        },
    },
    {
        "name": "lookup_past_visits",
        "description": (
            "Look up past completed visits beyond what's already included in "
            "the provided context, optionally filtered by specialty or keyword. "
            "With no filters, returns visits since the patient last saw the "
            "provider for this appointment — i.e. what's happened in between. "
            "Pass a specialty or keyword to search the patient's full history "
            "instead."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "specialty": {
                    "type": "string",
                    "description": "Optional: filter to visits with doctors of this specialty.",
                },
                "keyword": {
                    "type": "string",
                    "description": "Optional: filter to visits whose purpose or notes contain this keyword.",
                },
            },
            "required": [],
        },
    },
]


def claude_tools() -> list[dict[str, Any]]:
    """Tool specs in Claude's {name, description, input_schema} shape."""
    return [
        {"name": t["name"], "description": t["description"], "input_schema": t["parameters"]}
        for t in TOOL_SPECS
    ]


def ollama_tools() -> list[dict[str, Any]]:
    """Tool specs in OpenAI-style {type, function} shape.

    Used for both Ollama and any custom OpenAI-compatible backend — Ollama's
    /api/chat tool-calling already mirrors OpenAI's function-calling format,
    so a third provider speaking the same wire format needs no new adapter.
    """
    return [
        {
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t["description"],
                "parameters": t["parameters"],
            },
        }
        for t in TOOL_SPECS
    ]


def get_tools_for_provider(provider: str) -> list[dict[str, Any]]:
    """Pick the right tool-spec shape for a given llm_provider value.

    Shares its ollama/custom-vs-claude split with `get_llm_backend()` via
    `uses_openai_style_wire_format` so an unrecognized provider value can't
    make this function and `get_llm_backend()` pick mismatched shapes.
    """
    return ollama_tools() if uses_openai_style_wire_format(provider) else claude_tools()


class VisitPrepTools:
    """Executes visit-prep tools against the database, anonymizing results."""

    def __init__(
        self,
        db: AsyncSession,
        anonymizer: Anonymizer,
        profile_id: str,
        exclude_appointment_ids: Optional[list[str]] = None,
        target_doctor_id: Optional[str] = None,
        current_appointment_id: Optional[str] = None,
    ):
        self.db = db
        self.anonymizer = anonymizer
        self.profile_id = profile_id
        # Visits context_selection.py's Stage 1-4 pipeline already selected
        # into the base prompt — excluded here so lookup_past_visits can't
        # redundantly re-fetch them (DEC-024).
        self.exclude_appointment_ids = exclude_appointment_ids or []
        # The doctor for the appointment being prepped. Anchors
        # lookup_past_visits' default date window to "since the patient last
        # saw this provider" (issue #21). None (no doctor on the appointment)
        # leaves the lookup unbounded, as it was before.
        self.target_doctor_id = target_doctor_id
        # The appointment being prepped. Excluded when picking the window
        # anchor, matching _get_past_appointments' `Appointment.id !=` guard —
        # prep can be run on an already-completed appointment, and without this
        # such an appointment would anchor the window to its own date and
        # window out the very history it's asking about.
        self.current_appointment_id = current_appointment_id
        # Redaction events (issue #16) from anonymizing tool results,
        # aggregated across every tool call this executor makes — read by
        # the caller after the agentic loop finishes and folded into the
        # per-visit-prep-request total logged on ConversationLog.
        self.redaction_events: list[RedactionEvent] = []

    async def execute(self, name: str, tool_input: dict[str, Any]) -> str:
        """Execute a tool by name and return an anonymized string result."""
        if name == "get_medication_details":
            return await self._get_medication_details(tool_input.get("medication_name"))
        if name == "lookup_past_visits":
            return await self._lookup_past_visits(
                tool_input.get("specialty"), tool_input.get("keyword")
            )
        raise UnknownToolError(f"Unknown tool: {name}")

    async def _get_medication_details(self, medication_name: Optional[str]) -> str:
        query = select(Medication).where(Medication.profile_id == self.profile_id)
        if medication_name:
            query = query.where(Medication.name.ilike(f"%{medication_name}%"))
        result = await self.db.execute(query)
        medications = list(result.scalars().all())

        if not medications:
            return "No matching medications found."

        lines = []
        for med in medications:
            parts = [f"- {med.name}"]
            if med.dosage:
                parts.append(f"({med.dosage})")
            if med.frequency:
                parts.append(f"— {med.frequency}")
            lines.append(" ".join(parts))
            if med.purpose:
                lines.append(f"  Purpose: {med.purpose}")
            if med.side_effects:
                lines.append(f"  Known side effects: {med.side_effects}")
            if med.prescribing_doctor:
                prescribed_by = self.anonymizer.anonymize_doctor_reference(
                    med.prescribing_doctor, context="prescribing"
                )
                lines.append(f"  Prescribed by: {prescribed_by}")

        return "\n".join(lines)

    async def _last_visit_date_with_target_provider(self) -> Optional[datetime]:
        """Date of the patient's most recent completed visit with the doctor
        this appointment is being prepped for, or None if there isn't one.

        Deliberately ignores `exclude_appointment_ids`: that list exists to stop
        the tool re-surfacing visits already in the prompt (DEC-024), but an
        excluded visit is still a real visit and still the correct anchor for
        "what's happened since then." Anchoring off a filtered set would silently
        widen the window whenever the anchor visit was already selected — which
        is the common case, since the last visit with this provider is exactly
        what context selection tends to pick.
        """
        if not self.target_doctor_id:
            return None

        query = (
            select(Appointment.scheduled_date)
            .where(
                Appointment.profile_id == self.profile_id,
                Appointment.doctor_id == self.target_doctor_id,
                Appointment.status == "completed",
            )
            .order_by(Appointment.scheduled_date.desc())
            .limit(1)
        )
        if self.current_appointment_id:
            query = query.where(Appointment.id != self.current_appointment_id)

        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def _lookup_past_visits(self, specialty: Optional[str], keyword: Optional[str]) -> str:
        query = (
            select(Appointment)
            .options(selectinload(Appointment.doctor))
            .where(
                Appointment.profile_id == self.profile_id,
                Appointment.status == "completed",
            )
            .order_by(Appointment.scheduled_date.desc())
        )

        # With no explicit filter, default to "what's happened since I last saw
        # this provider" rather than an unbounded history dig (issue #21). An
        # explicit specialty/keyword means the model is asking a targeted
        # question, so the window would only get in its way — the issue asks for
        # the filters to compose *on top of* the window, but the window itself
        # only applies when neither is supplied.
        window_start: Optional[datetime] = None
        if not specialty and not keyword:
            window_start = await self._last_visit_date_with_target_provider()
            if window_start is not None:
                # Inclusive, per the issue: the anchor visit is itself useful
                # context for what was covered last time.
                query = query.where(Appointment.scheduled_date >= window_start)

        if self.exclude_appointment_ids:
            query = query.where(Appointment.id.notin_(self.exclude_appointment_ids))
        result = await self.db.execute(query)
        appointments = list(result.scalars().all())

        if specialty:
            appointments = [
                a for a in appointments
                if a.doctor and a.doctor.specialty
                and specialty.lower() in a.doctor.specialty.lower()
            ]
        if keyword:
            keyword_lower = keyword.lower()
            appointments = [
                a for a in appointments
                if (a.purpose and keyword_lower in a.purpose.lower())
                or (a.visit_notes and keyword_lower in a.visit_notes.lower())
            ]

        if not appointments:
            return "No matching past visits found."

        lines = []
        for appt in appointments[:10]:  # bound the result size
            anon, events = self.anonymizer.anonymize_appointment(appt)
            self.redaction_events.extend(events)
            lines.append(f"### Visit with {anon.doctor.title} on {anon.scheduled_date}")
            if anon.purpose:
                lines.append(f"Purpose: {anon.purpose}")
            if anon.prep_notes:
                lines.append(f"Planned to discuss: {anon.prep_notes}")
            if anon.visit_notes:
                lines.append(f"Notes: {anon.visit_notes}")
            lines.append("")

        return "\n".join(lines)
