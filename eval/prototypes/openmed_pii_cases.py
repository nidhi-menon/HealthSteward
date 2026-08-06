"""Benchmark corpus for the OpenMed PII prototype (issue #122).

**Prototype/evaluation data only.** Nothing here is imported by production code
or by `tests/` — it exists so `eval/prototypes/openmed_pii_prototype.py` can
score a third-party PII detector against the same real cases the current
anonymizer is already held to.

Every case below is transcribed from `tests/test_anonymization.py`, which is the
de-facto specification of what `src/utils/anonymization.py` is expected to catch
and (just as importantly) expected to leave alone. Each group cites the test it
came from, so this file stays checkable against the source of truth rather than
becoming an independent, drifting corpus.

Two case kinds, because a PII detector can fail in two directions:

- `PositiveCase` — text containing PII. `must_remove` lists the exact substrings
  that must not survive redaction. Missing one is a **leak**: the whole point of
  DEC-006's boundary is that these never reach an external LLM.
- `NegativeCase` — clinical text containing no PII. The redacted output must be
  byte-identical to the input. Redacting here is **over-redaction**: it doesn't
  leak anything, but it degrades the clinical content the visit-prep call needs
  to be useful, which is its own kind of failure (see
  `TestHardenedPIIPatterns::test_clinical_content_not_redacted`).

The `category` field exists so results can be reported per PII shape rather than
as a single aggregate number — "OpenMed wins on names, loses on dose ranges" is
a far more actionable finding than a single accuracy percentage.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class PositiveCase:
    """Text containing PII that must not survive redaction."""

    text: str
    must_remove: tuple[str, ...]
    category: str


@dataclass(frozen=True)
class NegativeCase:
    """Clinical text that must pass through redaction byte-identical."""

    text: str
    category: str
    # Substrings whose loss is the specific regression this case guards. Only
    # used to make failure output readable; the pass condition is exact equality.
    notable: tuple[str, ...] = field(default_factory=tuple)


# --- Positive cases -------------------------------------------------------
#
# Ordering mirrors tests/test_anonymization.py so the two can be diffed by eye.

POSITIVE_CASES: tuple[PositiveCase, ...] = (
    # TestPIIPatterns::test_phone_pattern_standard
    PositiveCase("Call me at 555-123-4567", ("555-123-4567",), "phone"),
    PositiveCase("Phone: (555) 123-4567", ("(555) 123-4567",), "phone"),
    PositiveCase("555.123.4567", ("555.123.4567",), "phone"),
    PositiveCase("+1-555-555-4567", ("+1-555-555-4567",), "phone"),
    PositiveCase("5551234567", ("5551234567",), "phone"),

    # TestPIIPatterns::test_email_pattern
    PositiveCase("Contact: john.doe@example.com", ("john.doe@example.com",), "email"),
    PositiveCase("email: patient123@hospital.org", ("patient123@hospital.org",), "email"),
    # TestAnonymizer::test_anonymize_text_emails
    PositiveCase(
        "Contact the office at frontdesk@clinic.com",
        ("frontdesk@clinic.com",),
        "email",
    ),

    # TestPIIPatterns::test_ssn_pattern / TestAnonymizer::test_anonymize_text_ssn
    PositiveCase("SSN: 123-45-6789", ("123-45-6789",), "ssn"),
    PositiveCase("123.45.6789", ("123.45.6789",), "ssn"),
    PositiveCase("Patient SSN: 123-45-6789", ("123-45-6789",), "ssn"),

    # TestHardenedPIIPatterns::test_international_phone_redacted_whole
    PositiveCase("Call +44 20 7946 0958", ("+44 20 7946 0958",), "phone_intl"),
    PositiveCase("Reach me on +91 98765 43210", ("+91 98765 43210",), "phone_intl"),
    PositiveCase("Clinic line +33 1 42 68 53 00", ("+33 1 42 68 53 00",), "phone_intl"),
    PositiveCase("Office: +81-3-1234-5678", ("+81-3-1234-5678",), "phone_intl"),
    PositiveCase("+44 (0)20 7946 0958", ("+44 (0)20 7946 0958",), "phone_intl"),

    # TestHardenedPIIPatterns::test_po_box_redacted
    PositiveCase("Mail to P.O. Box 1234", ("P.O. Box 1234",), "po_box"),
    PositiveCase("PO Box 567, Springfield", ("PO Box 567",), "po_box"),
    PositiveCase("Post Office Box 89", ("Post Office Box 89",), "po_box"),
    PositiveCase("p.o. box 42", ("p.o. box 42",), "po_box"),

    # TestHardenedPIIPatterns::test_widened_street_suffixes_redacted
    PositiveCase("742 Evergreen Terrace", ("742 Evergreen Terrace",), "address"),
    PositiveCase("742 Evergreen Ter", ("742 Evergreen Ter",), "address"),
    PositiveCase("12 Oak Circle", ("12 Oak Circle",), "address"),
    PositiveCase("900 Bay Parkway", ("900 Bay Parkway",), "address"),
    PositiveCase("900 Bay Pkwy", ("900 Bay Pkwy",), "address"),
    PositiveCase("45 Country Highway", ("45 Country Highway",), "address"),
    PositiveCase("88 Cedar Trail", ("88 Cedar Trail",), "address"),
    PositiveCase("5 Union Square", ("5 Union Square",), "address"),
    PositiveCase("17 Mill Crossing", ("17 Mill Crossing",), "address"),
    PositiveCase("3 Harbor Plaza", ("3 Harbor Plaza",), "address"),

    # TestHardenedPIIPatterns::test_address_unit_designator_redacted_with_address
    PositiveCase("742 Evergreen Terrace Apt 4B", ("742 Evergreen Terrace Apt 4B",), "address_unit"),
    PositiveCase("123 Main St Unit 5", ("123 Main St Unit 5",), "address_unit"),
    PositiveCase("50 Elm Road Suite 200", ("50 Elm Road Suite 200",), "address_unit"),
    PositiveCase("9 Pine Lane, Apt 12", ("9 Pine Lane, Apt 12",), "address_unit"),
    PositiveCase("9 Pine Lane #12", ("9 Pine Lane #12",), "address_unit"),

    # TestHardenedPIIPatterns::test_original_address_suffixes_still_work
    PositiveCase("123 Main St", ("123 Main St",), "address"),
    PositiveCase("45 Oak Avenue", ("45 Oak Avenue",), "address"),
    PositiveCase("9 Elm Blvd", ("9 Elm Blvd",), "address"),
    PositiveCase("77 Sunset Drive", ("77 Sunset Drive",), "address"),

    # TestHardenedPIIPatterns::test_zip_plus_four_redacted_whole / _state_qualified_zip
    PositiveCase("Lives at 94103-1234", ("94103-1234",), "zip"),
    PositiveCase("Springfield, IL 62704", ("62704",), "zip"),

    # TestHardenedPIIPatterns::test_additional_date_formats_redacted
    PositiveCase("DOB 15/06/1985", ("15/06/1985",), "date"),
    PositiveCase("DOB 06/15/85", ("06/15/85",), "date"),
    PositiveCase("DOB: 1985-06-15", ("1985-06-15",), "date"),
    PositiveCase("Born June 15, 1985", ("June 15, 1985",), "date"),
    PositiveCase("Born 15 June 1985", ("15 June 1985",), "date"),
    PositiveCase("Born Jun 15, 1985", ("Jun 15, 1985",), "date"),
    # TestHardenedPIIPatterns::test_original_date_format_still_redacted
    PositiveCase("DOB 06/15/1985", ("06/15/1985",), "date"),

    # TestHardenedPIIPatterns::test_mrn_value_redacted_label_kept
    PositiveCase("MRN: 12345678", ("12345678",), "mrn_labeled"),
    PositiveCase("MRN 004512", ("004512",), "mrn_labeled"),
    PositiveCase("Medical Record Number: 987654", ("987654",), "mrn_labeled"),
    PositiveCase("MRN: A00123456", ("A00123456",), "mrn_labeled"),
    PositiveCase("Chart Number: 55501234", ("55501234",), "mrn_labeled"),

    # TestHardenedPIIPatterns::test_insurance_id_value_redacted_label_kept
    PositiveCase("Member ID: XZY123456789", ("XZY123456789",), "insurance_id"),
    PositiveCase("Policy #: ABC-12345678", ("ABC-12345678",), "insurance_id"),
    PositiveCase("Group Number: 0012345", ("0012345",), "insurance_id"),
    PositiveCase("Subscriber ID 998877665", ("998877665",), "insurance_id"),

    # TestHardenedPIIPatterns::test_unlabeled_mrn_length_digit_runs_redacted
    PositiveCase("Chart 12345678 shows no changes", ("12345678",), "mrn_unlabeled"),
    PositiveCase("Reference number 5551234 on file", ("5551234",), "mrn_unlabeled"),
    PositiveCase("Patient identifier 9988776655", ("9988776655",), "mrn_unlabeled"),

    # Person names. The regex list catches none of these by construction — names
    # are the spaCy-NER half of DEC-006's approach, and issue #73 flags this as
    # the weakest part of the current design. These are the cases the OpenMed
    # comparison exists to probe.
    # Sources: TestAnonymizer::test_anonymize_text_phone_numbers,
    # test_anonymize_doctor_includes_anonymized_notes, TestAnonymizerProfile's
    # mock_profile condition notes.
    PositiveCase("Call Dr. Smith at 555-123-4567", ("Smith", "555-123-4567"), "person_name"),
    PositiveCase(
        "Diet controlled. Contact Dr. Smith at 555-000-1111 for questions.",
        ("Smith", "555-000-1111"),
        "person_name",
    ),
    PositiveCase(
        "Prefers phone follow-ups. Call 555-000-1111 to reach the office.",
        ("555-000-1111",),
        "phone",
    ),
    PositiveCase(
        "Emergency contact Jane Doe, reachable at 555-123-4567",
        ("Jane Doe", "555-123-4567"),
        "person_name",
    ),
    PositiveCase(
        "Referred by Dr. Sarah Johnson last spring",
        ("Sarah Johnson",),
        "person_name",
    ),
    PositiveCase(
        "Ask about fatigue, call 555-123-4567 if urgent",
        ("555-123-4567",),
        "phone",
    ),

    # TestHardenedPIIPatterns::test_mixed_note_redacts_pii_and_keeps_medicine
    # The one end-to-end case: realistic AVS-style note, four PII shapes at once.
    # Its clinical-content half is mirrored as a negative case below.
    PositiveCase(
        "Patient reports fatigue. Continue Metformin 500mg twice daily. "
        "MRN: 12345678. Call the office at +44 20 7946 0958 or write to "
        "742 Evergreen Terrace Apt 4B. DOB 15/06/1985.",
        ("12345678", "+44 20 7946 0958", "742 Evergreen Terrace", "15/06/1985"),
        "mixed_note",
    ),
)


# --- Negative cases -------------------------------------------------------

NEGATIVE_CASES: tuple[NegativeCase, ...] = (
    # TestHardenedPIIPatterns::test_clinical_content_not_redacted
    NegativeCase("Metformin 500mg twice daily", "medication"),
    NegativeCase("Lisinopril 10 mg daily", "medication"),
    NegativeCase("BP 120/80", "vitals", ("120/80",)),
    NegativeCase("A1C was 7.2", "labs", ("7.2",)),
    NegativeCase("Vitamin D 32 ng/mL", "labs", ("32 ng/mL",)),
    NegativeCase("Type 2 Diabetes, managed", "condition"),
    NegativeCase("Diagnosis code E11.9", "condition", ("E11.9",)),
    NegativeCase("Symptoms for 3 years", "duration"),
    NegativeCase("Appointment at 10:30", "scheduling", ("10:30",)),
    NegativeCase("Weight 185 lbs", "vitals", ("185",)),
    NegativeCase("LDL 130, HDL 55, total 210", "labs", ("130", "55", "210")),
    NegativeCase("Titrate 25-50 mg", "dosage", ("25-50",)),
    NegativeCase("Fasting glucose 95-110 range", "labs", ("95-110",)),
    NegativeCase("Take 1/2 tablet in the morning", "dosage", ("1/2",)),

    # TestHardenedPIIPatterns::test_bare_five_digit_number_not_redacted
    NegativeCase("Step count averaged 12500 per day", "vitals", ("12500",)),

    # TestHardenedPIIPatterns::test_month_and_year_without_day_preserved
    # Scheduling context, not a birthdate — keeping it is what makes the
    # anonymized text still useful for visit prep.
    NegativeCase("Follow up in January 2026", "scheduling", ("January 2026",)),

    # TestHardenedPIIPatterns::test_labeled_patterns_do_not_match_lowercase_prose
    NegativeCase("Plan: increase dose gradually", "plan", ("increase dose gradually",)),

    # TestHardenedPIIPatterns::test_unlabeled_numbers_not_treated_as_identifiers
    NegativeCase("Platelet count 250000 and ferritin 45", "labs", ("250000", "45")),

    # TestHardenedPIIPatterns::test_unlabeled_mrn_length_digit_runs_with_unit_preserved
    NegativeCase("Dose adjusted to 1234567 mcg", "dosage", ("1234567 mcg",)),
    NegativeCase("Reading was 12345678 mmHg", "vitals", ("12345678 mmHg",)),
    NegativeCase("Infusion rate 5551234 mL", "dosage", ("5551234 mL",)),

    # TestAnonymizer::test_anonymize_text_preserves_medical_content
    NegativeCase(
        "Patient has Type 2 Diabetes and takes Metformin 500mg twice daily",
        "medication",
        ("Type 2 Diabetes", "Metformin", "500mg"),
    ),

    # DEC-006 keeps clinic names deliberately ("Doctor clinic → Keep"), and the
    # current NER path only redacts PERSON, explicitly not ORG. A detector that
    # strips the clinic is over-redacting relative to this project's policy even
    # though HIPAA Safe Harbor would treat it as an identifier — worth measuring
    # separately rather than hiding inside the aggregate.
    NegativeCase("Seen at City Medical Center", "clinic_name", ("City Medical Center",)),
    NegativeCase("Follow-up scheduled at Metro Health", "clinic_name", ("Metro Health",)),
)


ALL_CATEGORIES = tuple(
    sorted({c.category for c in POSITIVE_CASES} | {c.category for c in NEGATIVE_CASES})
)
