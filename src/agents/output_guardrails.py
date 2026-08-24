"""Deterministic post-generation guardrails for visit-prep output (DEC-042).

Catches two hallucination shapes the LLM judge (eval/judge.py) found
concrete, repeated evidence for — presupposing a specific test/lab already
happened when it wasn't ordered, and presupposing a referral/specialist
relationship that isn't on file — without depending on any model's
instruction-following. A prompt-level fix for the same patterns (v7,
docs/notes/PROMPT_CHANGELOG.md) was tried first and measurably regressed
the rate on this project's small local default model (llama3.2:latest);
this checks the patient's actual structured data directly instead.

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

NOT covered here (see DEC-042 for why): named-external-authority claims,
fabricated numeric specifics, and unhedged "typically managed by X"
clinical-generalization claims — the last of which likely isn't
deterministically catchable at all.
"""

import re
from typing import Any

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
        r"\b(most recent|last|recent)\s+\S+\s+(test|testing|labs?)\b",
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
        r"\bshould i\b.*\b(get|ask about|request)\s+(a\s+)?(test|lab|screening)\b",
        r"\bdo i need\b.*\b(test|lab|screening)\b",
    ]
]

# Language implying an existing relationship with a specialist (a referral,
# a scheduled/schedulable follow-up with them) — as opposed to a
# cross-specialty *interaction* question, which score_scope (eval/scorers.py)
# already treats as permitted for the same reason.
_REFERRAL_RELATIONSHIP_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"\bspecialist\b",
        r"\breferral\b",
        r"\brefer(red)?\b",
        r"\bfollow-?up\s+(appointment\s+)?with\b",
        r"\bappointment with\b",
        r"\bschedule\b.*\bwith\b",
    ]
]


def _presupposes_missing_test(question: str, known_lab_names: set[str]) -> bool:
    q_lower = question.lower()
    if any(name in q_lower for name in known_lab_names):
        return False  # names a real, on-file test — not a presupposition
    if any(m.search(question) for m in _OPEN_QUESTION_MARKERS):
        return False  # phrased as an open ask, not asserting a past event
    return any(p.search(question) for p in _PRESUPPOSED_TEST_PATTERNS)


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


def apply_output_guardrails(
    questions: dict[str, list[str]],
    known_lab_names: set[str],
    known_specialty_names: set[str],
    referred_specialties: set[str],
) -> tuple[dict[str, list[str]], list[dict[str, Any]]]:
    """Strips questions presupposing a test or referral relationship not
    actually on file. Returns (filtered_questions, guardrail_events) — events
    are for logging/testing traceability, not shown to the user. A category
    that becomes empty is dropped entirely, consistent with the system
    prompt's own "never include an empty category" rule.
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
            kept.append(q)
        if kept:
            filtered[category] = kept

    return filtered, events
