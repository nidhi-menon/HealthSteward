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
from src.agents.llm_backend import ToolCallParsingError, get_llm_backend
from src.agents.ollama_client import OllamaClient, get_ollama_client
from src.agents.tools import VisitPrepTools, claude_tools, ollama_tools
from src.config import get_settings
from src.data.models import Appointment, FollowUp, LabOrder, Referral, Vitals
from src.utils.anonymization import Anonymizer, AnonymizedAppointment, AnonymizedProfile
from src.utils.context_selection import ContextSelector, ContextSelectionResult


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


def _infer_specialty_from_clinic(clinic: Optional[str]) -> Optional[str]:
    """Infer doctor specialty from clinic name as a fallback.

    E.g. "Sutter Endocrinology - San Francisco" → "Endocrinology"
    """
    if not clinic:
        return None
    clinic_lower = clinic.lower()
    specialty_keywords = {
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
    for keyword, specialty in specialty_keywords.items():
        if keyword in clinic_lower:
            return specialty
    return None


class VisitPrepAgent(BaseAgent):
    """Agent for generating AI-powered doctor visit preparation.

    Uses anonymization and intelligent context selection per DEC-006 and DEC-008.
    """

    SYSTEM_PROMPT_TEMPLATE = """You are a healthcare assistant preparing a patient for a visit with their {specialty}.

Your task: generate focused, actionable questions the patient should ask THIS doctor based on the patient data provided.

IMPORTANT RULES:
- Only include questions relevant to this doctor's specialty ({specialty})
- Do NOT suggest discussing medications prescribed by unrelated specialists (e.g. don't ask an endocrinologist about topical dermatology creams)
- DO identify cross-condition interactions that ARE relevant to this specialty (e.g. how PCOS and Hashimoto's interact hormonally IS relevant for an endocrinologist, even if one was diagnosed by a gynecologist)
- Use the lab orders and vitals data to generate specific questions (e.g. "Your last TSH was ordered on [date] — ask about results and whether dosage adjustment is needed")
- Reference pending follow-ups if relevant to this specialty
- Note significant changes in vitals (weight, BMI, blood pressure) and ask about them if relevant

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

Use these categories (skip any that have no relevant questions):
- "Condition Management" — questions about conditions this specialist manages or that interact with their care
- "Medication Review" — only medications this specialist manages or that could interact with their treatments
- "Lab Results & Monitoring" — questions about recent or pending lab work relevant to this specialty
- "Lifestyle & Prevention" — actionable lifestyle questions specific to their conditions and this specialty
- "Follow-up Planning" — what to schedule next, referrals to discuss

Generate 8-15 questions total. Be specific — reference actual condition names, medication names, and lab test names from the patient data provided."""

    # Fallback when no specialty is known
    SYSTEM_PROMPT_GENERIC = """You are a healthcare assistant preparing a patient for an upcoming doctor visit.

Your task: generate focused, actionable questions the patient should ask their doctor based on the patient data provided.

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

Use these categories (skip any that have no relevant questions):
- "Condition Management" — questions about their active conditions
- "Medication Review" — questions about current medications
- "Lab Results & Monitoring" — questions about recent or pending lab work
- "Lifestyle & Prevention" — actionable lifestyle questions
- "Follow-up Planning" — what to schedule next

Generate 8-15 questions total. Be specific — reference actual condition names, medication names, and lab test names from the patient data provided."""

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

    async def prepare_visit(
        self,
        appointment: Appointment,
        additional_concerns: Optional[str] = None,
    ) -> dict[str, Any]:
        """Generate visit preparation questions and context.

        Uses anonymization and context selection per DEC-006 and DEC-008.
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

        # Step 3: Load clinical data (labs, vitals, follow-ups, referrals)
        clinical_data = await self._get_clinical_data(appointment.profile_id)

        # Step 4: Anonymize current profile and appointment
        anonymized_profile = self.anonymizer.anonymize_profile(appointment.profile)
        anonymized_appointment = self.anonymizer.anonymize_appointment(appointment)

        # Step 5: Resolve medication → doctor specialty for tagging
        med_specialty_map = self._build_med_specialty_map(appointment.profile)

        # Step 6: Build context message
        target_specialty = None
        if appointment.doctor:
            target_specialty = appointment.doctor.specialty or _infer_specialty_from_clinic(appointment.doctor.clinic)
        context = self._build_anonymized_context(
            profile=anonymized_profile,
            appointment=anonymized_appointment,
            past_visits=context_result.selected_visits,
            clinical_data=clinical_data,
            med_specialty_map=med_specialty_map,
            conditions_raw=list(getattr(appointment.profile, 'conditions', [])),
            additional_concerns=self.anonymizer.anonymize_text(additional_concerns),
        )

        system_prompt = self._get_system_prompt(target_specialty)
        messages = [{"role": "user", "content": context}]

        try:
            # Step 7: Call LLM — try the agentic tool-use loop first (DEC-009),
            # falling back to single-shot generation if it's disabled, the
            # backend can't do reliable tool use, or it doesn't converge.
            response = None
            if self.settings.agent_tool_use_enabled:
                try:
                    response = await self._run_agentic_loop(
                        appointment.profile_id, messages, system_prompt
                    )
                except (ToolCallParsingError, RuntimeError) as e:
                    logger.warning(f"Agentic tool-use loop failed, falling back to single-shot: {e}")
                    response = None

            if response is None:
                if self.settings.llm_provider == "ollama":
                    response = await self._call_ollama(messages, system_prompt)
                else:
                    response = await self._call_claude(
                        messages=messages,
                        system=system_prompt,
                        temperature=0.7,
                    )

            # Step 8: Parse JSON response
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

    async def _run_agentic_loop(
        self,
        profile_id: str,
        messages: list[dict],
        system: str,
    ) -> str:
        """Run the bounded agentic tool-use loop (DEC-009, DEC-013).

        Raises ToolCallParsingError/RuntimeError if the loop can't converge
        within settings.agent_max_turns — callers should fall back to
        single-shot generation on those exceptions.
        """
        backend = get_llm_backend(self.settings)
        tools = ollama_tools() if self.settings.llm_provider == "ollama" else claude_tools()
        tool_executor = VisitPrepTools(self.db, self.anonymizer, profile_id)

        conversation = list(messages)

        for turn in range(self.settings.agent_max_turns):
            result = await backend.call(conversation, system, tools=tools)

            if not result.tool_calls:
                model_name = (
                    self.settings.ollama_model
                    if self.settings.llm_provider == "ollama"
                    else self.settings.anthropic_model
                )
                await self._log_conversation(
                    messages=messages,
                    response=result.text or "",
                    system=system,
                    input_tokens=None,
                    output_tokens=None,
                    model=model_name,
                )
                return result.text or ""

            conversation.append(backend.build_assistant_message(result))
            for tool_call in result.tool_calls:
                tool_result = await tool_executor.execute(tool_call.name, tool_call.input)
                conversation.append(backend.build_tool_result_message(tool_call, tool_result))

        raise RuntimeError(f"Agentic loop did not converge within {self.settings.agent_max_turns} turns")

    async def _call_ollama(self, messages: list[dict], system: str) -> str:
        """Call Ollama for generation."""
        client = await self._get_ollama_client()
        if not client:
            raise RuntimeError("Ollama is not available")

        ollama_messages = [{"role": "system", "content": system}]
        ollama_messages.extend(messages)

        response = await client.chat(
            messages=ollama_messages,
            temperature=0.7,
        )

        await self._log_conversation(
            messages=messages,
            response=response,
            system=system,
            input_tokens=None,
            output_tokens=None,
            model=self.settings.ollama_model,
        )

        return response

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

        # Medical conditions with ICD-10 and specialty tags
        if conditions_raw:
            lines.extend(["", "## Medical Conditions"])
            for cond in conditions_raw:
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

                notes = self.anonymizer.anonymize_text(getattr(cond, 'notes', None))
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
                if visit.visit_notes:
                    lines.append(f"- Notes: {visit.visit_notes}")
                lines.append("")

        # Additional concerns
        if additional_concerns:
            lines.extend(["", "## Additional Patient Concerns", additional_concerns])

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
