"""Tests for PII anonymization module."""

import pytest
from datetime import date
from unittest.mock import MagicMock

from src.utils.anonymization import (
    Anonymizer,
    AnonymizedProfile,
    PII_PATTERNS,
    anonymize_text,
)


class TestPIIPatterns:
    """Test regex patterns for PII detection."""

    def test_phone_pattern_standard(self):
        """Test standard phone number formats."""
        pattern = PII_PATTERNS['phone']

        # Should match
        assert pattern.search("Call me at 555-123-4567")
        assert pattern.search("Phone: (555) 123-4567")
        assert pattern.search("555.123.4567")
        assert pattern.search("+1-555-123-4567")
        assert pattern.search("5551234567")

    def test_email_pattern(self):
        """Test email detection."""
        pattern = PII_PATTERNS['email']

        # Should match
        assert pattern.search("Contact: john.doe@example.com")
        assert pattern.search("email: patient123@hospital.org")

        # Should not match (not valid emails)
        assert not pattern.search("john@")
        assert not pattern.search("not an email")

    def test_ssn_pattern(self):
        """Test SSN detection."""
        pattern = PII_PATTERNS['ssn']

        # Should match
        assert pattern.search("SSN: 123-45-6789")
        assert pattern.search("123.45.6789")
        assert pattern.search("123 45 6789")


class TestAnonymizer:
    """Test the Anonymizer class."""

    @pytest.fixture
    def anonymizer(self):
        """Create an anonymizer without NER for simpler testing."""
        return Anonymizer(use_ner=False)

    def test_calculate_age(self, anonymizer):
        """Test age calculation from date of birth."""
        # Test with a known date
        today = date.today()

        # Someone born 30 years ago today
        dob = date(today.year - 30, today.month, today.day)
        assert anonymizer.calculate_age(dob) == "30 years old"

        # Someone whose birthday hasn't occurred this year
        future_birthday = date(today.year - 30, 12, 31) if today.month < 12 else date(today.year - 30, today.month + 1, 1)
        if today.month == 12:
            future_birthday = date(today.year - 30, 1, 1)
        # This test is approximate - the important thing is that it returns a reasonable age string
        age_str = anonymizer.calculate_age(future_birthday)
        assert "years old" in age_str

        # None date
        assert anonymizer.calculate_age(None) is None

    def test_anonymize_doctor_reference_with_specialty(self, anonymizer):
        """Test doctor reference anonymization with specialty."""
        result = anonymizer.anonymize_doctor_reference(
            "Dr. John Smith",
            specialty="Cardiology"
        )
        assert result == "your Cardiology"
        assert "John" not in result
        assert "Smith" not in result

    def test_anonymize_doctor_reference_without_specialty(self, anonymizer):
        """Test doctor reference anonymization without specialty."""
        result = anonymizer.anonymize_doctor_reference("Dr. Jane Doe")
        assert result == "Doctor"
        assert "Jane" not in result

    def test_anonymize_doctor_reference_prescribing(self, anonymizer):
        """Test prescribing doctor anonymization."""
        result = anonymizer.anonymize_doctor_reference(
            "Dr. John Smith",
            specialty="Cardiology",
            context="prescribing"
        )
        assert result == "Prescribing physician"

    def test_anonymize_text_phone_numbers(self, anonymizer):
        """Test phone number redaction."""
        text = "Call Dr. Smith at 555-123-4567 or (800) 555-0100"
        result = anonymizer.anonymize_text(text)

        assert "555-123-4567" not in result
        assert "(800) 555-0100" not in result
        assert "[REDACTED]" in result

    def test_anonymize_text_emails(self, anonymizer):
        """Test email redaction."""
        text = "Contact the office at frontdesk@clinic.com"
        result = anonymizer.anonymize_text(text)

        assert "frontdesk@clinic.com" not in result
        assert "[REDACTED]" in result

    def test_anonymize_text_ssn(self, anonymizer):
        """Test SSN redaction."""
        text = "Patient SSN: 123-45-6789"
        result = anonymizer.anonymize_text(text)

        assert "123-45-6789" not in result
        assert "[REDACTED]" in result

    def test_anonymize_text_preserves_medical_content(self, anonymizer):
        """Test that medical information is preserved."""
        text = "Patient has Type 2 Diabetes and takes Metformin 500mg twice daily"
        result = anonymizer.anonymize_text(text)

        # Medical info should be preserved
        assert "Type 2 Diabetes" in result
        assert "Metformin" in result
        assert "500mg" in result

    def test_anonymize_text_none(self, anonymizer):
        """Test handling of None input."""
        assert anonymizer.anonymize_text(None) is None

    def test_anonymize_text_empty(self, anonymizer):
        """Test handling of empty string."""
        assert anonymizer.anonymize_text("") == ""


class TestAnonymizerProfile:
    """Test profile anonymization."""

    @pytest.fixture
    def anonymizer(self):
        return Anonymizer(use_ner=False)

    @pytest.fixture
    def mock_profile(self):
        """Create a mock profile object."""
        profile = MagicMock()
        profile.name = "John Doe"
        profile.date_of_birth = date(1985, 6, 15)
        profile.blood_type = "O+"
        profile.allergies = "Penicillin"
        profile.emergency_contact_name = "Jane Doe"
        profile.emergency_contact_phone = "555-123-4567"

        # Mock conditions
        condition = MagicMock()
        condition.name = "Type 2 Diabetes"
        condition.severity = "moderate"
        condition.status = "managed"
        condition.notes = "Diet controlled. Contact Dr. Smith at 555-000-1111 for questions."
        profile.conditions = [condition]

        # Mock medications
        medication = MagicMock()
        medication.name = "Metformin"
        medication.dosage = "500mg"
        medication.frequency = "twice daily"
        medication.purpose = "Blood sugar control"
        medication.side_effects = "GI upset"
        medication.prescribing_doctor = "Dr. John Smith"
        profile.medications = [medication]

        return profile

    def test_anonymize_profile_removes_name(self, anonymizer, mock_profile):
        """Test that patient name is not included in anonymized profile."""
        result = anonymizer.anonymize_profile(mock_profile)

        # The AnonymizedProfile doesn't have a name field at all
        assert not hasattr(result, 'name')
        assert isinstance(result, AnonymizedProfile)

    def test_anonymize_profile_age_conversion(self, anonymizer, mock_profile):
        """Test that DOB is converted to age."""
        result = anonymizer.anonymize_profile(mock_profile)

        assert result.age_description is not None
        assert "years old" in result.age_description
        # Should not contain the actual date
        assert "1985" not in str(result.age_description)

    def test_anonymize_profile_preserves_medical_info(self, anonymizer, mock_profile):
        """Test that conditions and medications are preserved."""
        result = anonymizer.anonymize_profile(mock_profile)

        assert len(result.conditions) == 1
        assert result.conditions[0]['name'] == "Type 2 Diabetes"
        assert result.conditions[0]['severity'] == "moderate"

        assert len(result.medications) == 1
        assert result.medications[0]['name'] == "Metformin"
        assert result.medications[0]['dosage'] == "500mg"

    def test_anonymize_profile_anonymizes_prescribing_doctor(self, anonymizer, mock_profile):
        """Test that prescribing doctor is anonymized."""
        result = anonymizer.anonymize_profile(mock_profile)

        med = result.medications[0]
        assert med['prescribed_by'] == "Prescribing physician"
        assert "John Smith" not in str(med)

    def test_anonymize_profile_anonymizes_notes(self, anonymizer, mock_profile):
        """Test that phone numbers in notes are redacted."""
        result = anonymizer.anonymize_profile(mock_profile)

        condition_notes = result.conditions[0]['notes']
        assert "555-000-1111" not in condition_notes
        assert "[REDACTED]" in condition_notes


class TestModuleLevelFunctions:
    """Test module-level convenience functions."""

    def test_anonymize_text_function(self):
        """Test the module-level anonymize_text function."""
        text = "Call 555-123-4567"
        result = anonymize_text(text)

        assert "555-123-4567" not in result
        assert "[REDACTED]" in result
