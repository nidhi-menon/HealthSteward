"""Tests for PII anonymization module."""

import pytest
from datetime import date
from unittest.mock import MagicMock

from src.utils.anonymization import (
    Anonymizer,
    AnonymizedProfile,
    PII_PATTERNS,
    SPACY_AVAILABLE,
    _normalise_entity_value,
    anonymize_text,
    current_token_scope,
    scrub_leaked_tokens,
    token_scope,
)


def _ner_usable() -> bool:
    """True only if the NER branch will actually execute.

    `SPACY_AVAILABLE` alone isn't enough: `Anonymizer.nlp` silently flips
    `use_ner` back to False when `en_core_web_sm` isn't downloaded, so spaCy
    can be installed and the regex-only path still be what runs. Issue #125 is
    precisely about that branch being invisible, so the guard checks the thing
    it claims to check rather than a proxy for it.
    """
    if not SPACY_AVAILABLE:
        return False
    probe = Anonymizer(use_ner=True)
    return probe.nlp is not None


NER_UNAVAILABLE = not _ner_usable()
requires_ner = pytest.mark.skipif(
    NER_UNAVAILABLE,
    reason="spaCy and/or en_core_web_sm not installed — NER branch cannot run",
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
        result, _ = anonymizer.anonymize_text(text)
        return result

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
        """Six-digit lab values fall outside the unlabeled-MRN length band
        (7-10 digits) and short values are never in range, so ordinary
        clinical numbers still pass through untouched."""
        result = self._redacted(anonymizer, "Platelet count 250000 and ferritin 45")
        assert "250000" in result
        assert "45" in result

    # --- Unlabeled MRN-shaped digit runs ---

    @pytest.mark.parametrize("text,leaked", [
        ("Chart 12345678 shows no changes", "12345678"),
        ("Reference number 5551234 on file", "5551234"),
        ("Patient identifier 9988776655", "9988776655"),
    ])
    def test_unlabeled_mrn_length_digit_runs_redacted(self, anonymizer, text, leaked):
        """Bare 7-10 digit runs with no label are still redacted — the accepted
        false-positive tradeoff from DEC-025's follow-up: catching unlabeled
        MRNs was judged more important than the risk of over-redacting an
        unlabeled clinical value of the same length."""
        result = self._redacted(anonymizer, text)
        assert leaked not in result
        assert "[REDACTED]" in result

    @pytest.mark.parametrize("text", [
        "Dose adjusted to 1234567 mcg",
        "Reading was 12345678 mmHg",
        "Infusion rate 5551234 mL",
    ])
    def test_unlabeled_mrn_length_digit_runs_with_unit_preserved(self, anonymizer, text):
        """A 7-10 digit value immediately followed by a clinical unit is
        excluded — it reads as a measurement, not an identifier."""
        result = self._redacted(anonymizer, text)
        assert result == text

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
        result, _ = anonymizer.anonymize_text(text)

        # PII gone
        assert "12345678" not in result
        assert "+44 20 7946 0958" not in result
        assert "742 Evergreen Terrace" not in result
        assert "15/06/1985" not in result
        # Medicine kept
        assert "Metformin 500mg twice daily" in result
        assert "fatigue" in result


class TestSafeHarborGapPatterns:
    """Coverage for the HIPAA Safe Harbor identifier categories that had no
    dedicated pattern before this class existed (issue #122 follow-up).

    Mapping `PII_PATTERNS` against all 18 Safe Harbor categories found 7 with
    no pattern of their own: fax numbers (caught incidentally by `phone`, but
    previously untested), URLs, IP addresses, certificate/license numbers,
    account numbers, vehicle identifiers, and device serial numbers. Every
    positive case here is paired with an adversarial negative case found
    during testing — the `license_number` and `device_serial` patterns were
    narrowed after an early draft over-redacted a vaccine lot number and a
    prior-authorization certificate, so those two negative cases guard a real
    regression, not a hypothetical one.
    """

    @pytest.fixture
    def anonymizer(self):
        return Anonymizer(use_ner=False)

    def _redacted(self, anonymizer, text):
        result, _ = anonymizer.anonymize_text(text)
        return result

    # --- Fax (#5) — no dedicated pattern; caught by `phone`, now pinned ---

    def test_fax_number_redacted_via_phone_pattern(self, anonymizer):
        """Fax numbers have no distinguishing format of their own, so `phone`
        catches them by format coincidence. Previously asserted in prose only
        (module docstring), not pinned by a test."""
        result = self._redacted(anonymizer, "Records were sent to Fax: 555-201-4487 per the referral.")
        assert "555-201-4487" not in result
        assert "[REDACTED]" in result

    # --- URLs (#14) ---

    @pytest.mark.parametrize("text,leaked", [
        ("See the patient portal at https://portal.healthsteward.example/records/8823.",
         "https://portal.healthsteward.example/records/8823"),
        ("Telehealth link: http://meet.clinicvideo.example/room/nm-4471",
         "http://meet.clinicvideo.example/room/nm-4471"),
    ])
    def test_url_redacted(self, anonymizer, text, leaked):
        result = self._redacted(anonymizer, text)
        assert leaked not in result

    # --- IP addresses (#15) ---

    @pytest.mark.parametrize("text,leaked", [
        ("Login attempt was logged from IP 192.168.1.42 during the session.", "192.168.1.42"),
        ("Session originated from 203.0.113.77, flagged for review.", "203.0.113.77"),
    ])
    def test_ip_address_redacted(self, anonymizer, text, leaked):
        result = self._redacted(anonymizer, text)
        assert leaked not in result

    # --- Certificate/license numbers (#11) ---

    @pytest.mark.parametrize("text,label", [
        ("Driver's License Number: D1234567 was used to verify identity.", "Driver's License Number:"),
        ("License No. RN-4471029 was recorded for the visiting nurse.", "License No."),
    ])
    def test_license_number_redacted_label_kept(self, anonymizer, text, label):
        result = self._redacted(anonymizer, text)
        assert result.startswith(label)
        assert "[REDACTED]" in result

    @pytest.mark.parametrize("text", [
        "Certificate of medical necessity CMN-4471 was filed with the DME order.",
        "Prior authorization Certificate #: PA-991244 approved for six months.",
    ])
    def test_certificate_document_types_not_redacted(self, anonymizer, text):
        """A bare "Certificate"/"Cert" trigger was tested and dropped: it also
        matches non-identifying document types and insurance authorization
        numbers, which would over-redact billing/clinical content this
        module means to keep. Only "License"/"DEA" are label-anchored."""
        result = self._redacted(anonymizer, text)
        assert result == text

    # --- Account numbers (#10) ---

    @pytest.mark.parametrize("text,label", [
        ("Billing account number AB-9284710 was updated after the payment.", "Billing account number"),
        ("Account Number: 7734190552 going forward.", "Account Number:"),
    ])
    def test_account_number_redacted_label_kept(self, anonymizer, text, label):
        """Distinct from `insurance_id` — "Account" isn't in that pattern's
        label list. Before this pattern existed, an alphanumeric-prefixed
        account number only had its digit portion caught by the unlabeled-MRN
        fallback ("Account #: AB-9284710" -> "Account #: AB-[REDACTED]")."""
        result = self._redacted(anonymizer, text)
        assert result.startswith(label)
        assert "[REDACTED]" in result
        assert "AB-9284710" not in result
        assert "7734190552" not in result

    def test_account_number_less_templated_phrasing_redacted(self, anonymizer):
        """A parity check against the adversarial rigor applied to
        `license_number`/`device_serial`: `license_number`/`device_serial` were
        narrowed only after adversarial testing found real false positives —
        `account_number` and `vehicle_id` shipped without narrowing because
        none was found, but hadn't been checked with the same intensity. This
        and the negative cases below close that gap; run once as a throwaway
        script during development, now pinned as a permanent regression guard."""
        result = self._redacted(anonymizer, "Please reference account no 88213047 when calling billing.")
        assert "88213047" not in result

    @pytest.mark.parametrize("text", [
        "Account of the patient's fall was documented in the nursing note.",
        "On account of the recent surgery, activity is restricted for two weeks.",
        "Taking into account the patient's allergy history, avoid penicillin.",
        "Account balance after insurance adjustment is $42.10.",
    ])
    def test_account_word_in_non_identifying_context_not_redacted(self, anonymizer, text):
        """"Account" appears in ordinary clinical/billing prose too — these
        guard against the label trigger firing on the word alone without an
        actual account-number-shaped value following it."""
        result = self._redacted(anonymizer, text)
        assert result == text

    # --- Vehicle identifiers (#12) ---

    def test_vin_redacted_label_kept(self, anonymizer):
        result = self._redacted(anonymizer, "Transport service logged VIN: 1HGCM82633A123456 for the pickup.")
        assert result.startswith("Transport service logged VIN:")
        assert "1HGCM82633A123456" not in result

    def test_vin_hash_label_variant_redacted(self, anonymizer):
        """Less-templated label punctuation ("VIN#" vs. "VIN:")."""
        result = self._redacted(
            anonymizer, "VIN# 5YJSA1E14FF101002 was logged for the non-emergency transport van."
        )
        assert "5YJSA1E14FF101002" not in result

    @pytest.mark.parametrize("text", [
        "Registration for the diabetes education class opens next Monday.",
        "Appointment registration number was not required for the walk-in visit.",
        "Waitlist registration closed for the November wellness screening.",
        "Vehicle transport was arranged but no VIN was recorded in the chart.",
    ])
    def test_vehicle_adjacent_words_in_non_identifying_context_not_redacted(self, anonymizer, text):
        """"Registration" and a bare, valueless "VIN" mention both appear in
        ordinary scheduling/transport prose — neither should trigger this
        pattern, which requires an explicit "VIN" label immediately followed
        by an 11-17 character alphanumeric value."""
        result = self._redacted(anonymizer, text)
        assert result == text

    # --- Device serial numbers (#13) ---

    @pytest.mark.parametrize("text,label", [
        ("Device Serial Number: SN-88213047 was replaced during the check.", "Device Serial Number:"),
        ("Serial No: CGM-771402 identifies the continuous glucose monitor.", "Serial No:"),
    ])
    def test_device_serial_redacted_label_kept(self, anonymizer, text, label):
        result = self._redacted(anonymizer, text)
        assert result.startswith(label)
        assert "[REDACTED]" in result

    @pytest.mark.parametrize("text", [
        "Vaccine Lot Number: XJ4471 was administered per protocol.",
        "Batch Serial: LOT-88213 confirmed against the vial label.",
    ])
    def test_lot_and_batch_numbers_not_redacted_as_device_serial(self, anonymizer, text):
        """A medication/vaccine lot or batch number identifies a manufacturing
        run, not an individual — not a HIPAA identifier, and over-redacting it
        destroys clinically useful content (which lot was administered matters
        for recalls/adverse events). The negative lookbehind on "Lot"/"Batch"
        immediately before "Serial" is what this test guards; found during
        adversarial testing, not anticipated when the pattern was first written."""
        result = self._redacted(anonymizer, text)
        assert result == text


@requires_ner
class TestNERPath:
    """Coverage for the spaCy NER branch of `anonymize_text` (issue #125).

    Every other class in this file constructs `Anonymizer(use_ner=False)`, so
    until this class existed the `if self.use_ner and self.nlp:` branch had no
    coverage at all — positive or negative. The suite was green both with and
    without spaCy installed, because nothing exercised the difference. That's
    how the drug-name over-redaction in `test_medication_names_over_redacted`
    stayed invisible: DEC-025's reasoning rests on negative cases asserting
    clinical content survives redaction, and those cases only ever ran against
    the regex-only anonymizer.

    **These tests pin what the NER path does today, not what it should do.**
    The known-bad cases are `xfail`, not fixed assertions — deciding how to
    handle `PERSON` false positives (allowlist / corroboration / larger model /
    accept-and-document) changes behavior on the DEC-006 trust boundary and is
    item (2) of #125, deliberately deferred. When that lands, the `xfail`s here
    are the list of things to revisit.

    The whole class skips when spaCy or `en_core_web_sm` is absent — which is
    the case on a fresh clone and in CI, since spaCy is in neither
    `requirements.txt` nor `environment.yml`. A missing optional dependency
    should not be a red build.
    """

    @pytest.fixture
    def anonymizer(self):
        return Anonymizer(use_ner=True)

    def _redacted(self, anonymizer, text):
        result, _ = anonymizer.anonymize_text(text)
        return result

    def test_ner_branch_is_actually_active(self, anonymizer):
        """Guard the guard.

        If this fixture ever silently degraded to regex-only, every negative
        case below would pass for the wrong reason and the class would be
        decorative — exactly the failure mode #125 exists to close. `Jane Doe`
        matches no regex in `PII_PATTERNS`, so it can only be caught by NER.
        """
        assert anonymizer.use_ner is True
        assert anonymizer.nlp is not None
        assert "Jane Doe" not in self._redacted(anonymizer, "Emergency contact Jane Doe")

    # --- Positive cases: names NER is here to catch ---

    @pytest.mark.parametrize("text,name", [
        ("Emergency contact Jane Doe at 555-123-4567", "Jane Doe"),
        ("Referred by Dr. Sarah Johnson last spring", "Sarah Johnson"),
        ("Spoke with Robert Martinez about the referral", "Robert Martinez"),
    ])
    def test_full_names_in_free_text_redacted(self, anonymizer, text, name):
        """Multi-token names in free text are the reason the NER branch exists —
        no `PII_PATTERNS` entry matches a bare name."""
        result = self._redacted(anonymizer, text)
        assert name not in result
        assert "[REDACTED]" in result

    @pytest.mark.xfail(
        reason="issue #125: en_core_web_sm doesn't tag single-token surnames "
               "after a title as PERSON. Pinned, not fixed.",
    )
    def test_single_token_surname_after_title_redacted(self, anonymizer):
        """`Smith` survives while `Sarah Johnson` doesn't — the weak case for
        `en_core_web_sm`, measured on the #122 corpus. The phone number in the
        same sentence is caught by regex, so the leak is easy to miss."""
        assert "Smith" not in self._redacted(anonymizer, "Call Dr. Smith at 555-123-4567")

    # --- Negative cases: clinical content must survive, NER on ---
    #
    # Same corpus as TestHardenedPIIPatterns::test_clinical_content_not_redacted,
    # re-run against the NER path. Exactly one case moves (see below), which is
    # the whole point of duplicating the list rather than trusting that the
    # regex-only result carries over.

    @pytest.mark.parametrize("text", [
        "Metformin 500mg twice daily",
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
        "Continue Metformin 500mg twice daily.",
        "Blood pressure well controlled on current regimen",
    ])
    def test_clinical_content_not_redacted_with_ner(self, anonymizer, text):
        """Over-redaction with NER on is a *worse* failure than with it off:
        it destroys clinically load-bearing tokens rather than dose-shaped
        numbers. `Lisinopril 10 mg daily` is the case from this same list that
        does not survive — split out below rather than dropped, so the
        difference between the two paths is visible in the test names."""
        assert self._redacted(anonymizer, text) == text

    @pytest.mark.parametrize("text,drug", [
        ("Lisinopril 10 mg daily", "Lisinopril"),
        ("Started Rosuvastatin last month.", "Rosuvastatin"),
    ])
    @pytest.mark.xfail(
        reason="issue #125 item (2), deferred: en_core_web_sm tags drug names "
               "as PERSON and anonymize_text redacts every PERSON "
               "unconditionally. Pinned as known-bad, not fixed.",
    )
    def test_medication_names_over_redacted(self, anonymizer, text, drug):
        """The finding that opened #125. The drug name is the single most
        clinically load-bearing token in the sentence and it is destroyed
        before the LLM generating visit prep ever sees it.

        Not an exotic-name edge case: sweeping 205 common generic and brand
        drug names through `en_core_web_sm` across five sentence templates,
        69% were tagged `PERSON` in at least one context and 8% in every
        context (see the #125 thread for the full numbers). `Started
        Rosuvastatin last month.` is the worse shape — the span swallows the
        preceding verb too, yielding `[REDACTED] last month.`
        """
        assert drug in self._redacted(anonymizer, text)

    # --- Redaction events (DEC-029) on the NER path ---

    def test_person_redaction_emits_event_with_span_not_value(self, anonymizer):
        """DEC-029's event log is also unpinned on this branch. A PERSON event
        must carry type and span only — never the matched name."""
        text = "Spoke with Robert Martinez about the referral"
        result, events = anonymizer.anonymize_text(text, field_name="notes")

        person_events = [e for e in events if e.entity_type == "PERSON"]
        assert len(person_events) == 1
        event = person_events[0]
        assert text[event.start:event.end] == "Robert Martinez"
        assert event.field_name == "notes"
        assert "Robert" not in str(event.to_dict())
        assert "Robert Martinez" not in result

    def test_person_event_ids_stable_across_runs(self, anonymizer):
        """Same guarantee `TestAnonymizer` makes for regex events: ids are a
        deterministic hash, so two runs over the same field agree."""
        text = "Emergency contact Jane Doe"
        _, first = anonymizer.anonymize_text(text, profile_id="p1", field_name="notes")
        _, second = anonymizer.anonymize_text(text, profile_id="p1", field_name="notes")

        assert [e.entity_id for e in first] == [e.entity_id for e in second]
        assert [e.entity_type for e in first] == ["PERSON"]

    def test_ner_spans_are_offsets_into_post_regex_text(self, anonymizer):
        """NER runs on the text *after* regex substitution, so its spans index
        the partially-redacted string, not the original. Pinned because it's a
        real trap for anyone reading `extra_data["redaction_events"]` — a
        PERSON span and a phone span in the same event list are offsets into
        two different strings."""
        text = "Call 555-123-4567 and ask for Jane Doe"
        result, events = anonymizer.anonymize_text(text)

        person = next(e for e in events if e.entity_type == "PERSON")
        post_regex = PII_PATTERNS["phone"].sub("[REDACTED]", text)
        assert post_regex[person.start:person.end] == "Jane Doe"
        # ...and not an offset into the original.
        assert text[person.start:person.end] != "Jane Doe"
        assert "Jane Doe" not in result


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

        result, events = anonymizer.anonymize_doctor(doctor)

        assert result.notes is not None
        assert "555-000-1111" not in result.notes
        assert "[REDACTED]" in result.notes
        assert "phone follow-ups" in result.notes
        assert any(e.entity_type == "phone" for e in events)

    def test_anonymize_doctor_with_no_notes(self, anonymizer):
        """None notes should stay None, not become an empty/placeholder string."""
        doctor = MagicMock()
        doctor.name = "Dr. Sarah Johnson"
        doctor.specialty = "Endocrinology"
        doctor.clinic = "City Medical Center"
        doctor.notes = None

        result, events = anonymizer.anonymize_doctor(doctor)

        assert result.notes is None
        assert events == []

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
        result, events = anonymizer.anonymize_text(text)

        assert "555-123-4567" not in result
        assert "(800) 555-0100" not in result
        assert "[REDACTED]" in result
        assert len(events) == 2
        assert all(e.entity_type == "phone" for e in events)

    def test_anonymize_text_emails(self, anonymizer):
        """Test email redaction."""
        text = "Contact the office at frontdesk@clinic.com"
        result, events = anonymizer.anonymize_text(text)

        assert "frontdesk@clinic.com" not in result
        assert "[REDACTED]" in result
        assert len(events) == 1
        assert events[0].entity_type == "email"

    def test_anonymize_text_ssn(self, anonymizer):
        """Test SSN redaction."""
        text = "Patient SSN: 123-45-6789"
        result, events = anonymizer.anonymize_text(text)

        assert "123-45-6789" not in result
        assert "[REDACTED]" in result
        assert len(events) == 1
        assert events[0].entity_type == "ssn"

    def test_anonymize_text_preserves_medical_content(self, anonymizer):
        """Test that medical information is preserved."""
        text = "Patient has Type 2 Diabetes and takes Metformin 500mg twice daily"
        result, events = anonymizer.anonymize_text(text)

        # Medical info should be preserved
        assert "Type 2 Diabetes" in result
        assert "Metformin" in result
        assert "500mg" in result
        assert events == []

    def test_anonymize_text_none(self, anonymizer):
        """Test handling of None input."""
        result, events = anonymizer.anonymize_text(None)
        assert result is None
        assert events == []

    def test_anonymize_text_empty(self, anonymizer):
        """Test handling of empty string."""
        result, events = anonymizer.anonymize_text("")
        assert result == ""
        assert events == []

    def test_anonymize_text_event_never_contains_raw_value(self, anonymizer):
        """The redaction event must carry type + span only — never the
        matched substring itself (issue #16, DEC-006)."""
        text = "SSN: 123-45-6789"
        result, events = anonymizer.anonymize_text(text)

        assert len(events) == 1
        event = events[0]
        matched_span = text[event.start:event.end]
        assert "123-45-6789" in matched_span  # span is meaningful...
        for attr_name in ("entity_type", "field_name"):
            value = getattr(event, attr_name)
            assert "123-45-6789" not in str(value)
        # The event object itself has no field holding the raw match
        assert not hasattr(event, "value")
        assert not hasattr(event, "matched_text")
        assert not hasattr(event, "raw_value")

    def test_anonymize_text_entity_id_stable_across_runs(self, anonymizer):
        """Same profile_id/field_name/text must yield the same entity id on
        repeated calls (issue #16) — the id is a deterministic hash, not a
        random UUID."""
        text = "Call 555-123-4567 or email a@b.com"
        _, events1 = anonymizer.anonymize_text(
            text, profile_id="profile-1", field_name="appointment:abc:purpose"
        )
        _, events2 = anonymizer.anonymize_text(
            text, profile_id="profile-1", field_name="appointment:abc:purpose"
        )

        assert [e.entity_id for e in events1] == [e.entity_id for e in events2]
        # Distinct entities within the same call get distinct ids
        assert len({e.entity_id for e in events1}) == len(events1)

    def test_anonymize_text_entity_id_differs_by_field_name(self, anonymizer):
        """The same text redacted under a different field_name must not
        collide — ids are scoped per field, not just per profile."""
        text = "Call 555-123-4567"
        _, events1 = anonymizer.anonymize_text(
            text, profile_id="profile-1", field_name="condition:c1:notes"
        )
        _, events2 = anonymizer.anonymize_text(
            text, profile_id="profile-1", field_name="condition:c2:notes"
        )

        assert events1[0].entity_id != events2[0].entity_id

    def test_anonymize_text_document_id_tagged_when_provided(self, anonymizer):
        """A document_id passed through is carried onto every event from that
        call (opportunistic per-document traceability, issue #16)."""
        text = "Weight 185 lbs, MRN: 12345678"
        _, events = anonymizer.anonymize_text(
            text, profile_id="profile-1", field_name="vitals:v1:notes",
            document_id="doc-1",
        )

        assert len(events) == 1
        assert events[0].document_id == "doc-1"
        assert events[0].to_dict()["document_id"] == "doc-1"
        assert "document_link" not in events[0].to_dict()

    def test_anonymize_text_no_document_link_logged_honestly(self, anonymizer):
        """Fields with no document lineage (e.g. user-typed notes) log
        `document_link: "none"` rather than omitting the key or fabricating
        a document_id (issue #16)."""
        text = "MRN: 12345678"
        _, events = anonymizer.anonymize_text(
            text, profile_id="profile-1", field_name="additional_concerns",
        )

        assert len(events) == 1
        assert events[0].document_id is None
        d = events[0].to_dict()
        assert d["document_link"] == "none"
        assert "document_id" not in d


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
        result, _ = anonymizer.anonymize_profile(mock_profile)

        # The AnonymizedProfile doesn't have a name field at all
        assert not hasattr(result, 'name')
        assert isinstance(result, AnonymizedProfile)

    def test_anonymize_profile_age_conversion(self, anonymizer, mock_profile):
        """Test that DOB is converted to age."""
        result, _ = anonymizer.anonymize_profile(mock_profile)

        assert result.age_description is not None
        assert "years old" in result.age_description
        # Should not contain the actual date
        assert "1985" not in str(result.age_description)

    def test_anonymize_profile_preserves_medical_info(self, anonymizer, mock_profile):
        """Test that conditions and medications are preserved."""
        result, _ = anonymizer.anonymize_profile(mock_profile)

        assert len(result.conditions) == 1
        assert result.conditions[0]['name'] == "Type 2 Diabetes"
        assert result.conditions[0]['severity'] == "moderate"

        assert len(result.medications) == 1
        assert result.medications[0]['name'] == "Metformin"
        assert result.medications[0]['dosage'] == "500mg"

    def test_anonymize_profile_anonymizes_prescribing_doctor(self, anonymizer, mock_profile):
        """Test that prescribing doctor is anonymized."""
        result, _ = anonymizer.anonymize_profile(mock_profile)

        med = result.medications[0]
        assert med['prescribed_by'] == "Prescribing physician"
        assert "John Smith" not in str(med)

    def test_anonymize_profile_anonymizes_notes(self, anonymizer, mock_profile):
        """Test that phone numbers in notes are redacted."""
        result, events = anonymizer.anonymize_profile(mock_profile)

        condition_notes = result.conditions[0]['notes']
        assert "555-000-1111" not in condition_notes
        assert "[REDACTED]" in condition_notes

    def test_anonymize_profile_condition_events_have_no_document_link(self, anonymizer, mock_profile):
        """Condition has no document_id column (src/data/models.py) — events
        must log "no document link" honestly rather than fabricate one."""
        _, events = anonymizer.anonymize_profile(mock_profile)

        assert len(events) == 1
        assert events[0].document_id is None
        assert events[0].to_dict()["document_link"] == "none"


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
        appointment.id = "appt-1"
        appointment.profile_id = "profile-1"
        appointment.doctor = doctor
        appointment.scheduled_date = date(2024, 3, 1)
        appointment.purpose = "Follow-up"
        appointment.prep_notes = "Ask about fatigue, call 555-123-4567 if urgent"
        appointment.visit_notes = "Discussed dosage increase"

        result, events = anonymizer.anonymize_appointment(appointment)

        assert result.prep_notes is not None
        assert "Ask about fatigue" in result.prep_notes
        assert "555-123-4567" not in result.prep_notes
        assert "[REDACTED]" in result.prep_notes
        assert result.visit_notes == "Discussed dosage increase"

        # Appointment has no document_id column — events log "no document link"
        assert len(events) == 1
        assert events[0].document_id is None
        assert events[0].to_dict()["document_link"] == "none"


class TestModuleLevelFunctions:
    """Test module-level convenience functions."""

    def test_anonymize_text_function(self):
        """Test the module-level anonymize_text function."""
        text = "Call 555-123-4567"
        result, events = anonymize_text(text)

        assert "555-123-4567" not in result
        assert "[REDACTED]" in result
        assert len(events) == 1
        assert events[0].entity_type == "phone"


class TestTokenScope:
    """Per-entity tokens instead of a flat `[REDACTED]` (issue #17).

    The point is relational: "referred by Dr. Smith to Dr. Jones" loses the
    fact that those are two different providers when both become the same
    literal. Inside a `token_scope()` they become `PERSON_1` and `PERSON_2`,
    consistently across every `anonymize_text()` call in the scope.

    These exercise the regex path, which needs no spaCy — the NER half is in
    `TestTokenScopeNER` below and skips when the model isn't installed.
    """

    @pytest.fixture
    def anonymizer(self):
        return Anonymizer(use_ner=False)

    def test_no_scope_is_byte_for_byte_todays_behaviour(self, anonymizer):
        """The default path must not change at all. Tokenisation is opt-in, so
        every existing caller — including the module-level singleton — keeps
        emitting `[REDACTED]` and can't accumulate a cross-patient map."""
        text = "Call 555-123-4567 or 555-987-6543"
        result, _ = anonymizer.anonymize_text(text)

        assert result == "Call [REDACTED] or [REDACTED]"
        assert current_token_scope() is None

    def test_distinct_values_get_distinct_tokens(self, anonymizer):
        with token_scope():
            result, _ = anonymizer.anonymize_text("Call 555-123-4567 or 555-987-6543")

        assert result == "Call PHONE_1 or PHONE_2"

    def test_the_same_value_gets_the_same_token_within_a_field(self, anonymizer):
        with token_scope():
            result, _ = anonymizer.anonymize_text(
                "Call 555-123-4567; if no answer call 555-123-4567 again"
            )

        assert result.count("PHONE_1") == 2
        assert "PHONE_2" not in result

    def test_the_same_value_gets_the_same_token_across_calls(self, anonymizer):
        """The whole reason the map is scoped rather than per-call: within one
        `prepare_visit()` the same entity is anonymized from several separate
        entry points (profile, doctor, appointment, concerns)."""
        with token_scope():
            first, _ = anonymizer.anonymize_text(
                "Contact 555-123-4567", field_name="condition:1:notes"
            )
            second, _ = anonymizer.anonymize_text(
                "Also 555-123-4567 and 555-987-6543", field_name="doctor:1:notes"
            )

        assert first == "Contact PHONE_1"
        assert second == "Also PHONE_1 and PHONE_2"

    def test_leaving_a_scope_clears_the_map(self, anonymizer):
        """Two patients in one process must never share a numbering space."""
        with token_scope():
            first, _ = anonymizer.anonymize_text("Call 555-123-4567")
        with token_scope():
            second, _ = anonymizer.anonymize_text("Call 555-987-6543")

        assert first == "Call PHONE_1"
        assert second == "Call PHONE_1"  # restarts, not PHONE_2
        assert current_token_scope() is None

    def test_the_module_singleton_does_not_leak_between_scopes(self):
        """`anonymize_text()`'s singleton is the path that would accumulate a
        cross-patient map if scope state lived on the instance."""
        with token_scope():
            first, _ = anonymize_text("Reach me at 555-123-4567")
        with token_scope():
            second, _ = anonymize_text("Reach me at 555-987-6543")

        assert first == second == "Reach me at PHONE_1"

    @pytest.mark.asyncio
    async def test_concurrent_tasks_get_independent_scopes(self):
        """Scope state is a ContextVar, so two requests running concurrently
        against the singleton can't see each other's tokens."""
        import asyncio

        async def anonymize(phone: str) -> str:
            with token_scope():
                await asyncio.sleep(0)  # force interleaving
                result, _ = anonymize_text(f"Call {phone}")
                await asyncio.sleep(0)
                return result

        first, second = await asyncio.gather(
            anonymize("555-123-4567"), anonymize("555-987-6543")
        )
        assert first == second == "Call PHONE_1"

    def test_distinct_types_number_independently(self, anonymizer):
        with token_scope():
            result, _ = anonymizer.anonymize_text(
                "Call 555-123-4567 or email pat@example.com"
            )

        assert result == "Call PHONE_1 or email EMAIL_1"

    def test_label_anchored_patterns_keep_their_label(self, anonymizer):
        """`MRN: MRN_1` — the label still says what kind of identifier was
        removed, exactly as `MRN: [REDACTED]` did (see PII_REPLACEMENTS)."""
        with token_scope():
            result, _ = anonymizer.anonymize_text("MRN: 1234567 seen in clinic")

        assert result == "MRN: MRN_1 seen in clinic"

    def test_the_same_identifier_labeled_and_bare_is_one_entity(self, anonymizer):
        """Tokens key on the matched value, not on which pattern caught it."""
        with token_scope():
            result, _ = anonymizer.anonymize_text("MRN: 1234567 — chart 1234567")

        assert result.count("MRN_1") == 2
        assert "MRN_2" not in result

    def test_redaction_event_offsets_survive_variable_length_tokens(
        self, anonymizer
    ):
        """`[REDACTED]` was fixed-width; tokens are not. Events are recorded
        against the text state each pattern matched against, so an event from a
        later pattern must still index correctly after an earlier pattern
        replaced a match with a shorter or longer token (DEC-029)."""
        text = "Call 555-123-4567 then email pat@example.com"
        with token_scope():
            _, events = anonymizer.anonymize_text(text)

        phone = next(e for e in events if e.entity_type == "phone")
        assert text[phone.start:phone.end] == "555-123-4567"

        email = next(e for e in events if e.entity_type == "email")
        post_phone = text.replace("555-123-4567", "PHONE_1")
        assert post_phone[email.start:email.end] == "pat@example.com"

    def test_events_still_never_carry_the_matched_value(self, anonymizer):
        with token_scope():
            _, events = anonymizer.anonymize_text(
                "Call 555-123-4567", field_name="notes"
            )

        assert "555-123-4567" not in str([e.to_dict() for e in events])


class TestEntityValueNormalisation:
    """How two mentions are judged to be the same entity (issue #17, Q3).

    Exact normalised matching only. A wrong *merge* would actively tell the
    model two different providers are one person; under-merging just degrades
    to roughly the pre-#17 behaviour for the mentions that didn't merge, which
    is the safe failure direction. So: casefold, strip one leading title, strip
    surrounding punctuation — and nothing fuzzier.
    """

    @pytest.mark.parametrize("first,second", [
        ("Dr. Smith", "Smith"),
        ("Dr. Smith", "smith"),
        ("Smith,", "Smith"),
        ("Dr.  Jane   Smith", "Jane Smith"),
        ("Doctor Jane Smith", "jane smith"),
    ])
    def test_mentions_that_merge(self, first, second):
        assert _normalise_entity_value(first) == _normalise_entity_value(second)

    @pytest.mark.parametrize("first,second", [
        ("Dr. Smith", "Dr. Smyth"),      # no fuzzy matching
        ("Jane Smith", "Smith"),         # no surname-only coreference
        ("Dr. Smith", "Dr. Jones"),
    ])
    def test_mentions_that_stay_distinct(self, first, second):
        assert _normalise_entity_value(first) != _normalise_entity_value(second)


class TestLeakedTokenGuard:
    """The output-side guard (issue #17, step 3).

    A model handed `PERSON_1` can echo it into a generated question. This
    rewrites stray tokens back to `[REDACTED]` — the marker the app already
    shows — so the worst case is exactly the pre-#17 behaviour. It is *not*
    re-hydration: nothing here maps a token back to the value it stood for.
    """

    @pytest.mark.parametrize("text,expected", [
        ("Ask PERSON_1 about the referral", "Ask [REDACTED] about the referral"),
        ("PERSON_1 referred you to PERSON_2",
         "[REDACTED] referred you to [REDACTED]"),
        ("Confirm MRN_1 at the desk", "Confirm [REDACTED] at the desk"),
        ("Call PHONE_12 before the visit", "Call [REDACTED] before the visit"),
        ("Check INSURANCE_ID_1", "Check [REDACTED]"),
    ])
    def test_tokens_are_rewritten(self, text, expected):
        assert scrub_leaked_tokens(text) == expected

    @pytest.mark.parametrize("text", [
        "Ask about your A1C trend since March",
        "Discuss PERSONAL goals for this year",   # not a token
        "Your PERSON of contact",                  # no index suffix
        "Bring the MRN card",
        "",
    ])
    def test_ordinary_text_is_untouched(self, text):
        assert scrub_leaked_tokens(text) == text

    def test_none_passes_through(self):
        assert scrub_leaked_tokens(None) is None


@requires_ner
class TestTokenScopeNER:
    """The half of issue #17 that motivated it: distinct people in free text.

    Skips wherever spaCy/`en_core_web_sm` is absent, matching `TestNERPath`.
    """

    @pytest.fixture
    def anonymizer(self):
        return Anonymizer(use_ner=True)

    def test_two_people_in_one_sentence_get_two_tokens(self, anonymizer):
        with token_scope():
            result, _ = anonymizer.anonymize_text(
                "Referred by Dr. Smith to Dr. Jones"
            )

        assert "PERSON_1" in result and "PERSON_2" in result
        assert "Smith" not in result and "Jones" not in result

    def test_the_same_person_across_fields_gets_one_token(self, anonymizer):
        with token_scope():
            first, _ = anonymizer.anonymize_text(
                "Robert Martinez ordered the panel", field_name="condition:1:notes"
            )
            second, _ = anonymizer.anonymize_text(
                "Follow up with Robert Martinez", field_name="doctor:1:notes"
            )

        assert "PERSON_1" in first
        assert "PERSON_1" in second
        assert "PERSON_2" not in second

    def test_no_scope_still_emits_the_flat_redaction(self, anonymizer):
        result, _ = anonymizer.anonymize_text("Referred by Dr. Smith to Dr. Jones")

        assert result.count("[REDACTED]") == 2
        assert "PERSON_1" not in result
