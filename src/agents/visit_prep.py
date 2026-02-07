"""Visit preparation agent using Claude or Ollama to generate personalized questions.

This module implements DEC-006 (PII Anonymization) and DEC-008 (Intelligent Context Selection):
- All data is anonymized before sending to the LLM
- Relevant past visit context is intelligently selected
- Supports both Claude API and local Ollama
- Logs only anonymized content to ConversationLog
"""

from typing import Any, Optional

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.agents.base import BaseAgent
from src.agents.ollama_client import OllamaClient, get_ollama_client
from src.config import get_settings
from src.data.models import Appointment
from src.utils.anonymization import Anonymizer, AnonymizedAppointment, AnonymizedProfile
from src.utils.context_selection import ContextSelector, ContextSelectionResult


class VisitPrepAgent(BaseAgent):
    """Agent for generating AI-powered doctor visit preparation.

    Uses anonymization and intelligent context selection per DEC-006 and DEC-008.
    """

    SYSTEM_PROMPT = """You are a helpful healthcare assistant preparing a patient for their upcoming doctor visit.

Your task is to generate personalized, relevant questions the patient should ask their doctor based on:
- Their medical conditions
- Current medications
- The purpose of this visit
- The doctor's specialty
- Relevant past visit notes (if provided)

Generate questions that are:
1. Prioritized by importance (most important first)
2. Categorized by topic (e.g., "Medication Questions", "Symptom Questions", "Lifestyle Questions")
3. Specific to their health situation
4. Actionable and clear

Respond with a JSON object in this exact format:
{
    "questions": {
        "Category Name": [
            "Question 1 text",
            "Question 2 text"
        ],
        "Another Category": [
            "Question text"
        ]
    },
    "context_summary": "A brief 2-3 sentence summary of the patient's key health context relevant to this visit."
}

Important:
- Generate 5-10 questions total across all categories
- Make questions specific to their conditions and medications
- Include questions about potential drug interactions if multiple medications
- If the purpose of the visit is specified, focus questions on that topic
- Reference relevant information from past visits if provided"""

    def __init__(self, db: AsyncSession):
        """Initialize the visit prep agent."""
        super().__init__(db)
        self.settings = get_settings()
        self.anonymizer = Anonymizer(use_ner=self.settings.use_ner_anonymization)
        self.context_selector = ContextSelector(
            anonymizer=self.anonymizer,
            stage2_threshold=self.settings.context_stage2_threshold,
            relevance_cutoff=self.settings.context_relevance_cutoff,
        )
        self._ollama_client: Optional[OllamaClient] = None

    async def _get_ollama_client(self) -> Optional[OllamaClient]:
        """Get Ollama client if available."""
        if self._ollama_client is None:
            self._ollama_client = await get_ollama_client()
        return self._ollama_client

    async def _get_past_appointments(self, profile_id: str, current_appointment_id: str) -> list[Appointment]:
        """Get past completed appointments for context.

        Args:
            profile_id: The profile to get appointments for
            current_appointment_id: The current appointment to exclude

        Returns:
            List of past completed appointments with doctor relationships
        """
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

    async def prepare_visit(
        self,
        appointment: Appointment,
        additional_concerns: Optional[str] = None,
    ) -> dict[str, Any]:
        """Generate visit preparation questions and context.

        Uses anonymization and context selection per DEC-006 and DEC-008.

        Args:
            appointment: Appointment with eager-loaded profile, conditions, medications, doctor
            additional_concerns: Optional additional concerns from the patient

        Returns:
            Dict with 'questions' (categorized) and 'context_summary'
        """
        # Step 1: Get past appointments for context
        past_appointments = await self._get_past_appointments(
            appointment.profile_id,
            appointment.id
        )

        # Step 2: Select relevant context (4-stage pipeline)
        context_result = await self.context_selector.select_context(
            target_appointment=appointment,
            all_past_appointments=past_appointments,
            max_tokens=self.settings.context_max_tokens,
        )

        logger.info(
            f"Context selection: {context_result.total_visits_considered} total, "
            f"{context_result.visits_after_stage1} after rules, "
            f"selected {len(context_result.selected_visits)} visits"
        )

        # Step 3: Anonymize current profile and appointment
        anonymized_profile = self.anonymizer.anonymize_profile(appointment.profile)
        anonymized_appointment = self.anonymizer.anonymize_appointment(appointment)

        # Step 4: Build anonymized context message
        context = self._build_anonymized_context(
            profile=anonymized_profile,
            appointment=anonymized_appointment,
            past_visits=context_result.selected_visits,
            additional_concerns=self.anonymizer.anonymize_text(additional_concerns),
        )

        messages = [{"role": "user", "content": context}]

        try:
            # Step 5: Call LLM (Claude or Ollama based on config)
            if self.settings.llm_provider == "ollama":
                response = await self._call_ollama(messages, self.SYSTEM_PROMPT)
            else:
                response = await self._call_claude(
                    messages=messages,
                    system=self.SYSTEM_PROMPT,
                    temperature=0.7,
                )

            # Step 6: Parse JSON response
            parsed = self._parse_json_response(response)

            if parsed and "questions" in parsed:
                return {
                    "questions": parsed.get("questions", {}),
                    "context_summary": parsed.get("context_summary", ""),
                }
            else:
                logger.warning("Could not parse JSON from LLM response")
                return {
                    "questions": {"General Questions": [response]},
                    "context_summary": "AI generated visit preparation (raw response).",
                }

        except Exception as e:
            logger.error(f"Visit prep generation failed: {e}")
            return self._get_fallback_response()

    async def _call_ollama(self, messages: list[dict], system: str) -> str:
        """Call Ollama for generation.

        Args:
            messages: List of message dicts
            system: System prompt

        Returns:
            Generated response text
        """
        client = await self._get_ollama_client()
        if not client:
            raise RuntimeError("Ollama is not available")

        # Convert to Ollama format with system message
        ollama_messages = [{"role": "system", "content": system}]
        ollama_messages.extend(messages)

        response = await client.chat(
            messages=ollama_messages,
            temperature=0.7,
        )

        # Log conversation (anonymized content only)
        await self._log_conversation(
            messages=messages,
            response=response,
            system=system,
            input_tokens=None,  # Ollama doesn't report tokens the same way
            output_tokens=None,
        )

        return response

    def _build_anonymized_context(
        self,
        profile: AnonymizedProfile,
        appointment: AnonymizedAppointment,
        past_visits: list[AnonymizedAppointment],
        additional_concerns: Optional[str] = None,
    ) -> str:
        """Build anonymized context message for the LLM.

        All PII has been removed per DEC-006.

        Args:
            profile: Anonymized health profile
            appointment: Anonymized current appointment
            past_visits: List of anonymized past visits
            additional_concerns: Optional anonymized concerns

        Returns:
            Formatted context string
        """
        lines = [
            "Please generate visit preparation questions based on the following information:",
            "",
            "## Patient Information",
        ]

        if profile.age_description:
            lines.append(f"- Age: {profile.age_description}")

        if profile.blood_type:
            lines.append(f"- Blood Type: {profile.blood_type}")

        if profile.allergies:
            lines.append(f"- Allergies: {profile.allergies}")

        # Appointment details (anonymized)
        lines.extend([
            "",
            "## Upcoming Appointment",
            f"- Provider: {appointment.doctor.title}",
        ])

        if appointment.doctor.specialty:
            lines.append(f"- Specialty: {appointment.doctor.specialty}")

        if appointment.doctor.clinic:
            lines.append(f"- Clinic: {appointment.doctor.clinic}")

        lines.append(f"- Date: {appointment.scheduled_date}")

        if appointment.purpose:
            lines.append(f"- Purpose: {appointment.purpose}")

        # Medical conditions (kept per DEC-006)
        if profile.conditions:
            lines.extend(["", "## Medical Conditions"])
            for condition in profile.conditions:
                status_info = f" ({condition['status']})" if condition.get('status') else ""
                severity_info = f" - Severity: {condition['severity']}" if condition.get('severity') else ""
                lines.append(f"- {condition['name']}{status_info}{severity_info}")
                if condition.get('notes'):
                    lines.append(f"  Notes: {condition['notes']}")

        # Medications (kept per DEC-006)
        if profile.medications:
            lines.extend(["", "## Current Medications"])
            for med in profile.medications:
                med_line = f"- {med['name']}"
                if med.get('dosage'):
                    med_line += f" ({med['dosage']})"
                if med.get('frequency'):
                    med_line += f" - {med['frequency']}"
                lines.append(med_line)
                if med.get('purpose'):
                    lines.append(f"  Purpose: {med['purpose']}")
                if med.get('side_effects'):
                    lines.append(f"  Known side effects: {med['side_effects']}")
                if med.get('prescribed_by'):
                    lines.append(f"  Prescribed by: {med['prescribed_by']}")

        # Past visits context (anonymized)
        if past_visits:
            lines.extend(["", "## Relevant Past Visits"])
            for visit in past_visits:
                lines.append(f"### Visit with {visit.doctor.title}")
                lines.append(f"- Date: {visit.scheduled_date}")
                if visit.purpose:
                    lines.append(f"- Purpose: {visit.purpose}")
                if visit.visit_notes:
                    lines.append(f"- Notes: {visit.visit_notes}")
                lines.append("")

        # Additional concerns (anonymized)
        if additional_concerns:
            lines.extend([
                "",
                "## Additional Patient Concerns",
                additional_concerns,
            ])

        return "\n".join(lines)

    def _get_fallback_response(self) -> dict[str, Any]:
        """Get fallback response when LLM is unavailable."""
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
        }
