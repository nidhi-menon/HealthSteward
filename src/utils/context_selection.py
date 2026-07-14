"""Intelligent context selection for visit preparation.

This module implements the 4-stage context selection logic per DEC-008:

STAGE 1: Rules-Based Filter (instant, free)
├── ✓ Include: Same doctor's last visit (pinned — never dropped by Stage 2's
│     candidate cap or relevance filter, or by Stage 3's budget packing)
├── ✓ Include: All PCP/Internal Medicine visits
├── ✓ Include: Related specialties (mapping)
└── ✗ Exclude: Doctors with exclude_from_prep flag

        ↓ If > 5 visits remain

STAGE 2: Local LLM Relevance Scoring (Ollama)
├── Candidates beyond context_stage2_max_candidates are capped before
│   scoring (cost control — one sequential, unbatched Ollama call per
│   candidate; see issue #56), pinned candidate exempted from the cap
├── Score each remaining visit 1-10 for relevance
├── Keep visits scoring >= 7 (pinned visit always kept regardless of score)
└── Fallback: Skip entirely if Ollama unavailable or below stage2_threshold

        ↓

STAGE 3: Token Budget Check
├── Packs visits by priority (Stage 2 relevance score, pinned visit always
│   first; recency as a fallback/tiebreaker when no score is available)
├── Visits that don't fit are dropped, not summarized or truncated — the
│   count of dropped visits is surfaced on ContextSelectionResult and
│   logged, not silent. Summarization was designed but never implemented
│   (see issue #56); this stage has always been pure truncation.
└── Continues past an over-budget visit instead of stopping, so a smaller
    later visit can still be packed in

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
# Provisional — not measured against real per-call Ollama latency. See issue #56.
STAGE_2_MAX_CANDIDATES = 15


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
    # Visibility into visits Stage 2/3 dropped, rather than leaving it silent —
    # see issue #56 for the follow-up on grounding/reducing these.
    visits_dropped_stage2_cap: int = 0
    visits_dropped_stage3_budget: int = 0


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
        stage2_max_candidates: int = STAGE_2_MAX_CANDIDATES,
    ):
        """Initialize the context selector.

        Args:
            anonymizer: Anonymizer instance for Stage 4
            ollama_client: Optional Ollama client for Stage 2/3
            stage2_threshold: Number of visits that triggers Stage 2
            relevance_cutoff: Minimum relevance score to keep (1-10)
            stage2_max_candidates: Cap on candidates sent to Stage 2's
                sequential, unbatched scoring calls (cost control, not a
                relevance judgment — see issue #56)
        """
        self.anonymizer = anonymizer or Anonymizer()
        self.ollama_client = ollama_client
        self.stage2_threshold = stage2_threshold
        self.relevance_cutoff = relevance_cutoff
        self.stage2_max_candidates = stage2_max_candidates

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
        pinned_ids: Optional[set] = None,
    ) -> list[tuple]:
        """Stage 2: Use local LLM to score relevance.

        Args:
            target_appointment: The appointment we're preparing for
            candidates: Candidates to score (already capped by the caller —
                see select_context — this method doesn't cap on its own)
            pinned_ids: Appointment ids that must survive regardless of
                score (e.g. Stage 1's same-doctor pin). Still scored, so
                Stage 3 has a real priority to sort by, but never dropped
                by the relevance_cutoff filter here.

        Returns:
            List of (appointment, score) pairs for visits that passed the
            relevance cutoff (or are pinned). score is None if Stage 2 was
            skipped for that candidate — callers shouldn't see that here
            since this method either scores everything it's given or (if
            no Ollama client) returns everything unscored.
        """
        pinned_ids = pinned_ids or set()

        if not self.ollama_client:
            # Skip Stage 2 if no Ollama client available
            return [(appt, None) for appt in candidates]

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

            is_pinned = appt.id in pinned_ids
            try:
                response = await self.ollama_client.generate(prompt)
                score = float(response.strip())
            except (ValueError, AttributeError):
                # If scoring fails, include the appointment to be safe —
                # borderline score, not top priority, not dropped either.
                score = self.relevance_cutoff

            if is_pinned or score >= self.relevance_cutoff:
                scored.append((appt, score))

        return scored

    def stage3_token_budget(
        self,
        appointments: list,
        max_tokens: int = 2000,
        score_map: Optional[dict] = None,
        pinned_ids: Optional[set] = None,
    ) -> tuple[list, int, int]:
        """Stage 3: Apply token budget, packing by priority.

        Does NOT summarize — visits that don't fit are dropped, not
        shortened. (The module docstring/this method's own prior comment
        both claimed summarization would happen "for now" — it never was
        implemented; see issue #56.) What this does do: pack by priority
        (pinned first, then Stage 2 relevance score, then recency as a
        tiebreaker/fallback) and keep evaluating past the first visit that
        doesn't fit, so a smaller later one can still be packed in — the
        previous version stopped at the first miss regardless of order.

        Args:
            appointments: Appointments to include (in their incoming order —
                used as the recency tiebreaker/fallback when no score exists)
            max_tokens: Maximum token budget
            score_map: Optional {appointment.id: score} from Stage 2. Missing
                entries sort after scored ones, in their original order.
            pinned_ids: Appointment ids that must be packed first regardless
                of score (e.g. Stage 1's same-doctor pin) — protects them
                from being dropped by budget the same way Stage 2's cap and
                relevance filter already protect them.

        Returns:
            Tuple of (selected appointments, estimated tokens used, count of
            visits that didn't fit and were dropped).
        """
        score_map = score_map or {}
        pinned_ids = pinned_ids or set()

        # Rough token estimation (4 chars per token average)
        def estimate_tokens(text: str) -> int:
            return len(text) // 4 if text else 0

        # Priority order: pinned first, then by Stage 2 score (descending),
        # then original/recency order as a stable tiebreaker for ties or
        # visits with no score at all (e.g. Stage 2 was skipped entirely).
        def priority_key(indexed_appt: tuple) -> tuple:
            index, appt = indexed_appt
            is_pinned = appt.id in pinned_ids
            score = score_map.get(appt.id)
            return (
                0 if is_pinned else 1,
                -(score if score is not None else float("-inf")),
                index,
            )

        ordered = [appt for _, appt in sorted(enumerate(appointments), key=priority_key)]

        total_tokens = 0
        selected = []
        dropped = 0

        for appt in ordered:
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
                # Doesn't fit — drop it, but keep evaluating the rest of the
                # priority order instead of stopping here (a later, smaller
                # visit may still fit).
                dropped += 1

        return selected, total_tokens, dropped

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

        # Identify the pinned same-doctor visit (if any) from Stage 1's output —
        # at most one, since stage1_rules_filter only ever keeps the most recent
        # visit per same doctor. Tracked by id so it survives Stage 2's cap and
        # relevance filter, and Stage 3's budget packing, unconditionally.
        pinned_ids: set = set()
        target_doctor = getattr(target_appointment, "doctor", None)
        if target_doctor:
            for appt in stage1_results:
                if appt.doctor and appt.doctor.id == target_doctor.id:
                    pinned_ids.add(appt.id)
                    break

        # Stage 2: LLM scoring (only if > threshold and Ollama available)
        used_local_llm = False
        visits_after_stage2 = None
        visits_dropped_stage2_cap = 0
        score_map: dict = {}

        if len(stage1_results) > self.stage2_threshold and self.ollama_client:
            pinned = [a for a in stage1_results if a.id in pinned_ids]
            rest = [a for a in stage1_results if a.id not in pinned_ids]

            # Cap candidates sent to Stage 2's sequential, unbatched scoring
            # calls (cost control, not a relevance judgment — issue #56).
            # The pinned visit doesn't count against the cap.
            room = max(self.stage2_max_candidates - len(pinned), 0)
            capped_rest = rest[:room]
            visits_dropped_stage2_cap = len(rest) - len(capped_rest)

            scored_pairs = await self.stage2_llm_scoring(
                target_appointment,
                pinned + capped_rest,
                pinned_ids=pinned_ids,
            )
            stage2_results = [appt for appt, _ in scored_pairs]
            score_map = {appt.id: score for appt, score in scored_pairs if score is not None}
            visits_after_stage2 = len(stage2_results)
            used_local_llm = True
        else:
            stage2_results = stage1_results

        # Stage 3: Token budget, priority-packed (pinned, then score, then recency)
        stage3_results, token_estimate, visits_dropped_stage3_budget = self.stage3_token_budget(
            stage2_results,
            max_tokens,
            score_map=score_map,
            pinned_ids=pinned_ids,
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
            visits_dropped_stage2_cap=visits_dropped_stage2_cap,
            visits_dropped_stage3_budget=visits_dropped_stage3_budget,
        )


# Module-level convenience
_default_selector: Optional[ContextSelector] = None


def get_context_selector() -> ContextSelector:
    """Get or create the default context selector instance."""
    global _default_selector
    if _default_selector is None:
        _default_selector = ContextSelector()
    return _default_selector
