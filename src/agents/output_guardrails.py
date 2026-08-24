"""Deterministic post-generation guardrails for visit-prep output (DEC-042).

Catches hallucination shapes the LLM judge (eval/judge.py) found concrete,
repeated evidence for — presupposing a specific test/lab result, referral
relationship, or additional medication that isn't in the patient's actual
structured data — without depending on any model's instruction-following.
A prompt-level fix for the same patterns (v7, docs/notes/PROMPT_CHANGELOG.md)
was tried first and measurably regressed the rate on this project's small
local default model (llama3.2:latest); this checks structured data directly
instead. Extended after the first validated pass's own residual claims
(DEC-042's second addendum) surfaced two more instances of the same shape.

Regex/keyword-based, same style as src/utils/anonymization.py — cheap,
auditable, deliberately narrow rather than an attempt at general claim
verification. Known limitation, same shape as anonymization.py's
documented gaps: these are phrase-pattern matches, not semantic
understanding — a genuinely novel phrasing of either pattern can slip
through, and a legitimate question using similar wording could in
principle be filtered. Flagged questions are stripped, not rewritten —
rewriting would require either another LLM call (defeats the point of a
deterministic filter) or a templated rewrite risking its own wrongness;
a stripped question just doesn't appear, which is a safe failure mode.

Checks both the generated questions AND context_summary (added after
DEC-042's real-run breakdown showed the majority of remaining unsupported
claims lived in context_summary, which earlier versions of this filter
never touched at all) — a specialty-management-convention claim ("which is
typically managed by Pulmonology") and a named-external-authority claim
("the American Thyroid Association's guidelines") are both, per the LLM
judge's own rubric (eval/judge.py), ALWAYS unsupported regardless of
phrasing, since this app has no source anywhere for either — so both are
safe to always strip, not just when a structured-data lookup says so.

NOT covered here (see DEC-042 for why): fabricated numeric specifics
(dosages/dates not on file) and a specific patient age/demographic claim
(the schema supports date_of_birth but eval fixtures never populate one,
same "needs new fixture plumbing + a policy decision" shape as the
deferred medication-start_date/"starting point" check).
"""

import re
from typing import Any, Optional

# Phrases that presuppose a specific test/lab already occurred and produced
# results, as opposed to an open question ("are there any tests I should ask
# about"), which is fine regardless of what's on file.
_PRESUPPOSED_TEST_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"\bresults? of\b",
        r"\bresults? from\b",
        r"\bwere the results\b",
        r"\bprevious results\b",
        r"\bcompare(d)?\s+to\s+(previous|prior|earlier)\b",
        r"\brecent lab trends?\b",
        r"\b(most recent|last|recent)\s+\S+\s+(tests?|testing|labs?)\b",
    ]
]

# If a question is phrased as an open/hypothetical ask about tests/labs
# specifically, it doesn't presuppose a past event even if it also contains
# a presupposition-pattern word elsewhere in the sentence — checked first,
# takes priority over the patterns above. Deliberately narrow ("are there
# any tests", not bare "are there any") — a bare marker matched unrelated
# clauses like "...and are there any concerns", which favors under-
# triggering the wrong direction (missing genuine presuppositions) rather
# than the intended one (not over-stripping legitimate open questions).
_OPEN_QUESTION_MARKERS = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"\bare there any\s+(tests?|labs?|screenings?)\b",
        r"\bshould i\b.*\b(get|ask about|request)\s+(a\s+)?(tests?|labs?|screenings?)\b",
        r"\bdo i need\b.*\b(tests?|labs?|screenings?)\b",
    ]
]

# Language implying an existing relationship with a specialist (a referral,
# a scheduled/schedulable follow-up with them) — as opposed to a
# cross-specialty *interaction* question, which score_scope (eval/scorers.py)
# already treats as permitted for the same reason.
_REFERRAL_RELATIONSHIP_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in [
        # \bspecialist\b (no plural) silently failed to match "specialists" —
        # \b requires a word boundary immediately after "specialist", but
        # the plural's trailing "s" is itself a word character, so there's
        # no boundary there. Found via a real recurring case this exact
        # plural phrasing ("referrals or specialists... such as
        # Pulmonology") that should have been stripped but wasn't.
        r"\bspecialists?\b",
        r"\breferrals?\b",
        r"\brefer(red)?\b",
        r"\bfollow-?up\s+(appointment\s+)?with\b",
        r"\bappointment with\b",
        r"\bschedule\b.*\bwith\b",
    ]
]


# Distinct from _PRESUPPOSED_TEST_PATTERNS: this project's LabOrder model
# (src/data/models.py) tracks that a test was ordered, but has NO result
# field at all — a result value is never stored anywhere in this schema.
# So a claim asserting a specific result/level/value is unsupported by
# construction regardless of whether the test's name matches something on
# file (found via DEC-042's second addendum: "based on the recent TSH
# levels" was wrongly treated as grounded by _presupposes_missing_test
# because "TSH" itself is a real, ordered test — but no TSH *level* exists
# anywhere to base anything on). Matched independently of known_lab_names
# for exactly that reason.
_PRESUPPOSED_RESULT_VALUE_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"\blevels?\s+(are|show|indicate)\b",
        r"\bbased on\b.{0,40}\b(levels?|results?)\b",
        r"\bresults?\s+(show|indicate|suggest)\b",
        # "What are my current A1C and TSH levels?" — found via DEC-042's
        # judge-v2 re-run: presupposes a result value exists ("current...
        # levels") without using "recent"/"most recent"/"last", which
        # _PRESUPPOSED_TEST_PATTERNS's temporal-qualifier check requires.
        r"\bcurrent\b.{0,40}\blevels?\b",
    ]
]


def _presupposes_missing_test(question: str, known_lab_names: set[str]) -> bool:
    if any(p.search(question) for p in _PRESUPPOSED_RESULT_VALUE_PATTERNS):
        if not any(m.search(question) for m in _OPEN_QUESTION_MARKERS):
            return True

    q_lower = question.lower()
    if any(name in q_lower for name in known_lab_names):
        return False  # names a real, on-file test — not a presupposition
    if any(m.search(question) for m in _OPEN_QUESTION_MARKERS):
        return False  # phrased as an open ask, not asserting a past event
    return any(p.search(question) for p in _PRESUPPOSED_TEST_PATTERNS)


# Phrases presupposing medications exist beyond what's actually on file —
# "other"/"additional" medications when the patient has at most one listed,
# or a bare "medications are prescribed" claim when none are listed at all.
_OTHER_MEDICATIONS_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"\bother medications?\b",
        r"\badditional medications?\b",
    ]
]
_MEDICATIONS_PRESCRIBED_PATTERN = re.compile(r"\bmedications?\s+(is|are)\s+prescribed\b", re.IGNORECASE)


def _presupposes_missing_medication(question: str, known_medication_count: int) -> bool:
    if any(p.search(question) for p in _OTHER_MEDICATIONS_PATTERNS) and known_medication_count <= 1:
        return True
    if _MEDICATIONS_PRESCRIBED_PATTERN.search(question) and known_medication_count == 0:
        return True
    return False


# "since my last visit" / "at my last visit" presupposes a prior visit
# occurred at all — found via a real, deterministic recurring case
# (cold_start, zero past visits surfaced in context) where this phrasing
# survived every other check untouched.
_PAST_VISIT_PATTERN = re.compile(r"\b(since|at|during)\s+my\s+(last|previous)\s+visit\b", re.IGNORECASE)


def _presupposes_missing_past_visit(question: str, known_past_visit_count: int) -> bool:
    return bool(_PAST_VISIT_PATTERN.search(question)) and known_past_visit_count == 0


def _presupposes_missing_referral(
    question: str, known_specialty_names: set[str], referred_specialties: set[str]
) -> str | None:
    """Returns the presupposed specialty name if found, else None."""
    if not any(p.search(question) for p in _REFERRAL_RELATIONSHIP_PATTERNS):
        return None
    q_lower = question.lower()
    for specialty in known_specialty_names:
        if specialty.lower() in q_lower and specialty.lower() not in referred_specialties:
            return specialty
    return None


# A "typically/usually/commonly managed by X" claim asserts a general
# clinical-specialty-assignment convention this app has no source for
# anywhere (no clinical-knowledge database, nothing in the patient's own
# record could ever state a general convention like this) — always
# unsupported regardless of which specialty follows or whether the patient
# happens to see that specialty for real. Matches the LLM judge's own
# rubric (eval/judge.py), which names this exact claim type as always-
# unsupported. Found via the original ad hoc manual review AND confirmed
# still recurring in every live judge run since (DEC-042).
_SPECIALTY_CONVENTION_PATTERN = re.compile(
    r"\b(typically|usually|commonly|generally)\s+(managed|treated|handled)\s+by\b", re.IGNORECASE
)

# A named external authority/guideline reference ("American Thyroid
# Association guidelines", "ATA guidelines") is unsupported the same way —
# this app has no source for any external clinical guideline's content.
# Two shapes: a multi-word capitalized organization name (2-4 title-case
# words) immediately before "guidelines"/"recommendations", or a short
# all-caps acronym (2-6 letters) in the same position. Requiring 2+
# capitalized words (not 1) deliberately excludes a sentence-initial "The
# guidelines..." — capitalized only because it starts the sentence, not
# because it names anything specific.
_NAMED_AUTHORITY_PATTERNS = [
    re.compile(p)
    for p in [
        # Tolerates a parenthetical acronym between the full name and
        # "guidelines" (e.g. "American Thyroid Association (ATA)
        # guidelines") — found via a real recurring case where the bare
        # version of this pattern required the capitalized name
        # immediately before "guidelines" with nothing in between, so the
        # parenthesized acronym broke the match entirely.
        r"\b(?:[A-Z][a-zA-Z]*\s+){2,4}(?:\([A-Z]{2,6}\)\s+)?(?:guidelines?|recommendations?)\b",
        r"\b[A-Z]{2,6}\s+(?:guidelines?|recommendations?)\b",
    ]
]


def _presupposes_specialty_convention_or_named_authority(text: str) -> Optional[str]:
    """Returns the matched reason ("specialty_convention" or
    "named_authority") if text asserts either, else None."""
    if _SPECIALTY_CONVENTION_PATTERN.search(text):
        return "specialty_convention"
    if any(p.search(text) for p in _NAMED_AUTHORITY_PATTERNS):
        return "named_authority"
    return None


def _filter_free_text(text: str) -> tuple[str, list[dict[str, Any]]]:
    """Applies the specialty-convention/named-authority check to context_summary
    (free text, not a discrete list like questions) by splitting into
    sentences and dropping only the offending ones — same "strip, don't
    rewrite" posture as the question-level checks, at sentence granularity
    since blanking the whole summary over one bad sentence would lose
    otherwise-good content unnecessarily. Simple '. ' splitting, not
    grammar-aware — same pragmatic-regex tradeoff as the rest of this
    module; a mid-sentence period (an abbreviation) could split wrong, but
    the failure mode is at worst an oddly-broken sentence, not lost safety.
    """
    if not text:
        return text, []
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    kept = []
    events = []
    for s in sentences:
        reason = _presupposes_specialty_convention_or_named_authority(s)
        if reason:
            events.append({"sentence": s, "reason": reason})
            continue
        kept.append(s)
    return " ".join(kept), events


def apply_output_guardrails(
    questions: dict[str, list[str]],
    known_lab_names: set[str],
    known_specialty_names: set[str],
    referred_specialties: set[str],
    known_medication_count: int = 0,
    context_summary: str = "",
    known_past_visit_count: int = 0,
) -> tuple[dict[str, list[str]], str, list[dict[str, Any]]]:
    """Strips questions presupposing a test/result, referral relationship, or
    additional medication not actually on file, plus a specialty-management-
    convention or named-external-authority claim anywhere (questions or
    context_summary). Returns (filtered_questions, filtered_context_summary,
    guardrail_events) — events are for logging/testing traceability, not
    shown to the user. A category that becomes empty is dropped entirely,
    consistent with the system prompt's own "never include an empty
    category" rule.
    """
    filtered: dict[str, list[str]] = {}
    events: list[dict[str, Any]] = []

    for category, items in questions.items():
        kept = []
        for q in items or []:
            if _presupposes_missing_test(q, known_lab_names):
                events.append({"category": category, "question": q, "reason": "presupposed_test"})
                continue
            specialty = _presupposes_missing_referral(q, known_specialty_names, referred_specialties)
            if specialty:
                events.append(
                    {"category": category, "question": q, "reason": "presupposed_referral", "specialty": specialty}
                )
                continue
            if _presupposes_missing_medication(q, known_medication_count):
                events.append({"category": category, "question": q, "reason": "presupposed_medication"})
                continue
            if _presupposes_missing_past_visit(q, known_past_visit_count):
                events.append({"category": category, "question": q, "reason": "presupposed_past_visit"})
                continue
            reason = _presupposes_specialty_convention_or_named_authority(q)
            if reason:
                events.append({"category": category, "question": q, "reason": reason})
                continue
            kept.append(q)
        if kept:
            filtered[category] = kept

    filtered_summary, summary_events = _filter_free_text(context_summary)
    for e in summary_events:
        events.append({"category": "Context Summary", "question": e["sentence"], "reason": e["reason"]})

    return filtered, filtered_summary, events
