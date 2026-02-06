"""Visit preparation agent using Claude to generate personalized questions."""

from typing import Any, Optional

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from src.agents.base import BaseAgent
from src.data.models import Appointment


class VisitPrepAgent(BaseAgent):
    """Agent for generating AI-powered doctor visit preparation."""

    SYSTEM_PROMPT = """You are a helpful healthcare assistant preparing a patient for their upcoming doctor visit.

Your task is to generate personalized, relevant questions the patient should ask their doctor based on:
- Their medical conditions
- Current medications
- The purpose of this visit
- The doctor's specialty

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
- If the purpose of the visit is specified, focus questions on that topic"""

    def __init__(self, db: AsyncSession):
        """Initialize the visit prep agent."""
        super().__init__(db)

    async def prepare_visit(
        self,
        appointment: Appointment,
        additional_concerns: Optional[str] = None,
    ) -> dict[str, Any]:
        """Generate visit preparation questions and context.

        Args:
            appointment: Appointment with eager-loaded profile, conditions, medications, doctor
            additional_concerns: Optional additional concerns from the patient

        Returns:
            Dict with 'questions' (categorized) and 'context_summary'
        """
        # Build context message
        context = self._build_context(appointment, additional_concerns)

        messages = [{"role": "user", "content": context}]

        try:
            response = await self._call_claude(
                messages=messages,
                system=self.SYSTEM_PROMPT,
                temperature=0.7,
            )

            # Parse JSON response
            parsed = self._parse_json_response(response)

            if parsed and "questions" in parsed:
                return {
                    "questions": parsed.get("questions", {}),
                    "context_summary": parsed.get("context_summary", ""),
                }
            else:
                # Fallback: return raw response as context
                logger.warning("Could not parse JSON from Claude response")
                return {
                    "questions": {"General Questions": [response]},
                    "context_summary": "AI generated visit preparation (raw response).",
                }

        except Exception as e:
            logger.error(f"Visit prep generation failed: {e}")
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

    def _build_context(
        self,
        appointment: Appointment,
        additional_concerns: Optional[str] = None,
    ) -> str:
        """Build context message for Claude from appointment data.

        Args:
            appointment: Appointment with related data
            additional_concerns: Optional additional patient concerns

        Returns:
            Formatted context string
        """
        profile = appointment.profile
        doctor = appointment.doctor

        lines = [
            "Please generate visit preparation questions based on the following information:",
            "",
            "## Patient Information",
            f"- Name: {profile.name}",
        ]

        if profile.date_of_birth:
            lines.append(f"- Date of Birth: {profile.date_of_birth}")

        if profile.blood_type:
            lines.append(f"- Blood Type: {profile.blood_type}")

        if profile.allergies:
            lines.append(f"- Allergies: {profile.allergies}")

        lines.extend([
            "",
            "## Appointment Details",
            f"- Doctor: {doctor.name}",
        ])

        if doctor.specialty:
            lines.append(f"- Specialty: {doctor.specialty}")

        if doctor.clinic:
            lines.append(f"- Clinic: {doctor.clinic}")

        lines.append(f"- Date: {appointment.scheduled_date}")

        if appointment.purpose:
            lines.append(f"- Purpose: {appointment.purpose}")

        if appointment.notes:
            lines.append(f"- Notes: {appointment.notes}")

        # Add conditions
        if profile.conditions:
            lines.extend(["", "## Medical Conditions"])
            for condition in profile.conditions:
                status_info = f" ({condition.status})" if condition.status else ""
                severity_info = f" - Severity: {condition.severity}" if condition.severity else ""
                lines.append(f"- {condition.name}{status_info}{severity_info}")
                if condition.notes:
                    lines.append(f"  Notes: {condition.notes}")

        # Add medications
        if profile.medications:
            lines.extend(["", "## Current Medications"])
            for med in profile.medications:
                med_line = f"- {med.name}"
                if med.dosage:
                    med_line += f" ({med.dosage})"
                if med.frequency:
                    med_line += f" - {med.frequency}"
                lines.append(med_line)
                if med.purpose:
                    lines.append(f"  Purpose: {med.purpose}")
                if med.side_effects:
                    lines.append(f"  Known side effects: {med.side_effects}")

        # Add additional concerns
        if additional_concerns:
            lines.extend([
                "",
                "## Additional Patient Concerns",
                additional_concerns,
            ])

        return "\n".join(lines)
