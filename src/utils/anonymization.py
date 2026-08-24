"""PII anonymization utilities for LLM calls.

This module provides functionality to anonymize personally identifiable information
before sending data to external LLM APIs (like Claude). It uses a combination of:
- Deterministic replacement for structured fields
- Regex patterns for common PII shapes (phone incl. international, email, SSN,
  ZIP+4, numeric/ISO/written dates, PO boxes, street addresses, URLs, IP
  addresses, and label-anchored medical-record, insurance, license, account,
  vehicle, and device identifiers)
- spaCy NER for detecting names in free-text fields

`PII_PATTERNS` was mapped against all 18 HIPAA Safe Harbor identifier
categories (issue #122 follow-up): 16 are testable given this is a text-only
document parser (biometric identifiers and full-face photographs are out of
scope by construction — no image or biometric data is ingested); of those 16,
this module covers 15 with a dedicated or incidental pattern. Fax numbers have
no pattern of their own — they're caught by `phone`, since a fax number has no
distinguishing format. The remaining category, #18's open-ended "any other
unique identifying number or code," cannot be closed by a fixed pattern list
by definition.

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

import hashlib
import re
from contextlib import contextmanager
from contextvars import ContextVar
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
class RedactionEvent:
    """Record of a single PII match found and redacted (issue #16).

    Deliberately carries only the entity TYPE and SPAN, never the matched
    substring itself — logging the redacted value would defeat the purpose
    of anonymization (DEC-006). `entity_id` is a deterministic hash, not a
    random UUID, so repeated runs against the same underlying field produce
    the same id — see `_make_entity_id`.
    """

    entity_id: str
    entity_type: str  # PII_PATTERNS key (e.g. "phone", "mrn") or "PERSON" (NER)
    start: int  # offset into the text state the match was found against
    end: int
    field_name: str
    # Only set for fields sourced from a Document (Vitals/LabOrder/Referral/
    # FollowUp per src/data/models.py). None for everything else — including
    # Condition/Medication/Appointment, which have no document_id column at
    # all, and user-typed fields (notes, additional_concerns) which were
    # never document-sourced to begin with.
    document_id: Optional[str] = None

    def to_dict(self) -> dict:
        """Serialize for ConversationLog.extra_data.

        Uses an explicit `"document_link": "none"` rather than omitting the
        key when there's no document lineage — logging honestly that there
        is no link, rather than a key's mere absence looking like an
        oversight (issue #16).
        """
        d = {
            "entity_id": self.entity_id,
            "entity_type": self.entity_type,
            "start": self.start,
            "end": self.end,
            "field_name": self.field_name,
        }
        if self.document_id:
            d["document_id"] = self.document_id
        else:
            d["document_link"] = "none"
        return d


def _make_entity_id(
    profile_id: Optional[str],
    field_name: str,
    entity_type: str,
    occurrence_index: int,
) -> str:
    """Deterministic per-entity id: sha256((profile_id, field_name, entity_type,
    occurrence_index)), truncated. NOT a random UUID and NOT derived from the
    matched content itself — stable across repeated runs against the same
    underlying field, which is the whole point (issue #16).
    """
    key = f"{profile_id}|{field_name}|{entity_type}|{occurrence_index}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]


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
    # HIPAA Safe Harbor #14: web URLs. A patient-portal or telehealth-room link
    # is as identifying as the account it points to.
    'url': re.compile(
        r'https?://[^\s<>"]+', re.IGNORECASE
    ),
    # HIPAA Safe Harbor #15: IPv4 addresses (octet-bounded, not "any 4 dotted
    # numbers", so this doesn't collide with anything dose/lab-shaped — nothing
    # else in clinical text is written as three dots between 0-255 values).
    'ip_address': re.compile(
        r'\b(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)\b'
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
    # HIPAA Safe Harbor #11: certificate/license numbers. Label-anchored on
    # "License"/"DEA" specifically — a bare "Certificate" trigger was tested
    # and dropped: it also matches non-identifying document types ("Certificate
    # of medical necessity") and insurance authorization numbers ("Prior
    # authorization Certificate #: PA-991244"), which would over-redact
    # clinical/billing content DEC-006 means to keep. "License"/"DEA" alone
    # had zero false positives against an 88-case adversarial negative sweep.
    'license_number': re.compile(
        r'(?P<label>\b(?:Driver.?s?\s+License|License|DEA)'
        r'\s*(?:Number|No\.?|#)?\s*[:#]?\s*)'
        r'(?=[A-Z0-9-]*\d)[A-Z0-9][A-Z0-9-]{3,}\b',
        re.IGNORECASE
    ),
    # HIPAA Safe Harbor #10: generic account numbers. Distinct from
    # `insurance_id` because "Account" isn't in that pattern's label list —
    # without this, only the pattern-length-collision with `mrn_unlabeled`
    # incidentally caught an account number's digit portion, and only when it
    # had no alphanumeric prefix ("Account #: AB-9284710" redacted to
    # "Account #: AB-[REDACTED]", leaking "AB-").
    'account_number': re.compile(
        r'(?P<label>\bAccount\s*(?:Number|No\.?|#)?\s*[:#]?\s*)'
        r'(?=[A-Z0-9-]*\d)[A-Z0-9][A-Z0-9-]{3,}\b',
        re.IGNORECASE
    ),
    # HIPAA Safe Harbor #12: vehicle identifiers. Narrow on purpose — only a
    # VIN with an explicit "VIN" label, not a bare 11-17 char alnum run, which
    # would be far too broad a net over ordinary clinical text.
    'vehicle_id': re.compile(
        r'(?P<label>\bVIN\s*[:#]?\s*)[A-HJ-NPR-Z0-9]{11,17}\b',
        re.IGNORECASE
    ),
    # HIPAA Safe Harbor #13: device identifiers/serial numbers. The negative
    # lookbehind on "Lot"/"Batch" is load-bearing: a medication/vaccine lot or
    # batch number identifies a manufacturing run, not an individual, and
    # "Batch Serial: LOT-88213" would otherwise over-redact it — found during
    # adversarial testing, not anticipated up front.
    'device_serial': re.compile(
        r'(?P<label>\b(?<!Lot\s)(?<!Batch\s)(?:Device\s+)?Serial'
        r'\s*(?:Number|No\.?|#)?\s*[:#]?\s*)[A-Z0-9-]{4,}\b',
        re.IGNORECASE
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
    'license_number': r'\g<label>[REDACTED]',
    'account_number': r'\g<label>[REDACTED]',
    'vehicle_id': r'\g<label>[REDACTED]',
    'device_serial': r'\g<label>[REDACTED]',
}

DEFAULT_REDACTION = '[REDACTED]'

# Token type per PII_PATTERNS key, for scoped tokenisation (issue #17). Both MRN
# patterns share a type on purpose: the same identifier written with a label in
# one field and bare in another is one entity, and tokens key on the matched
# value, not on which pattern happened to catch it.
TOKEN_TYPES = {
    'zip_code': 'ZIP',
    'phone_intl': 'PHONE',
    'phone': 'PHONE',
    'email': 'EMAIL',
    'ssn': 'SSN',
    'url': 'URL',
    'ip_address': 'IP_ADDRESS',
    'date': 'DATE',
    'date_iso': 'DATE',
    'date_written': 'DATE',
    'po_box': 'ADDRESS',
    'address': 'ADDRESS',
    'mrn': 'MRN',
    'insurance_id': 'INSURANCE_ID',
    'license_number': 'LICENSE_NUMBER',
    'account_number': 'ACCOUNT_NUMBER',
    'vehicle_id': 'VEHICLE_ID',
    'device_serial': 'DEVICE_SERIAL',
    'mrn_unlabeled': 'MRN',
    'PERSON': 'PERSON',
}

# Matches any token this module can emit, for the output-side leakage guard.
TOKEN_PATTERN = re.compile(
    r'\b(?:' + '|'.join(sorted(set(TOKEN_TYPES.values()))) + r')_\d+\b'
)

# Titles stripped before two mentions are compared. Deliberately short: exact
# normalised matching only, no coreference resolution and nothing fuzzier (see
# `_normalise_entity_value`).
_TITLE_PREFIXES = (
    'dr', 'dr.', 'doctor', 'mr', 'mr.', 'mrs', 'mrs.', 'ms', 'ms.',
    'miss', 'prof', 'prof.', 'professor',
)


def _normalise_entity_value(value: str) -> str:
    """Normalise a matched value so two mentions of one entity collapse to one
    token — casefold, drop a leading title, strip surrounding punctuation and
    collapse internal whitespace.

    Deliberately conservative (issue #17, Q3). A wrong *merge* is worse than
    today's behaviour: today the model learns nothing about the relationship
    between two redacted mentions; a bad merge would actively tell it two
    different providers are the same person. Under-merging just degrades to
    roughly today's state for the mentions that didn't merge, which is the safe
    failure direction — so no fuzzy matching, no surname-only equivalence beyond
    title stripping, no coreference.
    """
    cleaned = re.sub(r'\s+', ' ', value).strip().strip('.,;:#-').casefold()
    parts = cleaned.split(' ')
    if len(parts) > 1 and parts[0] in _TITLE_PREFIXES:
        parts = parts[1:]
    return ' '.join(parts).strip()


class _TokenScope:
    """The value → token map for one logical unit of anonymization."""

    def __init__(self) -> None:
        self._tokens: dict[tuple[str, str], str] = {}
        self._counts: dict[str, int] = {}

    def token_for(self, token_type: str, value: str) -> str:
        key = (token_type, _normalise_entity_value(value))
        existing = self._tokens.get(key)
        if existing is not None:
            return existing
        index = self._counts.get(token_type, 0) + 1
        self._counts[token_type] = index
        token = f"{token_type}_{index}"
        self._tokens[key] = token
        return token

    def as_dict(self) -> dict[str, str]:
        """Token → normalised source value, for tests and diagnostics only.

        Never logged and never returned to a caller outside the process: the
        values here are the raw PII the scope exists to keep off the wire.
        """
        return {token: value for (_, value), token in self._tokens.items()}


# Scope state lives in a ContextVar, not on the Anonymizer instance, so the
# module-level singleton behind `anonymize_text()` can never accumulate a
# cross-patient map: each asyncio task (i.e. each request) gets its own copy of
# the context, and a scope opened in one is invisible to every other.
_active_token_scope: ContextVar[Optional[_TokenScope]] = ContextVar(
    'anonymizer_token_scope', default=None
)


def current_token_scope() -> Optional[_TokenScope]:
    """The token scope in effect for this task, or None outside a scope."""
    return _active_token_scope.get()


@contextmanager
def token_scope():
    """Give per-entity tokens (`PERSON_1`, `MRN_1`) to everything anonymized
    inside this block, consistent across every `anonymize_text()` call in it.

    Outside a scope, redaction behaviour is byte-for-byte what it has always
    been: every match becomes `[REDACTED]`. Tokenisation is opt-in per call
    site so no existing caller changes behaviour by accident (issue #17).
    """
    token = _active_token_scope.set(_TokenScope())
    try:
        yield _active_token_scope.get()
    finally:
        _active_token_scope.reset(token)


def scrub_leaked_tokens(text: Optional[str]) -> Optional[str]:
    """Rewrite any token that survived into model output back to `[REDACTED]`.

    The leakage guard for issue #17: a model handed `PERSON_1` in its input can
    echo it verbatim in a generated question, which would look broken. This
    rewrites stray tokens to the neutral marker the app already shows for
    redacted content, so the worst case is exactly today's behaviour rather
    than an opaque identifier.

    Deliberately *not* re-hydration — nothing here maps a token back to the
    real value it stood for. Whether tokens should be re-hydrated for the
    patient's own eyes is still open on #17; this guard is compatible with
    either answer, since re-hydration would run first and this would catch
    whatever it couldn't map.
    """
    if not text:
        return text
    return TOKEN_PATTERN.sub(DEFAULT_REDACTION, text)


def _replacement_for(pattern_name: str, scope: Optional[_TokenScope]):
    """The `re.sub` replacement for one pattern — a template outside a scope,
    a per-match token-minting function inside one.

    Label-anchored patterns keep their label either way, so anonymized text
    still reads as `MRN: MRN_1` rather than losing the clinical context. The
    token is keyed on the identifier alone, without the label, so the same MRN
    written `MRN: 1234567` in one field and bare in another is one entity.
    """
    if scope is None:
        return PII_REPLACEMENTS.get(pattern_name, DEFAULT_REDACTION)

    token_type = TOKEN_TYPES.get(pattern_name, pattern_name.upper())

    def replace(match: 're.Match') -> str:
        label = ''
        value = match.group(0)
        if 'label' in match.re.groupindex and match.group('label'):
            label = match.group('label')
            value = value[len(label):]
        return label + scope.token_for(token_type, value)

    return replace


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

    def anonymize_text(
        self,
        text: Optional[str],
        *,
        profile_id: Optional[str] = None,
        field_name: str = "",
        document_id: Optional[str] = None,
    ) -> tuple[Optional[str], list[RedactionEvent]]:
        """Anonymize free-text by removing detected PII.

        Uses regex patterns for common PII formats, and optionally
        spaCy NER for detecting person names.

        Args:
            text: Free-text that may contain PII
            profile_id: HealthProfile id the text belongs to, used only to
                derive stable per-entity ids (issue #16) — never logged raw.
            field_name: Identifier for which field this is (e.g.
                "condition:<id>:notes"), also only used for entity-id
                derivation and as the `field_name` on each RedactionEvent.
            document_id: Document this field was sourced from, if any. Only
                Vitals/LabOrder/Referral/FollowUp have document lineage —
                see RedactionEvent's docstring.

        Returns:
            (anonymized_text, redaction_events) — events carry only entity
            type + span, never the matched substring (DEC-006).
        """
        if not text:
            return text, []

        result = text
        events: list[RedactionEvent] = []
        occurrence_counts: dict[str, int] = {}
        scope = current_token_scope()

        # Apply regex patterns in declaration order — see the ordering note on
        # PII_PATTERNS. Label-anchored patterns use a replacement template that
        # preserves their label; everything else redacts the whole match.
        for pattern_name, pattern in PII_PATTERNS.items():
            replacement = _replacement_for(pattern_name, scope)
            for match in pattern.finditer(result):
                idx = occurrence_counts.get(pattern_name, 0)
                occurrence_counts[pattern_name] = idx + 1
                events.append(RedactionEvent(
                    entity_id=_make_entity_id(profile_id, field_name, pattern_name, idx),
                    entity_type=pattern_name,
                    start=match.start(),
                    end=match.end(),
                    field_name=field_name,
                    document_id=document_id,
                ))
            result = pattern.sub(replacement, result)

        # Apply NER if available
        if self.use_ner and self.nlp:
            doc = self.nlp(result)
            person_entities = [e for e in doc.ents if e.label_ == 'PERSON']
            # Record events in left-to-right order for stable occurrence
            # indices, then replace from the end so earlier offsets stay valid.
            for ent in sorted(person_entities, key=lambda e: e.start_char):
                idx = occurrence_counts.get('PERSON', 0)
                occurrence_counts['PERSON'] = idx + 1
                events.append(RedactionEvent(
                    entity_id=_make_entity_id(profile_id, field_name, 'PERSON', idx),
                    entity_type='PERSON',
                    start=ent.start_char,
                    end=ent.end_char,
                    field_name=field_name,
                    document_id=document_id,
                ))
            for ent in sorted(person_entities, key=lambda e: e.start_char, reverse=True):
                # Replaced right-to-left so earlier offsets stay valid, but the
                # token is assigned by value, so a repeated name still collapses
                # to one token regardless of the order they're rewritten in.
                person = (
                    scope.token_for('PERSON', ent.text) if scope
                    else DEFAULT_REDACTION
                )
                result = result[:ent.start_char] + person + result[ent.end_char:]

        return result, events

    def anonymize_profile(self, profile) -> tuple[AnonymizedProfile, list[RedactionEvent]]:
        """Anonymize a full health profile for LLM consumption.

        Args:
            profile: HealthProfile ORM object with loaded relationships

        Returns:
            (AnonymizedProfile with PII removed, aggregated RedactionEvents)
        """
        profile_id = getattr(profile, 'id', None)
        events: list[RedactionEvent] = []

        # Process conditions. Condition has no document_id column (per
        # src/data/models.py) so these events are always "no document link".
        conditions = []
        for condition in getattr(profile, 'conditions', []):
            notes, notes_events = self.anonymize_text(
                condition.notes,
                profile_id=profile_id,
                field_name=f"condition:{condition.id}:notes",
            )
            events.extend(notes_events)
            conditions.append({
                'name': condition.name,
                'severity': condition.severity,
                'status': condition.status,
                'notes': notes,
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
        ), events

    def anonymize_doctor(self, doctor) -> tuple[AnonymizedDoctor, list[RedactionEvent]]:
        """Anonymize doctor information for LLM consumption.

        Args:
            doctor: Doctor ORM object

        Returns:
            (AnonymizedDoctor with name/contact removed but specialty/clinic
            kept, RedactionEvents). Doctor has no document_id column, so
            events are always "no document link".
        """
        notes, events = self.anonymize_text(
            doctor.notes,
            profile_id=getattr(doctor, 'profile_id', None),
            field_name=f"doctor:{doctor.id}:notes",
        )
        return AnonymizedDoctor(
            title=self.anonymize_doctor_reference(doctor.name, doctor.specialty),
            specialty=doctor.specialty,
            clinic=doctor.clinic,  # Keep clinic name per DEC-006
            notes=notes,
        ), events

    def anonymize_appointment(self, appointment) -> tuple[AnonymizedAppointment, list[RedactionEvent]]:
        """Anonymize appointment information for LLM consumption.

        Args:
            appointment: Appointment ORM object with doctor relationship loaded

        Returns:
            (AnonymizedAppointment with PII removed, aggregated
            RedactionEvents). Appointment has no document_id column, so
            events are always "no document link".
        """
        events: list[RedactionEvent] = []
        doctor, doctor_events = self.anonymize_doctor(appointment.doctor)
        events.extend(doctor_events)

        profile_id = getattr(appointment, 'profile_id', None)
        purpose, purpose_events = self.anonymize_text(
            appointment.purpose, profile_id=profile_id,
            field_name=f"appointment:{appointment.id}:purpose",
        )
        prep_notes, prep_events = self.anonymize_text(
            appointment.prep_notes, profile_id=profile_id,
            field_name=f"appointment:{appointment.id}:prep_notes",
        )
        visit_notes, visit_events = self.anonymize_text(
            appointment.visit_notes, profile_id=profile_id,
            field_name=f"appointment:{appointment.id}:visit_notes",
        )
        events.extend(purpose_events)
        events.extend(prep_events)
        events.extend(visit_events)

        return AnonymizedAppointment(
            doctor=doctor,
            scheduled_date=appointment.scheduled_date.isoformat() if appointment.scheduled_date else None,
            purpose=purpose,
            prep_notes=prep_notes,
            visit_notes=visit_notes,
        ), events


# Module-level convenience function
_default_anonymizer: Optional[Anonymizer] = None


def get_anonymizer() -> Anonymizer:
    """Get or create the default anonymizer instance."""
    global _default_anonymizer
    if _default_anonymizer is None:
        _default_anonymizer = Anonymizer()
    return _default_anonymizer


def anonymize_text(
    text: Optional[str],
    *,
    profile_id: Optional[str] = None,
    field_name: str = "",
    document_id: Optional[str] = None,
) -> tuple[Optional[str], list[RedactionEvent]]:
    """Convenience function to anonymize text using the default anonymizer."""
    return get_anonymizer().anonymize_text(
        text, profile_id=profile_id, field_name=field_name, document_id=document_id
    )
