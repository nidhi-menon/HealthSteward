"""Deterministic scorers for visit-prep generation output (issue #29, v1).

Every function here is a pure, no-LLM-involved check — the whole point of
v1 is a fast, reproducible smoke test that doesn't depend on a second
model's judgment. See eval/__init__.py for what this deliberately does and
doesn't measure.
"""

import re
from typing import Any, Optional

from eval.fixtures import EvalCase
from src.utils.context_selection import are_specialties_related

KNOWN_CATEGORIES = {
    "Condition Management",
    "Medication Review",
    "Lab Results & Monitoring",
    "Lifestyle & Prevention",
    "Follow-up Planning",
}


def _all_questions(result: dict[str, Any]) -> list[tuple[str, str]]:
    """Flatten {category: [questions]} into [(category, question_text)]."""
    pairs = []
    for category, questions in (result.get("questions") or {}).items():
        for q in questions or []:
            pairs.append((category, q))
    return pairs


def expected_min_questions(case: EvalCase) -> int:
    """Scale the expected minimum question count with how much *in-scope* data
    a case actually has, rather than enforcing a fixed 8 for every case.

    Found via #29's first real runs: cold_start (one condition, nothing
    else) failing the fixed 8-question floor was in tension with the
    system prompt's own anti-hallucination rules — pushing the model to
    invent content just to hit a fixed number for a case with genuinely
    little to ask about isn't a real quality bar. 2 questions per known
    entity, floor of 3, capped at the prompt's own stated 8, is a rough
    but principled scale-down for sparse cases; richer cases still expect
    the full 8.

    Counts in_scope_entities, not known_entities (issue #75, DEC-033):
    cross_specialty_scope has 4 entities but half of them are the
    dermatology material the prompt explicitly forbids discussing at an
    endocrinology visit, so counting all 4 produced a full floor of 8 for
    a case with only 2 things it's actually allowed to ask about — the
    same data-sparsity as cold_start, hidden behind a healthy-looking
    entity count.
    """
    return min(8, max(3, len(in_scope_entities(case)) * 2))


def score_format(result: dict[str, Any], min_questions: int = 8) -> dict[str, Any]:
    """Format validity: valid JSON shape, min_questions-15 questions, known categories, none empty."""
    questions = result.get("questions")
    issues = []

    if not isinstance(questions, dict):
        return {"valid": False, "question_count": 0, "issues": ["'questions' is not a dict"]}

    total = sum(len(v or []) for v in questions.values())
    if not (min_questions <= total <= 15):
        issues.append(f"question count {total} outside {min_questions}-15")

    for category, qs in questions.items():
        if category not in KNOWN_CATEGORIES:
            issues.append(f"unknown category: {category!r}")
        if not qs:
            issues.append(f"empty category: {category!r}")

    return {"valid": not issues, "question_count": total, "issues": issues}


def known_entities(case: EvalCase) -> set[str]:
    """Entity names (lowercased) that a grounded question is allowed to reference.

    Deliberately *not* scope-aware, and deliberately not narrowed to match
    in_scope_entities (issue #75): score_groundedness asks "did the model
    invent this?", which is a different question from "should the model
    have brought this up?". Dropping the off-scope dermatology medication
    here would make a question about Clobetasol read as ungrounded — a
    hallucination — when it's a real entity from the patient's own record
    that score_scope already catches, correctly, as a scope violation.
    Conflating the two would double-count one failure and destroy the
    scope checker's own signal.
    """
    entities = {c.name.lower() for c in case.conditions}
    entities |= {m.name.lower() for m in case.medications}
    entities |= {lab.test_name.lower() for lab in case.lab_orders}
    return entities


def in_scope_entities(case: EvalCase) -> set[str]:
    """Entity names (lowercased) the model is legitimately *expected* to ask
    about at this case's target visit — i.e. known_entities minus anything
    the prompt's cross-specialty rules forbid discussing.

    Used only for the question-count floor (expected_min_questions), never
    for groundedness. Scope is read the same way each entity type already
    encodes it:

    - Medications carry prescribing_doctor_key, so their specialty is
      resolvable and compared to the target doctor's via the same
      are_specialties_related() the runtime scope logic uses. A medication
      with no prescriber, or one whose prescriber has no specialty, counts
      as in scope — absence of a scope signal isn't evidence of being off
      scope, and defaulting the other way would silently deflate the floor.
    - Conditions have no doctor link and nothing structural marks them as
      one specialty's, so the fixture states its own intent via
      ConditionFixture.in_scope rather than having this function guess
      from icd_10. Deriving it from ICD10_SPECIALTY_MAP was the
      alternative, and was rejected: that map is the hand-authored surface
      #72/#74 are mid-consolidation on, and coupling the eval harness's
      floor to it would inherit that debt. See DEC-033.
    - Lab orders are always counted: they're ordered for this profile and
      nothing in the fixtures ties one to a non-target specialty.
    """
    doctors_by_key = {d.key: d for d in case.doctors}
    target_doctor = doctors_by_key.get(case.target_doctor_key)
    target_specialty = target_doctor.specialty if target_doctor else None

    entities = {c.name.lower() for c in case.conditions if c.in_scope}

    for med in case.medications:
        prescriber = doctors_by_key.get(med.prescribing_doctor_key) if med.prescribing_doctor_key else None
        prescriber_specialty = prescriber.specialty if prescriber else None
        if (
            target_specialty
            and prescriber_specialty
            and not are_specialties_related(target_specialty, prescriber_specialty)
        ):
            continue
        entities.add(med.name.lower())

    entities |= {lab.test_name.lower() for lab in case.lab_orders}
    return entities


def score_groundedness(result: dict[str, Any], entities: set[str]) -> dict[str, Any]:
    """Cheap entity-match pass: does each question reference at least one real entity.

    This is the "smoke test" version, not the deeper NLI-judge pass docs/tdd.html
    describes for v2 — it catches obvious hallucination (an entity that was never
    in the input) but can't catch subtler unsupported inferential claims.

    "Lifestyle & Prevention" is excluded from both the numerator and
    denominator — the visit_prep.py prompts explicitly allow this one
    category to stay data-light (general guidance tied to a condition or
    specialty, not a specific unprovided fact), so entity-matching it
    against provided data isn't a meaningful check. Found via v3's eval
    evidence (see PROMPT_CHANGELOG.md): generic, prompt-permitted Lifestyle
    questions were dragging grounded_rate down without reflecting any real
    change in model behavior.
    """
    pairs = [(c, q) for c, q in _all_questions(result) if c != "Lifestyle & Prevention"]
    if not pairs:
        return {"grounded_rate": None, "ungrounded_questions": []}

    ungrounded = []
    for category, q in pairs:
        q_lower = q.lower()
        if not any(entity in q_lower for entity in entities):
            ungrounded.append({"category": category, "question": q})

    grounded_count = len(pairs) - len(ungrounded)
    return {
        "grounded_rate": grounded_count / len(pairs),
        "ungrounded_questions": ungrounded,
    }


def off_scope_medications(med_specialty_map: dict[str, str], target_specialty: Optional[str]) -> set[str]:
    """Medication names (lowercased) tagged for a specialty unrelated to the target visit."""
    if not target_specialty:
        return set()
    return {
        name.lower()
        for name, specialty in med_specialty_map.items()
        if specialty and not are_specialties_related(target_specialty, specialty)
    }


# A mention of an off-scope medication paired with interaction-language is
# the specialty-drug-interaction question the system prompt explicitly
# requires ("DO identify cross-condition interactions that ARE relevant to
# this specialty") — not the "discuss/manage this other doctor's med" case
# the same prompt forbids. Without this exclusion, score_scope collapses
# both into "violation," which is stricter than the rule the model was
# actually told to follow — found via DEC-042's judge work when the sole
# flagged "violation" across two eval runs turned out to be the exact
# Metformin/Clobetasol interaction question the paper's own qualitative
# section separately praises as genuinely useful synthesis. Simple
# substring check, not phrase-structure aware — matches this project's
# existing regex-first approach elsewhere (see anonymization.py), and its
# limitation (can't tell whether the off-scope med is actually paired with
# an in-scope one, vs. mentioned alongside unrelated interaction language)
# is the same kind of known, documented gap as those patterns.
_INTERACTION_LANGUAGE = "interact"  # covers interact/interacts/interaction/interactions/interacting


def score_scope(result: dict[str, Any], off_scope_names: set[str]) -> dict[str, Any]:
    """Scope checker: does any question recommend or ask to discuss/manage an
    off-scope-tagged medication directly. A question that instead names the
    off-scope medication only to check for an interaction with an in-scope
    one is not a violation — see _INTERACTION_LANGUAGE's comment.

    Checks the final generated output. Tool-call results are checked
    separately by score_tool_result_scope — Phase 2 retrieval bypasses the
    med_specialty_map tagging entirely (a known gap, see issue #74's
    context), so a tool result can carry no scope signal even when the
    final output correctly avoids it.
    """
    pairs = _all_questions(result)
    violations = []
    for category, q in pairs:
        q_lower = q.lower()
        if _INTERACTION_LANGUAGE in q_lower:
            continue
        for name in off_scope_names:
            if name in q_lower:
                violations.append({"category": category, "question": q, "medication": name})
    return {
        "violation_count": len(violations),
        "violation_rate": (len(violations) / len(pairs)) if pairs else None,
        "violations": violations,
    }


def score_tool_result_scope(tool_calls: list[dict[str, Any]], off_scope_names: set[str]) -> dict[str, Any]:
    """Does a get_medication_details tool result surface an off-scope medication
    with no specialty tag attached (the tool bypasses med_specialty_map entirely).
    Observational: reports whether an off-scope medication appears in a tool
    result at all, since the tool never tags anything regardless of scope.
    """
    hits = []
    for call in tool_calls:
        if call.get("name") != "get_medication_details":
            continue
        result_lower = (call.get("result") or "").lower()
        for name in off_scope_names:
            if name in result_lower:
                hits.append({"medication": name, "result": call.get("result")})
    return {"untagged_off_scope_hits": hits}


def score_tool_call_necessity(case: EvalCase, tool_calls: list[dict[str, Any]]) -> dict[str, Any]:
    """Observational: was the tool this case was designed to make useful actually called."""
    if not case.expects_tool_call:
        return {"applicable": False}
    called_names = {c.get("name") for c in tool_calls}
    return {
        "applicable": True,
        "expected_tool": case.expects_tool_call,
        "was_called": case.expects_tool_call in called_names,
        "calls_made": sorted(called_names),
    }


def score_tool_call_convergence(raw_result: dict[str, Any]) -> dict[str, Any]:
    """Did this case's agentic tool-use loop converge, and if not, why.

    Reads the fields VisitPrepAgent.prepare_visit already returns
    (`agentic_path`, `fallback_reason` — see FALLBACK_* in visit_prep.py):
    `agentic_path=True` means the loop produced a usable response via real
    tool-calling; `False` means prepare_visit fell back to single-shot
    generation, tagged with why (non_convergence within agent_max_turns is
    benign per DEC-013; parse_error/unknown_tool/loop_error mean the
    backend's tool-calling itself broke). This is the harness-level signal
    for "is small-model tool-calling actually reliable" rather than just
    "graceful under failure" — a case can gracefully fall back on every
    single run and still mean the agentic loop never once produced real
    output for it.
    """
    return {
        "converged": bool(raw_result.get("agentic_path")),
        "fallback_reason": raw_result.get("fallback_reason"),
    }


_VISIT_LINE_RE = re.compile(r"### Visit with (.+?) on (.+)")


def score_retrieval_redundancy(
    phase1_selected_dates: list[str],
    tool_calls: list[dict[str, Any]],
) -> dict[str, Any]:
    """Regression check: did a lookup_past_visits tool call re-surface a visit
    Phase 1's context selection already included.

    As of DEC-024, lookup_past_visits excludes Phase-1-selected appointment
    ids at the SQL query level (src/agents/tools.py), so overlap should now
    be structurally impossible, not just unlikely — a nonzero overlap_count
    here indicates the exclusion filter regressed, not merely a quality dip.
    Still matched on scheduled_date rather than the real id, since this
    reads the tool's rendered text output (AnonymizedAppointment carries no
    original id by design) rather than the query itself.
    """
    phase1_dates = set(phase1_selected_dates)
    phase2_dates: set[str] = set()

    for call in tool_calls:
        if call.get("name") != "lookup_past_visits":
            continue
        for _title, date_str in _VISIT_LINE_RE.findall(call.get("result") or ""):
            phase2_dates.add(date_str.strip())

    overlap = phase1_dates & phase2_dates
    return {
        "phase1_visit_count": len(phase1_dates),
        "phase2_lookup_visit_count": len(phase2_dates),
        "overlap_count": len(overlap),
        "overlap_rate": (len(overlap) / len(phase2_dates)) if phase2_dates else None,
    }
