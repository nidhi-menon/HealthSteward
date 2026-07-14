"""PII anonymization utilities for LLM calls.

This module provides functionality to anonymize personally identifiable information
before sending data to external LLM APIs (like Claude). It uses a combination of:
- Deterministic replacement for structured fields
- Regex patterns for common PII patterns (phone, email, SSN)
- spaCy NER for detecting names in free-text fields

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


@dataclass
class AnonymizedAppointment:
    """Anonymized appointment data ready for LLM consumption."""

    doctor: AnonymizedDoctor
    scheduled_date: str  # ISO format date
    purpose: Optional[str]  # Anonymized
    visit_notes: Optional[str]  # Anonymized


# Common regex patterns for PII detection
PII_PATTERNS = {
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
    # Dates that might be birthdates (MM/DD/YYYY, MM-DD-YYYY, etc.)
    'date': re.compile(
        r'\b(?:0?[1-9]|1[0-2])[/\-.](?:0?[1-9]|[12]\d|3[01])[/\-.](?:19|20)\d{2}\b'
    ),
    # Street addresses (simplified pattern)
    'address': re.compile(
        r'\b\d+\s+[A-Za-z]+(?:\s+[A-Za-z]+)*\s+(?:St|Street|Ave|Avenue|Blvd|Boulevard|Rd|Road|Dr|Drive|Ln|Lane|Way|Ct|Court|Pl|Place)\.?\b',
        re.IGNORECASE
    ),
}


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

        # Apply regex patterns
        for pattern_name, pattern in PII_PATTERNS.items():
            result = pattern.sub('[REDACTED]', result)

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
