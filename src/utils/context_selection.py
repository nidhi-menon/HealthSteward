"""Intelligent context selection for visit preparation.

This module implements the 4-stage context selection logic per DEC-008:

STAGE 1: Rules-Based Filter (instant, free)
├── ✓ Include: Same doctor's last visit
├── ✓ Include: All PCP/Internal Medicine visits
├── ✓ Include: Related specialties (mapping)
└── ✗ Exclude: Doctors with exclude_from_prep flag

        ↓ If > 5 visits remain

STAGE 2: Local LLM Relevance Scoring (Ollama)
├── Score each visit 1-10 for relevance
├── Keep visits scoring >= 7
└── Fallback: Skip if Ollama unavailable

        ↓

STAGE 3: Token Budget Check
├── If over budget: summarize older visits
└── Use local LLM for summarization

        ↓

STAGE 4: Anonymize + Send to Main LLM
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from src.utils.anonymization import Anonymizer, AnonymizedAppointment


# Specialty mapping: which specialties are relevant to each other
# Primary Care / Internal Medicine is relevant to all
SPECIALTY_MAPPING: dict[str, set[str]] = {
    "Primary Care": {"*"},  # Relevant to all
    "Internal Medicine": {"*"},  # Relevant to all
    "General Practice": {"*"},  # Relevant to all
    "Family Medicine": {"*"},  # Relevant to all

    "Endocrinology": {
        "Cardiology", "Nephrology", "Ophthalmology",
        "Podiatry", "Neurology", "Vascular Surgery",
        "Obstetrics and Gynecology", "Gynecology",
    },
    "Cardiology": {
        "Endocrinology", "Nephrology", "Pulmonology",
        "Vascular Surgery", "Internal Medicine"
    },
    "Oncology": {"*"},  # Relevant to all

    "Nephrology": {
        "Cardiology", "Endocrinology", "Urology"
    },
    "Pulmonology": {
        "Cardiology", "Allergy", "Sleep Medicine"
    },
    "Gastroenterology": {
        "Hepatology", "Oncology", "Nutrition"
    },
    "Neurology": {
        "Psychiatry", "Neurosurgery", "Pain Management"
    },
    "Orthopedics": {
        "Physical Therapy", "Rheumatology", "Pain Management"
    },
    "Rheumatology": {
        "Orthopedics", "Dermatology", "Internal Medicine"
    },
    "Obstetrics and Gynecology": {
        "Endocrinology", "Urology", "Oncology",
    },
    "Gynecology": {
        "Endocrinology", "Urology", "Oncology",
    },
    "Dermatology": {
        "Rheumatology", "Allergy",
    },
}

# Configuration
STAGE_2_THRESHOLD = 5  # Run Stage 2 if more than 5 visits after Stage 1
RELEVANCE_SCORE_CUTOFF = 7  # Keep visits scoring >= 7


@dataclass
class VisitContext:
    """A past visit with its context for prep."""

    appointment_id: str
    doctor_specialty: Optional[str]
    scheduled_date: datetime
    purpose: Optional[str]
    visit_notes: Optional[str]
    relevance_score: Optional[float] = None
    is_same_doctor: bool = False


@dataclass
class ContextSelectionResult:
    """Result of context selection."""

    selected_visits: list[AnonymizedAppointment]
    total_visits_considered: int
    visits_after_stage1: int
    visits_after_stage2: Optional[int]
    used_local_llm: bool
    token_estimate: int


def normalize_specialty(specialty: Optional[str]) -> Optional[str]:
    """Normalize specialty names for comparison.

    Args:
        specialty: Raw specialty name

    Returns:
        Normalized specialty name or None
    """
    if not specialty:
        return None

    # Common normalizations
    specialty = specialty.strip()

    # Map common variations
    variations = {
        "pcp": "Primary Care",
        "primary care physician": "Primary Care",
        "internal med": "Internal Medicine",
        "gi": "Gastroenterology",
        "ent": "Otolaryngology",
        "ob/gyn": "Obstetrics and Gynecology",
        "obgyn": "Obstetrics and Gynecology",
        "gynecology": "Gynecology",
        "ob-gyn": "Obstetrics and Gynecology",
        "gyn": "Gynecology",
        "dermatology": "Dermatology",
        "derm": "Dermatology",
        "endocrinology": "Endocrinology",
        "endo": "Endocrinology",
    }

    lower = specialty.lower()
    if lower in variations:
        return variations[lower]

    return specialty


def is_primary_care(specialty: Optional[str]) -> bool:
    """Check if a specialty is considered primary care.

    Args:
        specialty: The specialty to check

    Returns:
        True if this is a primary care specialty
    """
    if not specialty:
        return False

    normalized = normalize_specialty(specialty)
    if not normalized:
        return False

    primary_care_specialties = {
        "Primary Care",
        "Internal Medicine",
        "General Practice",
        "Family Medicine",
    }

    return normalized in primary_care_specialties


def are_specialties_related(specialty1: Optional[str], specialty2: Optional[str]) -> bool:
    """Check if two specialties are related per the specialty mapping.

    Args:
        specialty1: First specialty
        specialty2: Second specialty

    Returns:
        True if specialties are related
    """
    if not specialty1 or not specialty2:
        return False

    norm1 = normalize_specialty(specialty1)
    norm2 = normalize_specialty(specialty2)

    if not norm1 or not norm2:
        return False

    # Same specialty is always related
    if norm1 == norm2:
        return True

    # Check if either is primary care (related to all)
    if is_primary_care(norm1) or is_primary_care(norm2):
        return True

    # Check mapping
    related1 = SPECIALTY_MAPPING.get(norm1, set())
    related2 = SPECIALTY_MAPPING.get(norm2, set())

    # Check for wildcard (related to all)
    if "*" in related1 or "*" in related2:
        return True

    # Check if specialty2 is in specialty1's related set or vice versa
    return norm2 in related1 or norm1 in related2


class ContextSelector:
    """Selects relevant past visits for visit preparation context."""

    def __init__(
        self,
        anonymizer: Optional[Anonymizer] = None,
        ollama_client=None,
        stage2_threshold: int = STAGE_2_THRESHOLD,
        relevance_cutoff: float = RELEVANCE_SCORE_CUTOFF,
    ):
        """Initialize the context selector.

        Args:
            anonymizer: Anonymizer instance for Stage 4
            ollama_client: Optional Ollama client for Stage 2/3
            stage2_threshold: Number of visits that triggers Stage 2
            relevance_cutoff: Minimum relevance score to keep (1-10)
        """
        self.anonymizer = anonymizer or Anonymizer()
        self.ollama_client = ollama_client
        self.stage2_threshold = stage2_threshold
        self.relevance_cutoff = relevance_cutoff

    def stage1_rules_filter(
        self,
        target_appointment,
        past_appointments: list,
    ) -> list:
        """Stage 1: Apply rules-based filtering.

        Rules:
        - Include: Same doctor's last visit
        - Include: All PCP/Internal Medicine visits
        - Include: Related specialties
        - Exclude: Doctors with exclude_from_prep_context flag

        Args:
            target_appointment: The appointment we're preparing for
            past_appointments: List of past appointments (completed)

        Returns:
            Filtered list of relevant appointments
        """
        target_doctor = target_appointment.doctor
        target_specialty = target_doctor.specialty if target_doctor else None

        relevant = []
        same_doctor_found = False

        # Sort by date descending to get most recent first
        sorted_appointments = sorted(
            past_appointments,
            key=lambda a: a.scheduled_date,
            reverse=True
        )

        for appt in sorted_appointments:
            doctor = appt.doctor
            if not doctor:
                continue

            # Skip if doctor has exclude_from_prep_context flag
            if getattr(doctor, 'exclude_from_prep_context', False):
                continue

            # Include: Same doctor's last visit (only the most recent)
            if doctor.id == target_doctor.id:
                if not same_doctor_found:
                    relevant.append(appt)
                    same_doctor_found = True
                # Skip other visits from same doctor
                continue

            # Include: All PCP/Internal Medicine visits
            if is_primary_care(doctor.specialty):
                relevant.append(appt)
                continue

            # Include: Related specialties
            if are_specialties_related(target_specialty, doctor.specialty):
                relevant.append(appt)
                continue

        return relevant

    async def stage2_llm_scoring(
        self,
        target_appointment,
        candidates: list,
    ) -> list:
        """Stage 2: Use local LLM to score relevance.

        Args:
            target_appointment: The appointment we're preparing for
            candidates: Candidates from Stage 1

        Returns:
            Filtered list with only high-relevance visits
        """
        if not self.ollama_client:
            # Skip Stage 2 if no Ollama client available
            return candidates

        target_specialty = target_appointment.doctor.specialty if target_appointment.doctor else "general"
        target_purpose = target_appointment.purpose or "routine visit"

        scored = []
        for appt in candidates:
            # Build prompt for scoring
            prompt = f"""Rate the relevance of this past visit for preparing for an upcoming {target_specialty} appointment about "{target_purpose}".

Past visit:
- Specialty: {appt.doctor.specialty if appt.doctor else 'Unknown'}
- Purpose: {appt.purpose or 'Not specified'}
- Notes: {appt.visit_notes[:200] if appt.visit_notes else 'None'}

Rate from 1-10 where:
- 10 = Highly relevant (same condition, directly related)
- 7 = Moderately relevant (related health context)
- 4 = Slightly relevant (general health)
- 1 = Not relevant (unrelated)

Respond with just the number."""

            try:
                response = await self.ollama_client.generate(prompt)
                score = float(response.strip())
                if score >= self.relevance_cutoff:
                    scored.append(appt)
            except (ValueError, AttributeError):
                # If scoring fails, include the appointment to be safe
                scored.append(appt)

        return scored

    def stage3_token_budget(
        self,
        appointments: list,
        max_tokens: int = 2000,
    ) -> tuple[list, int]:
        """Stage 3: Apply token budget and summarize if needed.

        Args:
            appointments: Appointments to include
            max_tokens: Maximum token budget

        Returns:
            Tuple of (appointments or summaries, estimated tokens)
        """
        # Rough token estimation (4 chars per token average)
        def estimate_tokens(text: str) -> int:
            return len(text) // 4 if text else 0

        total_tokens = 0
        selected = []

        for appt in appointments:
            visit_text = f"""
Visit with {appt.doctor.specialty if appt.doctor else 'Doctor'}
Date: {appt.scheduled_date}
Purpose: {appt.purpose or 'N/A'}
Notes: {appt.visit_notes or 'N/A'}
"""
            tokens = estimate_tokens(visit_text)

            if total_tokens + tokens <= max_tokens:
                selected.append(appt)
                total_tokens += tokens
            else:
                # Over budget - could summarize here with local LLM
                # For now, just stop adding
                break

        return selected, total_tokens

    async def select_context(
        self,
        target_appointment,
        all_past_appointments: list,
        max_tokens: int = 2000,
    ) -> ContextSelectionResult:
        """Run the full 4-stage context selection pipeline.

        Args:
            target_appointment: The appointment we're preparing for
            all_past_appointments: All past completed appointments
            max_tokens: Maximum token budget for context

        Returns:
            ContextSelectionResult with selected visits
        """
        total_considered = len(all_past_appointments)

        # Stage 1: Rules-based filter
        stage1_results = self.stage1_rules_filter(
            target_appointment,
            all_past_appointments
        )
        visits_after_stage1 = len(stage1_results)

        # Stage 2: LLM scoring (only if > threshold and Ollama available)
        used_local_llm = False
        visits_after_stage2 = None

        if len(stage1_results) > self.stage2_threshold and self.ollama_client:
            stage2_results = await self.stage2_llm_scoring(
                target_appointment,
                stage1_results
            )
            visits_after_stage2 = len(stage2_results)
            used_local_llm = True
        else:
            stage2_results = stage1_results

        # Stage 3: Token budget
        stage3_results, token_estimate = self.stage3_token_budget(
            stage2_results,
            max_tokens
        )

        # Stage 4: Anonymize
        anonymized = [
            self.anonymizer.anonymize_appointment(appt)
            for appt in stage3_results
        ]

        return ContextSelectionResult(
            selected_visits=anonymized,
            total_visits_considered=total_considered,
            visits_after_stage1=visits_after_stage1,
            visits_after_stage2=visits_after_stage2,
            used_local_llm=used_local_llm,
            token_estimate=token_estimate,
        )


# Module-level convenience
_default_selector: Optional[ContextSelector] = None


def get_context_selector() -> ContextSelector:
    """Get or create the default context selector instance."""
    global _default_selector
    if _default_selector is None:
        _default_selector = ContextSelector()
    return _default_selector
