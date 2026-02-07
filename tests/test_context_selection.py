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
        result, tokens = selector.stage3_token_budget(appointments, max_tokens=500)

        # Should have fewer appointments than input
        assert len(result) < len(appointments)
        assert tokens <= 500


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
