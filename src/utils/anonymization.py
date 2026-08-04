"""PII anonymization utilities for LLM calls.

This module provides functionality to anonymize personally identifiable information
before sending data to external LLM APIs (like Claude). It uses a combination of:
- Deterministic replacement for structured fields
- Regex patterns for common PII shapes (phone incl. international, email, SSN,
  ZIP+4, numeric/ISO/written dates, PO boxes, street addresses, and
  label-anchored medical-record and insurance identifiers)
- spaCy NER for detecting names in free-text fields

Free-text anonymization is best-effort, not a guarantee — the pattern list is
regex-based and cannot cover every real-world PII shape. See issue #92 for the
separate evaluation of a dedicated PII-detection library.

Per DEC-006:
- Patient name → omitted entirely (AnonymizedProfile has no name field at
  all, rather than substituting a placeholder like "Patient")
- Date of birth → Exact age (e.g., "39 years old")
- Emergency contact → Remove entirely
- Doctor name → "your [specialty]" or "Doctor"
- Doctor phone/email → Remove entirely
- Doctor clinic → Keep
- Prescribing doctor → "Prescribing physician"
- Conditions/medications → Keep (medically relevant)
- Free-text notes → Regex + NER scanning
"""

import re
from dataclasses import dataclass
from datetime import date
from typing import Optional

# Try to import spacy, but make it optional
try:
    import spacy
    SPACY_AVAILABLE = True
except ImportError:
    SPACY_AVAILABLE = False
    spacy = None


@dataclass
class AnonymizedProfile:
    """Anonymized health profile data ready for LLM consumption.

    Deliberately has no name field — the patient's name is omitted
    entirely rather than replaced with a placeholder string.
    """

    age_description: Optional[str]  # e.g., "39 years old"
    blood_type: Optional[str]
    allergies: Optional[str]
    conditions: list[dict]  # name, severity, status, notes (anonymized)
    medications: list[dict]  # name, dosage, frequency, purpose, side_effects (anonymized)


@dataclass
class AnonymizedDoctor:
    """Anonymized doctor data ready for LLM consumption."""

    title: str  # e.g., "your Endocrinologist" or "Doctor"
    specialty: Optional[str]
    clinic: Optional[str]  # Keep clinic name
    notes: Optional[str]  # Anonymized


@dataclass
class AnonymizedAppointment:
    """Anonymized appointment data ready for LLM consumption."""

    doctor: AnonymizedDoctor
    scheduled_date: str  # ISO format date
    purpose: Optional[str]  # Anonymized
    prep_notes: Optional[str]  # Anonymized — notes before the visit (concerns, questions to ask)
    visit_notes: Optional[str]  # Anonymized — notes during/after the visit (what was discussed, outcomes)


# Street-type suffixes recognized by the address pattern, as both the spelled-out
# form and the USPS-style abbreviation. Deliberately excludes bare nouns that are
# common in clinical prose (Park, Point, Row, Run, Path, Bend) — the false-positive
# cost there outweighs the coverage gain.
_STREET_SUFFIXES = (
    r'St|Street|Ave|Avenue|Blvd|Boulevard|Rd|Road|Dr|Drive|Ln|Lane|Way|Ct|Court'
    r'|Pl|Place|Ter|Terrace|Cir|Circle|Pkwy|Parkway|Hwy|Highway|Trl|Trail'
    r'|Sq|Square|Loop|Aly|Alley|Cres|Crescent|Plz|Plaza|Xing|Crossing'
    r'|Tpke|Turnpike|Expy|Expressway|Fwy|Freeway|Hts|Heights|Trce|Trace'
)

# Secondary address designators (apartment/unit/suite), matched only as a trailing
# part of an already-matched street address so they are redacted along with it.
_UNIT_DESIGNATORS = r'Apt|Apartment|Unit|Ste|Suite|Rm|Room|Fl|Floor|Bldg|Building'

# Month names for written-out dates, spelled-out and 3-letter abbreviated.
_MONTHS = (
    r'Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?'
    r'|Aug(?:ust)?|Sep(?:t)?(?:ember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?'
)

# Common regex patterns for PII detection.
#
# Ordering matters: `anonymize_text` applies these in declaration order, and an
# earlier pattern that matches a superset of a later one wins. In particular the
# ZIP+4 and international-phone patterns must precede `phone`, which would
# otherwise match only a fragment and leave the rest of the identifier in place.
# `mrn_unlabeled` must run last, after the label-anchored patterns, so it
# doesn't steal digits from a match that needs to keep its label.
#
# Patterns fall into three groups:
#   - *Shape* patterns (phone, email, SSN, address, dates) match the identifier
#     itself and are safe to apply unconditionally.
#   - *Labeled* patterns (MRN, insurance IDs) match a bare digit/alnum run that
#     is only identifiable as PII because of an adjacent label. These capture the
#     label in a group and keep it (see PII_REPLACEMENTS) so the redacted text
#     still reads as "MRN: [REDACTED]" rather than losing the clinical context.
#   - *Unlabeled length-band* (`mrn_unlabeled`): a bare 7-10 digit run with no
#     label at all. Narrower than "any long digit run" — see its own comment
#     below for the length band and unit-exclusion reasoning.
PII_PATTERNS = {
    # ZIP+4 and state-qualified ZIP codes. Must run first: `phone`'s 7-digit
    # branch would otherwise consume the "103-1234" of a ZIP+4 and leave a bare
    # "94" behind. A bare 5-digit ZIP is deliberately not matched — it is
    # indistinguishable from an ordinary number in clinical text.
    'zip_code': re.compile(
        r'\b\d{5}-\d{4}\b'
        r'|'
        r'\b[A-Z]{2}\s+\d{5}(?:-\d{4})?\b'
    ),
    # International / E.164-style numbers: a leading "+" country code followed by
    # at least two more digit groups. Runs before `phone` so the whole number is
    # redacted rather than just its trailing 10 digits.
    'phone_intl': re.compile(
        r'\+\d{1,3}(?:[-.\s]?\(?\d{1,5}\)?){2,6}'
    ),
    # Phone numbers (various formats)
    'phone': re.compile(
        r'(\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}'
        r'|'
        r'\d{3}[-.\s]\d{4}'  # Simple 7-digit
    ),
    # Email addresses
    'email': re.compile(
        r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    ),
    # Social Security Numbers
    'ssn': re.compile(
        r'\b\d{3}[-.\s]?\d{2}[-.\s]?\d{4}\b'
    ),
    # Numeric dates. Widened from MM/DD/YYYY-only to also cover day-first
    # (DD/MM/YYYY) ordering and 2-digit years, since a birthdate written
    # "15/06/1985" or "06/15/85" is exactly as identifying as "06/15/1985".
    # Requires all three components, so dose ranges ("25-50 mg"), ratios
    # ("120/80"), and fractions ("1/2 tablet") are left alone.
    'date': re.compile(
        r'\b\d{1,2}[/\-.]\d{1,2}[/\-.](?:19|20)?\d{2}\b'
    ),
    # ISO-8601 dates (YYYY-MM-DD).
    'date_iso': re.compile(
        r'\b(?:19|20)\d{2}-(?:0?[1-9]|1[0-2])-(?:0?[1-9]|[12]\d|3[01])\b'
    ),
    # Written-out dates ("June 15, 1985" / "15 June 1985"). Requires an explicit
    # day number, so a bare month-and-year ("follow up January 2026") stays
    # readable — that's scheduling context, not a birthdate.
    'date_written': re.compile(
        rf'\b(?:{_MONTHS})\s+\d{{1,2}}(?:st|nd|rd|th)?,?\s+(?:19|20)\d{{2}}\b'
        r'|'
        rf'\b\d{{1,2}}(?:st|nd|rd|th)?\s+(?:{_MONTHS})\s+(?:19|20)\d{{2}}\b',
        re.IGNORECASE
    ),
    # PO boxes ("P.O. Box 1234", "Post Office Box 567").
    'po_box': re.compile(
        r'\b(?:P\.?\s*O\.?|Post\s+Office)\s*Box\s*#?\s*\d+\b',
        re.IGNORECASE
    ),
    # Street addresses, with an optional trailing apartment/unit designator so
    # "742 Evergreen Terrace Apt 4B" is redacted whole rather than leaving the
    # unit number behind.
    'address': re.compile(
        rf'\b\d+\s+[A-Za-z]+(?:\s+[A-Za-z]+)*\s+(?:{_STREET_SUFFIXES})\.?'
        rf'(?:[,\s]+(?:{_UNIT_DESIGNATORS})\.?\s*#?\s*[\w-]+|[,\s]+#\s*[\w-]+)?\b',
        re.IGNORECASE
    ),
    # Medical record / chart numbers. Label-anchored (see module note above).
    'mrn': re.compile(
        r'(?P<label>\b(?:MRN|MR\s*#|Medical\s+Record\s+(?:Number|No\.?|#)?'
        r'|Record\s+(?:Number|No\.?|#)|Chart\s+(?:Number|No\.?|#))\s*[:#]?\s*)'
        r'(?=[A-Za-z0-9-]*\d)[A-Za-z]{0,3}[-\s]?\d[\d-]{3,11}\b',
        re.IGNORECASE
    ),
    # Insurance member / policy / group identifiers. Label-anchored, and the
    # value must be uppercase-alnum containing at least one digit — matching the
    # value case-insensitively would let an ordinary lowercase word ("Plan:
    # increase dose") read as an identifier.
    'insurance_id': re.compile(
        r'(?P<label>(?i:\b(?:Member|Subscriber|Policy|Group|Insurance|Plan|Beneficiary)'
        r'\s*(?:ID|No\.?|Number|#)?)\s*[:#]?\s*)'
        r'(?=[A-Z0-9-]*\d)[A-Z0-9][A-Z0-9-]{3,}\b'
    ),
    # Bare digit runs of MRN-typical length (7-10 digits) with no adjacent
    # label. Deliberately narrower than "any long digit run": most clinical
    # values that could collide (dosages, A1C, LDL/HDL, ratios) fall outside
    # this length band, and a run immediately followed by a unit is excluded
    # so vitals/labs written with a value+unit shape ("12345678 mmHg") aren't
    # caught. Six-digit values (e.g. a platelet count) are still out of range
    # and pass through untouched. Must run last: it must not steal digits from
    # a label-anchored `mrn`/`insurance_id` match, which needs its label kept.
    # Accepted false-positive risk: an unlabeled 7-10 digit clinical value with
    # no unit context will still be redacted — judged the better tradeoff on
    # DEC-006's trust boundary than leaving unlabeled MRNs uncaught.
    'mrn_unlabeled': re.compile(
        r'\b\d{7,10}\b'
        r'(?!\s*(?:mg|mcg|mL|ml|L|mmHg|bpm|kg|lbs?|%|IU|mmol(?:/L)?|mg/dL|°[CF]|units?)\b)'
    ),
}

# Per-pattern replacement templates for `re.sub`. Patterns absent from this map
# fall back to redacting the entire match. Label-anchored patterns keep their
# label so anonymized text still says what kind of identifier was removed.
PII_REPLACEMENTS = {
    'mrn': r'\g<label>[REDACTED]',
    'insurance_id': r'\g<label>[REDACTED]',
}

DEFAULT_REDACTION = '[REDACTED]'


class Anonymizer:
    """Handles PII anonymization for health data before sending to LLMs."""

    def __init__(self, use_ner: bool = True):
        """Initialize the anonymizer.

        Args:
            use_ner: Whether to use spaCy NER for name detection.
                    Falls back to regex-only if spaCy unavailable.
        """
        self.use_ner = use_ner and SPACY_AVAILABLE
        self._nlp = None

    @property
    def nlp(self):
        """Lazy-load spaCy model."""
        if self._nlp is None and self.use_ner:
            try:
                self._nlp = spacy.load("en_core_web_sm")
            except OSError:
                # Model not installed
                self.use_ner = False
                self._nlp = None
        return self._nlp

    def calculate_age(self, date_of_birth: Optional[date]) -> Optional[str]:
        """Convert date of birth to age description.

        Args:
            date_of_birth: The patient's date of birth

        Returns:
            Age description like "39 years old" or None
        """
        if not date_of_birth:
            return None

        today = date.today()
        age = today.year - date_of_birth.year

        # Adjust if birthday hasn't occurred this year
        if (today.month, today.day) < (date_of_birth.month, date_of_birth.day):
            age -= 1

        return f"{age} years old"

    def anonymize_doctor_reference(
        self,
        doctor_name: Optional[str],
        specialty: Optional[str] = None,
        context: str = "general"
    ) -> str:
        """Anonymize a doctor reference.

        Args:
            doctor_name: The doctor's name (will be removed)
            specialty: The doctor's specialty (used if available)
            context: Either "general" (→ "your [specialty]") or
                    "prescribing" (→ "Prescribing physician")

        Returns:
            Anonymized reference like "your Endocrinologist" or "Doctor"
        """
        if context == "prescribing":
            return "Prescribing physician"

        if specialty:
            return f"your {specialty}"
        return "Doctor"

    def anonymize_text(self, text: Optional[str]) -> Optional[str]:
        """Anonymize free-text by removing detected PII.

        Uses regex patterns for common PII formats, and optionally
        spaCy NER for detecting person names.

        Args:
            text: Free-text that may contain PII

        Returns:
            Anonymized text with PII replaced by [REDACTED]
        """
        if not text:
            return text

        result = text

        # Apply regex patterns in declaration order — see the ordering note on
        # PII_PATTERNS. Label-anchored patterns use a replacement template that
        # preserves their label; everything else redacts the whole match.
        for pattern_name, pattern in PII_PATTERNS.items():
            replacement = PII_REPLACEMENTS.get(pattern_name, DEFAULT_REDACTION)
            result = pattern.sub(replacement, result)

        # Apply NER if available
        if self.use_ner and self.nlp:
            doc = self.nlp(result)
            # Sort entities by start position in reverse to replace from end
            entities = sorted(doc.ents, key=lambda e: e.start_char, reverse=True)
            for ent in entities:
                if ent.label_ in ('PERSON', 'ORG'):
                    # Only redact PERSON, keep ORG (might be clinic names)
                    if ent.label_ == 'PERSON':
                        result = result[:ent.start_char] + '[REDACTED]' + result[ent.end_char:]

        return result

    def anonymize_profile(self, profile) -> AnonymizedProfile:
        """Anonymize a full health profile for LLM consumption.

        Args:
            profile: HealthProfile ORM object with loaded relationships

        Returns:
            AnonymizedProfile with PII removed
        """
        # Process conditions
        conditions = []
        for condition in getattr(profile, 'conditions', []):
            conditions.append({
                'name': condition.name,
                'severity': condition.severity,
                'status': condition.status,
                'notes': self.anonymize_text(condition.notes),
            })

        # Process medications
        medications = []
        for medication in getattr(profile, 'medications', []):
            medications.append({
                'name': medication.name,
                'dosage': medication.dosage,
                'frequency': medication.frequency,
                'purpose': medication.purpose,
                'side_effects': medication.side_effects,
                # Anonymize prescribing_doctor reference
                'prescribed_by': self.anonymize_doctor_reference(
                    medication.prescribing_doctor,
                    context="prescribing"
                ) if medication.prescribing_doctor else None,
            })

        return AnonymizedProfile(
            age_description=self.calculate_age(profile.date_of_birth),
            blood_type=profile.blood_type,
            allergies=profile.allergies,
            conditions=conditions,
            medications=medications,
        )

    def anonymize_doctor(self, doctor) -> AnonymizedDoctor:
        """Anonymize doctor information for LLM consumption.

        Args:
            doctor: Doctor ORM object

        Returns:
            AnonymizedDoctor with name/contact removed but specialty/clinic kept
        """
        return AnonymizedDoctor(
            title=self.anonymize_doctor_reference(doctor.name, doctor.specialty),
            specialty=doctor.specialty,
            clinic=doctor.clinic,  # Keep clinic name per DEC-006
            notes=self.anonymize_text(doctor.notes),
        )

    def anonymize_appointment(self, appointment) -> AnonymizedAppointment:
        """Anonymize appointment information for LLM consumption.

        Args:
            appointment: Appointment ORM object with doctor relationship loaded

        Returns:
            AnonymizedAppointment with PII removed
        """
        return AnonymizedAppointment(
            doctor=self.anonymize_doctor(appointment.doctor),
            scheduled_date=appointment.scheduled_date.isoformat() if appointment.scheduled_date else None,
            purpose=self.anonymize_text(appointment.purpose),
            prep_notes=self.anonymize_text(appointment.prep_notes),
            visit_notes=self.anonymize_text(appointment.visit_notes),
        )


# Module-level convenience function
_default_anonymizer: Optional[Anonymizer] = None


def get_anonymizer() -> Anonymizer:
    """Get or create the default anonymizer instance."""
    global _default_anonymizer
    if _default_anonymizer is None:
        _default_anonymizer = Anonymizer()
    return _default_anonymizer


def anonymize_text(text: Optional[str]) -> Optional[str]:
    """Convenience function to anonymize text using the default anonymizer."""
    return get_anonymizer().anonymize_text(text)
