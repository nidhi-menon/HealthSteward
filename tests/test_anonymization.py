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


class TestHardenedPIIPatterns:
    """Coverage for the PII shapes added in issue #73.

    The original 5-pattern list (phone/email/SSN/date/simplified-address) let a
    range of real-world PII shapes through unredacted. Each case below is a shape
    that leaked before the pattern list was hardened; the negative cases guard
    the other direction — this runs on clinical free text, so redacting dosages,
    vitals, or lab values would be its own kind of failure.
    """

    @pytest.fixture
    def anonymizer(self):
        return Anonymizer(use_ner=False)

    def _redacted(self, anonymizer, text):
        return anonymizer.anonymize_text(text)

    # --- International phone numbers ---

    @pytest.mark.parametrize("text,leaked", [
        ("Call +44 20 7946 0958", "+44 20 7946 0958"),
        ("Reach me on +91 98765 43210", "+91 98765 43210"),
        ("Clinic line +33 1 42 68 53 00", "+33 1 42 68 53 00"),
        ("Office: +81-3-1234-5678", "+81-3-1234-5678"),
        ("+44 (0)20 7946 0958", "+44 (0)20 7946 0958"),
    ])
    def test_international_phone_redacted_whole(self, anonymizer, text, leaked):
        """International numbers must be redacted entirely.

        The pre-existing `phone` pattern matched only the trailing 10 digits of
        these, leaving the country and area code (e.g. "+44 20 7") in place —
        a partial redaction is still a leak.
        """
        result = self._redacted(anonymizer, text)
        assert "[REDACTED]" in result
        assert leaked not in result
        # No stray digits survive from the number itself
        assert not any(ch.isdigit() for ch in result)

    # --- PO boxes ---

    @pytest.mark.parametrize("text", [
        "Mail to P.O. Box 1234",
        "PO Box 567, Springfield",
        "Post Office Box 89",
        "p.o. box 42",
    ])
    def test_po_box_redacted(self, anonymizer, text):
        result = self._redacted(anonymizer, text)
        assert "[REDACTED]" in result
        assert "Box" not in result

    # --- Street addresses: widened suffixes and unit designators ---

    @pytest.mark.parametrize("text", [
        "742 Evergreen Terrace",
        "742 Evergreen Ter",
        "12 Oak Circle",
        "900 Bay Parkway",
        "900 Bay Pkwy",
        "45 Country Highway",
        "88 Cedar Trail",
        "5 Union Square",
        "17 Mill Crossing",
        "3 Harbor Plaza",
    ])
    def test_widened_street_suffixes_redacted(self, anonymizer, text):
        """Suffixes beyond the original St/Ave/Blvd/Rd/Dr/Ln/Way/Ct/Pl list."""
        result = self._redacted(anonymizer, text)
        assert result == "[REDACTED]"

    @pytest.mark.parametrize("text", [
        "742 Evergreen Terrace Apt 4B",
        "123 Main St Unit 5",
        "50 Elm Road Suite 200",
        "9 Pine Lane, Apt 12",
        "9 Pine Lane #12",
    ])
    def test_address_unit_designator_redacted_with_address(self, anonymizer, text):
        """Apartment/unit numbers must be redacted along with the street address,
        not left dangling after it."""
        result = self._redacted(anonymizer, text)
        assert result == "[REDACTED]"

    def test_original_address_suffixes_still_work(self, anonymizer):
        """Regression guard: widening the suffix list must not break the
        suffixes the original pattern already covered."""
        for text in ["123 Main St", "45 Oak Avenue", "9 Elm Blvd", "77 Sunset Drive"]:
            assert self._redacted(anonymizer, text) == "[REDACTED]"

    # --- ZIP codes ---

    def test_zip_plus_four_redacted_whole(self, anonymizer):
        """ZIP+4 must redact whole. The `phone` pattern's 7-digit branch used to
        consume "103-1234" and leave a bare "94" behind."""
        result = self._redacted(anonymizer, "Lives at 94103-1234")
        assert result == "Lives at [REDACTED]"

    def test_state_qualified_zip_redacted(self, anonymizer):
        result = self._redacted(anonymizer, "Springfield, IL 62704")
        assert "62704" not in result
        assert "[REDACTED]" in result

    def test_bare_five_digit_number_not_redacted(self, anonymizer):
        """A bare 5-digit number is not treated as a ZIP — indistinguishable
        from an ordinary number in clinical text."""
        result = self._redacted(anonymizer, "Step count averaged 12500 per day")
        assert "12500" in result

    # --- Dates ---

    @pytest.mark.parametrize("text,leaked", [
        ("DOB 15/06/1985", "15/06/1985"),        # day-first ordering
        ("DOB 06/15/85", "06/15/85"),            # 2-digit year
        ("DOB: 1985-06-15", "1985-06-15"),       # ISO-8601
        ("Born June 15, 1985", "June 15, 1985"),  # written, month-first
        ("Born 15 June 1985", "15 June 1985"),    # written, day-first
        ("Born Jun 15, 1985", "Jun 15, 1985"),    # abbreviated month
    ])
    def test_additional_date_formats_redacted(self, anonymizer, text, leaked):
        result = self._redacted(anonymizer, text)
        assert "[REDACTED]" in result
        assert leaked not in result

    def test_original_date_format_still_redacted(self, anonymizer):
        """Regression guard for the original MM/DD/YYYY pattern."""
        result = self._redacted(anonymizer, "DOB 06/15/1985")
        assert "06/15/1985" not in result
        assert "[REDACTED]" in result

    def test_month_and_year_without_day_preserved(self, anonymizer):
        """A bare month+year is scheduling context, not a birthdate — keeping it
        is what makes the anonymized text still useful for visit prep."""
        result = self._redacted(anonymizer, "Follow up in January 2026")
        assert "January 2026" in result

    # --- Label-anchored identifiers: MRN ---

    @pytest.mark.parametrize("text,label", [
        ("MRN: 12345678", "MRN:"),
        ("MRN 004512", "MRN"),
        ("Medical Record Number: 987654", "Medical Record Number:"),
        ("MRN: A00123456", "MRN:"),
        ("Chart Number: 55501234", "Chart Number:"),
    ])
    def test_mrn_value_redacted_label_kept(self, anonymizer, text, label):
        """The identifier value is redacted but its label survives, so the
        anonymized text still reads as "MRN: [REDACTED]" — the LLM keeps the
        clinical context without receiving the identifier."""
        result = self._redacted(anonymizer, text)
        assert result.startswith(label)
        assert "[REDACTED]" in result
        assert not any(ch.isdigit() for ch in result)

    # --- Label-anchored identifiers: insurance ---

    @pytest.mark.parametrize("text,label", [
        ("Member ID: XZY123456789", "Member ID:"),
        ("Policy #: ABC-12345678", "Policy #:"),
        ("Group Number: 0012345", "Group Number:"),
        ("Subscriber ID 998877665", "Subscriber ID"),
    ])
    def test_insurance_id_value_redacted_label_kept(self, anonymizer, text, label):
        result = self._redacted(anonymizer, text)
        assert result.startswith(label)
        assert "[REDACTED]" in result

    def test_labeled_patterns_do_not_match_lowercase_prose(self, anonymizer):
        """The insurance-ID value is matched case-sensitively on purpose. Matching
        it case-insensitively would let ordinary prose after one of these labels
        ("Plan: increase dose") read as an identifier and get redacted."""
        result = self._redacted(anonymizer, "Plan: increase dose gradually")
        assert "increase dose gradually" in result
        assert "[REDACTED]" not in result

    def test_unlabeled_numbers_not_treated_as_identifiers(self, anonymizer):
        """MRN/insurance patterns are label-anchored by design — an unanchored
        "long digit run" pattern would redact lab values and dosages."""
        result = self._redacted(anonymizer, "Platelet count 250000 and ferritin 45")
        assert "250000" in result
        assert "45" in result

    # --- Negative cases: clinical content must survive ---

    @pytest.mark.parametrize("text", [
        "Metformin 500mg twice daily",
        "Lisinopril 10 mg daily",
        "BP 120/80",
        "A1C was 7.2",
        "Vitamin D 32 ng/mL",
        "Type 2 Diabetes, managed",
        "Diagnosis code E11.9",
        "Symptoms for 3 years",
        "Appointment at 10:30",
        "Weight 185 lbs",
        "LDL 130, HDL 55, total 210",
        "Titrate 25-50 mg",
        "Fasting glucose 95-110 range",
        "Take 1/2 tablet in the morning",
    ])
    def test_clinical_content_not_redacted(self, anonymizer, text):
        """Over-redaction is a real failure mode for the widened patterns: dose
        ranges, ratios, and fractions all look date- or identifier-shaped."""
        result = self._redacted(anonymizer, text)
        assert result == text

    def test_mixed_note_redacts_pii_and_keeps_medicine(self, anonymizer):
        """End-to-end shape of a realistic AVS-style note."""
        text = (
            "Patient reports fatigue. Continue Metformin 500mg twice daily. "
            "MRN: 12345678. Call the office at +44 20 7946 0958 or write to "
            "742 Evergreen Terrace Apt 4B. DOB 15/06/1985."
        )
        result = anonymizer.anonymize_text(text)

        # PII gone
        assert "12345678" not in result
        assert "+44 20 7946 0958" not in result
        assert "742 Evergreen Terrace" not in result
        assert "15/06/1985" not in result
        # Medicine kept
        assert "Metformin 500mg twice daily" in result
        assert "fatigue" in result


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

    def test_anonymize_doctor_includes_anonymized_notes(self, anonymizer):
        """Regression test for issue #51: Doctor.notes must reach
        AnonymizedDoctor, anonymized the same way as every other free-text
        field (e.g. Condition.notes, see test_anonymize_profile_anonymizes_notes).
        """
        doctor = MagicMock()
        doctor.name = "Dr. Sarah Johnson"
        doctor.specialty = "Endocrinology"
        doctor.clinic = "City Medical Center"
        doctor.notes = "Prefers phone follow-ups. Call 555-000-1111 to reach the office."

        result = anonymizer.anonymize_doctor(doctor)

        assert result.notes is not None
        assert "555-000-1111" not in result.notes
        assert "[REDACTED]" in result.notes
        assert "phone follow-ups" in result.notes

    def test_anonymize_doctor_with_no_notes(self, anonymizer):
        """None notes should stay None, not become an empty/placeholder string."""
        doctor = MagicMock()
        doctor.name = "Dr. Sarah Johnson"
        doctor.specialty = "Endocrinology"
        doctor.clinic = "City Medical Center"
        doctor.notes = None

        result = anonymizer.anonymize_doctor(doctor)

        assert result.notes is None

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


class TestAnonymizeAppointment:
    """Test anonymize_appointment, including prep_notes exposure."""

    @pytest.fixture
    def anonymizer(self):
        return Anonymizer(use_ner=False)

    def test_anonymize_appointment_includes_prep_notes(self, anonymizer):
        """prep_notes (pre-visit concerns/questions) must be anonymized and
        included, not silently dropped alongside visit_notes."""
        doctor = MagicMock()
        doctor.name = "Dr. Smith"
        doctor.specialty = "Endocrinology"
        doctor.clinic = "Metro Health"
        doctor.notes = None

        appointment = MagicMock()
        appointment.doctor = doctor
        appointment.scheduled_date = date(2024, 3, 1)
        appointment.purpose = "Follow-up"
        appointment.prep_notes = "Ask about fatigue, call 555-123-4567 if urgent"
        appointment.visit_notes = "Discussed dosage increase"

        result = anonymizer.anonymize_appointment(appointment)

        assert result.prep_notes is not None
        assert "Ask about fatigue" in result.prep_notes
        assert "555-123-4567" not in result.prep_notes
        assert "[REDACTED]" in result.prep_notes
        assert result.visit_notes == "Discussed dosage increase"


class TestModuleLevelFunctions:
    """Test module-level convenience functions."""

    def test_anonymize_text_function(self):
        """Test the module-level anonymize_text function."""
        text = "Call 555-123-4567"
        result = anonymize_text(text)

        assert "555-123-4567" not in result
        assert "[REDACTED]" in result
