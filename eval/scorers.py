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
    """Scale the expected minimum question count with how much real data a
    case actually has, rather than enforcing a fixed 8 for every case.

    Found via #29's first real runs: cold_start (one condition, nothing
    else) failing the fixed 8-question floor was in tension with the
    system prompt's own anti-hallucination rules — pushing the model to
    invent content just to hit a fixed number for a case with genuinely
    little to ask about isn't a real quality bar. 2 questions per known
    entity, floor of 3, capped at the prompt's own stated 8, is a rough
    but principled scale-down for sparse cases; richer cases still expect
    the full 8.
    """
    return min(8, max(3, len(known_entities(case)) * 2))


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
    """Entity names (lowercased) that a grounded question is allowed to reference."""
    entities = {c.name.lower() for c in case.conditions}
    entities |= {m.name.lower() for m in case.medications}
    entities |= {lab.test_name.lower() for lab in case.lab_orders}
    return entities


def score_groundedness(result: dict[str, Any], entities: set[str]) -> dict[str, Any]:
    """Cheap entity-match pass: does each question reference at least one real entity.

    This is the "smoke test" version, not the deeper NLI-judge pass docs/tdd.html
    describes for v2 — it catches obvious hallucination (an entity that was never
    in the input) but can't catch subtler unsupported inferential claims.
    """
    pairs = _all_questions(result)
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


def score_scope(result: dict[str, Any], off_scope_names: set[str]) -> dict[str, Any]:
    """Scope checker: does any question reference an off-scope-tagged medication.

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


_VISIT_LINE_RE = re.compile(r"### Visit with (.+?) on (.+)")


def score_retrieval_redundancy(
    phase1_selected_dates: list[str],
    tool_calls: list[dict[str, Any]],
) -> dict[str, Any]:
    """Observational: did a lookup_past_visits tool call re-surface a visit
    Phase 1's context selection already included.

    Matched on scheduled_date (a reliable per-visit identity even though
    AnonymizedAppointment carries no original id — see #71/#72-adjacent
    discussion: nothing in the pipeline currently correlates Phase 1 and
    Phase 2 retrieval by anything sturdier than this).
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
