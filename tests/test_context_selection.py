"""Tests for intelligent context selection module."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, AsyncMock

from src.utils.context_selection import (
    ContextSelector,
    normalize_specialty,
    is_primary_care,
    are_specialties_related,
    SPECIALTY_MAPPING,
    STAGE_2_THRESHOLD,
)


class TestSpecialtyNormalization:
    """Test specialty normalization functions."""

    def test_normalize_specialty_variations(self):
        """Test that specialty variations are normalized."""
        assert normalize_specialty("pcp") == "Primary Care"
        assert normalize_specialty("PCP") == "Primary Care"
        assert normalize_specialty("internal med") == "Internal Medicine"
        assert normalize_specialty("GI") == "Gastroenterology"
        assert normalize_specialty("ob/gyn") == "Obstetrics and Gynecology"

    def test_normalize_specialty_passthrough(self):
        """Test that unknown specialties are passed through."""
        assert normalize_specialty("Cardiology") == "Cardiology"
        assert normalize_specialty("Dermatology") == "Dermatology"

    def test_normalize_specialty_none(self):
        """Test handling of None."""
        assert normalize_specialty(None) is None

    def test_normalize_specialty_strips_whitespace(self):
        """Test that whitespace is stripped."""
        assert normalize_specialty("  Cardiology  ") == "Cardiology"


class TestIsPrimaryCare:
    """Test primary care detection."""

    def test_primary_care_specialties(self):
        """Test that primary care specialties are detected."""
        assert is_primary_care("Primary Care")
        assert is_primary_care("Internal Medicine")
        assert is_primary_care("General Practice")
        assert is_primary_care("Family Medicine")
        assert is_primary_care("pcp")  # Via normalization

    def test_non_primary_care(self):
        """Test that specialists are not marked as primary care."""
        assert not is_primary_care("Cardiology")
        assert not is_primary_care("Dermatology")
        assert not is_primary_care("Oncology")

    def test_none_specialty(self):
        """Test handling of None."""
        assert not is_primary_care(None)


class TestSpecialtyRelations:
    """Test specialty relationship detection."""

    def test_same_specialty_related(self):
        """Test that same specialty is always related."""
        assert are_specialties_related("Cardiology", "Cardiology")
        assert are_specialties_related("Dermatology", "Dermatology")

    def test_primary_care_related_to_all(self):
        """Test that primary care is related to all specialties."""
        assert are_specialties_related("Primary Care", "Cardiology")
        assert are_specialties_related("Cardiology", "Internal Medicine")
        assert are_specialties_related("pcp", "Oncology")

    def test_specialty_mapping_relations(self):
        """Test specific specialty relationships from mapping."""
        # Endocrinology → Cardiology
        assert are_specialties_related("Endocrinology", "Cardiology")
        assert are_specialties_related("Cardiology", "Endocrinology")

        # Endocrinology → Nephrology
        assert are_specialties_related("Endocrinology", "Nephrology")

    def test_unrelated_specialties(self):
        """Test that unrelated specialties return False."""
        # These are not in each other's related sets
        assert not are_specialties_related("Dermatology", "Gastroenterology")
        assert not are_specialties_related("Podiatry", "Pulmonology")

    def test_oncology_related_to_all(self):
        """Test that oncology is related to all (marked with *)."""
        assert are_specialties_related("Oncology", "Dermatology")
        assert are_specialties_related("Oncology", "Cardiology")

    def test_none_handling(self):
        """Test handling of None values."""
        assert not are_specialties_related(None, "Cardiology")
        assert not are_specialties_related("Cardiology", None)
        assert not are_specialties_related(None, None)


class TestContextSelector:
    """Test the ContextSelector class."""

    @pytest.fixture
    def selector(self):
        """Create a context selector without Ollama."""
        return ContextSelector(ollama_client=None)

    @pytest.fixture
    def mock_doctor(self):
        """Create a mock doctor factory."""
        def _create(name="Dr. Test", specialty="Cardiology", exclude=False, id="doc-1"):
            doctor = MagicMock()
            doctor.id = id
            doctor.name = name
            doctor.specialty = specialty
            doctor.clinic = "Test Clinic"
            doctor.exclude_from_prep_context = exclude
            return doctor
        return _create

    @pytest.fixture
    def mock_appointment(self, mock_doctor):
        """Create a mock appointment factory."""
        def _create(doctor=None, days_ago=0, status="completed", visit_notes=None):
            appt = MagicMock()
            appt.id = f"appt-{days_ago}"
            appt.doctor = doctor or mock_doctor()
            appt.scheduled_date = datetime.now() - timedelta(days=days_ago)
            appt.status = status
            appt.purpose = "Checkup"
            appt.visit_notes = visit_notes
            return appt
        return _create

    def test_stage1_includes_same_doctor(self, selector, mock_doctor, mock_appointment):
        """Test that same doctor's last visit is included."""
        doctor = mock_doctor(id="doc-1", specialty="Cardiology")
        target = mock_appointment(doctor=doctor, days_ago=0, status="scheduled")

        past_visits = [
            mock_appointment(doctor=doctor, days_ago=30),
            mock_appointment(doctor=doctor, days_ago=60),
        ]

        result = selector.stage1_rules_filter(target, past_visits)

        # Should include only the most recent visit from same doctor
        assert len(result) == 1
        assert result[0].id == "appt-30"

    def test_stage1_includes_primary_care(self, selector, mock_doctor, mock_appointment):
        """Test that primary care visits are always included."""
        target_doctor = mock_doctor(id="doc-1", specialty="Cardiology")
        target = mock_appointment(doctor=target_doctor, status="scheduled")

        pcp_doctor = mock_doctor(id="doc-2", specialty="Primary Care")
        past_visits = [
            mock_appointment(doctor=pcp_doctor, days_ago=30),
            mock_appointment(doctor=pcp_doctor, days_ago=60),
        ]

        result = selector.stage1_rules_filter(target, past_visits)

        # Should include all PCP visits
        assert len(result) == 2

    def test_stage1_includes_related_specialties(self, selector, mock_doctor, mock_appointment):
        """Test that related specialties are included."""
        # Target is Cardiology
        target_doctor = mock_doctor(id="doc-1", specialty="Cardiology")
        target = mock_appointment(doctor=target_doctor, status="scheduled")

        # Endocrinology is related to Cardiology
        endo_doctor = mock_doctor(id="doc-2", specialty="Endocrinology")
        past_visits = [
            mock_appointment(doctor=endo_doctor, days_ago=30),
        ]

        result = selector.stage1_rules_filter(target, past_visits)

        assert len(result) == 1

    def test_stage1_excludes_flagged_doctors(self, selector, mock_doctor, mock_appointment):
        """Test that doctors with exclude_from_prep_context are excluded."""
        target_doctor = mock_doctor(id="doc-1", specialty="Cardiology")
        target = mock_appointment(doctor=target_doctor, status="scheduled")

        # This doctor is excluded (e.g., sensitive specialty)
        excluded_doctor = mock_doctor(id="doc-2", specialty="Primary Care", exclude=True)
        past_visits = [
            mock_appointment(doctor=excluded_doctor, days_ago=30),
        ]

        result = selector.stage1_rules_filter(target, past_visits)

        # Should not include the excluded doctor's visit
        assert len(result) == 0

    def test_stage1_excludes_unrelated_specialties(self, selector, mock_doctor, mock_appointment):
        """Test that unrelated specialties are excluded."""
        target_doctor = mock_doctor(id="doc-1", specialty="Cardiology")
        target = mock_appointment(doctor=target_doctor, status="scheduled")

        # Dermatology is not related to Cardiology
        derm_doctor = mock_doctor(id="doc-2", specialty="Dermatology")
        past_visits = [
            mock_appointment(doctor=derm_doctor, days_ago=30),
        ]

        result = selector.stage1_rules_filter(target, past_visits)

        assert len(result) == 0

    def test_stage3_token_budget(self, selector, mock_doctor, mock_appointment):
        """Test token budget limiting."""
        doctor = mock_doctor()

        # Create many appointments with long visit notes
        appointments = []
        for i in range(10):
            appt = mock_appointment(doctor=doctor, days_ago=i*7)
            appt.visit_notes = "A" * 1000  # Long notes
            appointments.append(appt)

        # With a small token budget, should limit results
        result, tokens, dropped = selector.stage3_token_budget(appointments, max_tokens=500)

        # Should have fewer appointments than input
        assert len(result) < len(appointments)
        assert tokens <= 500
        # Every appointment not selected should be counted as dropped, not silently lost
        assert dropped == len(appointments) - len(result)

    def test_stage3_continues_past_oversized_visit(self, selector, mock_doctor, mock_appointment):
        """A visit too big to fit shouldn't stop smaller later visits from being packed."""
        doctor = mock_doctor()

        huge = mock_appointment(doctor=doctor, days_ago=0)
        huge.visit_notes = "A" * 4000  # Won't fit in the budget below

        small = mock_appointment(doctor=doctor, days_ago=7)
        small.visit_notes = "short note"

        # huge is first in recency order but doesn't fit — small should still be packed
        result, tokens, dropped = selector.stage3_token_budget([huge, small], max_tokens=100)

        assert small.id in [a.id for a in result]
        assert dropped == 1

    def test_stage3_prioritizes_by_score(self, selector, mock_doctor, mock_appointment):
        """Higher-scored visits should be packed before lower-scored ones, regardless of recency order."""
        doctor = mock_doctor()

        low_score_recent = mock_appointment(doctor=doctor, days_ago=0)
        low_score_recent.visit_notes = "A" * 300

        high_score_older = mock_appointment(doctor=doctor, days_ago=30)
        high_score_older.visit_notes = "A" * 300

        score_map = {low_score_recent.id: 3.0, high_score_older.id: 9.0}

        # Budget only fits one of the two
        result, tokens, dropped = selector.stage3_token_budget(
            [low_score_recent, high_score_older], max_tokens=100, score_map=score_map,
        )

        assert len(result) == 1
        assert result[0].id == high_score_older.id
        assert dropped == 1

    def test_stage3_pinned_always_packed_first(self, selector, mock_doctor, mock_appointment):
        """A pinned visit should survive budget packing even with a low or missing score."""
        doctor = mock_doctor()

        pinned_low_score = mock_appointment(doctor=doctor, days_ago=0)
        pinned_low_score.visit_notes = "A" * 300

        unpinned_high_score = mock_appointment(doctor=doctor, days_ago=30)
        unpinned_high_score.visit_notes = "A" * 300

        score_map = {pinned_low_score.id: 1.0, unpinned_high_score.id: 9.0}

        result, tokens, dropped = selector.stage3_token_budget(
            [pinned_low_score, unpinned_high_score],
            max_tokens=100,
            score_map=score_map,
            pinned_ids={pinned_low_score.id},
        )

        assert len(result) == 1
        assert result[0].id == pinned_low_score.id
        assert dropped == 1


class TestContextSelectorAsync:
    """Test async methods of ContextSelector."""

    @pytest.fixture
    def mock_anonymizer(self):
        """Create a mock anonymizer."""
        anonymizer = MagicMock()
        anonymizer.anonymize_appointment = MagicMock(return_value=MagicMock())
        return anonymizer

    @pytest.fixture
    def selector(self, mock_anonymizer):
        """Create a context selector with mock anonymizer."""
        return ContextSelector(anonymizer=mock_anonymizer)

    @pytest.mark.asyncio
    async def test_select_context_returns_result(self, selector):
        """Test that select_context returns a proper result object."""
        target = MagicMock()
        target.doctor = MagicMock()
        target.doctor.id = "doc-1"
        target.doctor.specialty = "Cardiology"

        result = await selector.select_context(target, [])

        assert result.total_visits_considered == 0
        assert result.visits_after_stage1 == 0
        assert result.used_local_llm is False

    @pytest.mark.asyncio
    async def test_select_context_skips_stage2_below_threshold(self, selector):
        """Test that Stage 2 is skipped when below threshold."""
        target = MagicMock()
        target.doctor = MagicMock()
        target.doctor.id = "doc-1"
        target.doctor.specialty = "Cardiology"

        # Create fewer appointments than threshold
        past = []
        for i in range(STAGE_2_THRESHOLD - 1):
            appt = MagicMock()
            appt.doctor = MagicMock()
            appt.doctor.id = f"doc-{i}"
            appt.doctor.specialty = "Primary Care"
            appt.doctor.exclude_from_prep_context = False
            appt.scheduled_date = datetime.now() - timedelta(days=i*7)
            appt.visit_notes = None
            appt.purpose = None
            past.append(appt)

        result = await selector.select_context(target, past)

        # Stage 2 should not have been used
        assert result.visits_after_stage2 is None
        assert result.used_local_llm is False

    def _make_past_appointment(self, doctor_id, days_ago, specialty="Primary Care"):
        appt = MagicMock()
        appt.id = f"appt-{doctor_id}-{days_ago}"
        appt.doctor = MagicMock()
        appt.doctor.id = doctor_id
        appt.doctor.specialty = specialty
        appt.doctor.exclude_from_prep_context = False
        appt.scheduled_date = datetime.now() - timedelta(days=days_ago)
        appt.visit_notes = "short note"
        appt.purpose = None
        return appt

    @pytest.mark.asyncio
    async def test_select_context_caps_stage2_candidates(self, mock_anonymizer):
        """Candidates beyond stage2_max_candidates shouldn't reach the LLM scoring call."""
        ollama_client = MagicMock()
        ollama_client.generate = AsyncMock(return_value="9")  # everyone scores high

        selector = ContextSelector(
            anonymizer=mock_anonymizer,
            ollama_client=ollama_client,
            stage2_max_candidates=3,
        )

        target = MagicMock()
        target.doctor = MagicMock()
        target.doctor.id = "target-doc"  # no same-doctor visits in `past`, so nothing is pinned
        target.doctor.specialty = "Cardiology"

        # All Primary Care (always pass Stage 1), more than the cap of 3
        past = [self._make_past_appointment(f"doc-{i}", days_ago=i) for i in range(6)]

        result = await selector.select_context(target, past)

        assert result.visits_dropped_stage2_cap == 3
        assert ollama_client.generate.call_count == 3

    @pytest.mark.asyncio
    async def test_select_context_pinned_survives_cap_and_low_score(self, mock_anonymizer):
        """Same-doctor's last visit should survive both the Stage 2 cap and a low relevance score."""
        ollama_client = MagicMock()
        ollama_client.generate = AsyncMock(return_value="1")  # everyone scores low

        selector = ContextSelector(
            anonymizer=mock_anonymizer,
            ollama_client=ollama_client,
            stage2_max_candidates=2,
            relevance_cutoff=7.0,
        )

        target = MagicMock()
        target.doctor = MagicMock()
        target.doctor.id = "target-doc"
        target.doctor.specialty = "Cardiology"

        # Same doctor as target, oldest of the bunch — would lose a pure-recency cap
        pinned = self._make_past_appointment("target-doc", days_ago=400, specialty="Cardiology")
        # Plenty of unrelated-but-included Primary Care visits, more recent
        others = [self._make_past_appointment(f"doc-{i}", days_ago=i) for i in range(1, 6)]

        result = await selector.select_context(target, [pinned] + others)

        # Everyone scores "1" (below the 7.0 cutoff), but the pinned visit must survive anyway
        anonymized_ids = {
            call.args[0].id for call in mock_anonymizer.anonymize_appointment.call_args_list
        }
        assert pinned.id in anonymized_ids
