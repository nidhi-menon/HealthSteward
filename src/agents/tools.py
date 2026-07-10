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

from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.agents.llm_backend import uses_openai_style_wire_format
from src.data.models import Appointment, Medication
from src.utils.anonymization import Anonymizer

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
            "the provided context, optionally filtered by specialty or keyword."
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

    def __init__(self, db: AsyncSession, anonymizer: Anonymizer, profile_id: str):
        self.db = db
        self.anonymizer = anonymizer
        self.profile_id = profile_id

    async def execute(self, name: str, tool_input: dict[str, Any]) -> str:
        """Execute a tool by name and return an anonymized string result."""
        if name == "get_medication_details":
            return await self._get_medication_details(tool_input.get("medication_name"))
        if name == "lookup_past_visits":
            return await self._lookup_past_visits(
                tool_input.get("specialty"), tool_input.get("keyword")
            )
        return f"Unknown tool: {name}"

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
            anon = self.anonymizer.anonymize_appointment(appt)
            lines.append(f"### Visit with {anon.doctor.title} on {anon.scheduled_date}")
            if anon.purpose:
                lines.append(f"Purpose: {anon.purpose}")
            if anon.visit_notes:
                lines.append(f"Notes: {anon.visit_notes}")
            lines.append("")

        return "\n".join(lines)
