"""Tests for the v1 eval harness's own scoring logic (issue #29).

The harness's job is to catch real regressions, so its scorers need their
own regression protection — same reasoning as testing the tools/backends
they're built on. Uses mocked LLM output (same pattern as test_visit_prep.py)
so these don't depend on a live model.
"""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from eval import retrieval_stage1, scorers
from eval.fixtures import GENERATION_CASES, DoctorFixture, EvalCase, MedicationFixture
from eval.run import run_generation_case
from src.data.models import Base


def _mock_text_response(payload: dict) -> MagicMock:
    mock_message = MagicMock()
    mock_message.content = [SimpleNamespace(type="text", text=json.dumps(payload))]
    mock_message.usage = MagicMock(input_tokens=100, output_tokens=50)
    return mock_message


@pytest.fixture(autouse=True)
def _claude_provider_no_ner(monkeypatch):
    from src.config import get_settings
    settings = get_settings()
    monkeypatch.setattr(settings, "llm_provider", "claude")
    monkeypatch.setattr(settings, "use_ner_anonymization", False)


@pytest.fixture(autouse=True)
def _no_ollama_client(monkeypatch):
    monkeypatch.setattr(
        "src.agents.visit_prep.get_ollama_client", AsyncMock(return_value=None)
    )


@pytest.fixture
async def eval_db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False, future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async_session = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session


def test_all_fixture_cases_have_valid_doctor_and_medication_keys():
    """Every EvalCase must reference doctor keys that actually exist in its own
    doctors list — a typo here would silently KeyError deep in eval/db.py."""
    for case in GENERATION_CASES:
        doctor_keys = {d.key for d in case.doctors}
        assert case.target_doctor_key in doctor_keys, case.id
        for m in case.medications:
            if m.prescribing_doctor_key:
                assert m.prescribing_doctor_key in doctor_keys, case.id
        for pv in case.past_visits:
            assert pv.doctor_key in doctor_keys, case.id


def test_expected_min_questions_scales_down_for_sparse_cases():
    cold_start = next(c for c in GENERATION_CASES if c.id == "cold_start")
    richer = next(c for c in GENERATION_CASES if c.id == "tool_call_necessity_dosing")

    assert scorers.expected_min_questions(cold_start) < 8
    assert scorers.expected_min_questions(richer) == 8


# Pins the floor each fixture case is actually held to, so the numbers are
# regression-covered rather than re-derived by hand every time someone
# wonders why a case passed or failed format validity (issue #75).
EXPECTED_FLOORS = {
    "cross_specialty_scope": 4,   # 2 in-scope entities; 2 more are off-scope dermatology
    "groundedness_labs_vitals": 6,  # 3 in-scope entities, all countable
    "cold_start": 3,              # 1 entity, so the max(3, ...) floor binds
    "tool_call_necessity_dosing": 8,  # 4 in-scope entities, capped at the prompt's own 8
    "retrieval_redundancy": 4,    # 2 in-scope entities
}


@pytest.mark.parametrize("case_id,expected_floor", sorted(EXPECTED_FLOORS.items()))
def test_expected_min_questions_per_case(case_id, expected_floor):
    case = next(c for c in GENERATION_CASES if c.id == case_id)
    assert scorers.expected_min_questions(case) == expected_floor


def test_every_fixture_case_has_a_pinned_floor():
    """A new case added without a pinned floor would silently skip the check
    above, so make the omission itself a failure."""
    assert {c.id for c in GENERATION_CASES} == set(EXPECTED_FLOORS)


def test_in_scope_entities_excludes_off_scope_medication_and_condition():
    """The whole point of #75: cross_specialty_scope looks entity-rich (4)
    but half of it is material the v3 prompt forbids discussing, so the
    floor was demanding 8 questions from 2 questions' worth of input."""
    case = next(c for c in GENERATION_CASES if c.id == "cross_specialty_scope")

    assert len(scorers.known_entities(case)) == 4
    assert scorers.in_scope_entities(case) == {"type 2 diabetes mellitus", "metformin"}
    assert "clobetasol cream" not in scorers.in_scope_entities(case)
    assert "mild plaque psoriasis" not in scorers.in_scope_entities(case)


def test_known_entities_stays_scope_blind_for_groundedness():
    """known_entities must keep counting off-scope entities, or a question
    about the real-but-off-scope Clobetasol would score as a hallucination
    instead of a scope violation — see the docstring on known_entities."""
    case = next(c for c in GENERATION_CASES if c.id == "cross_specialty_scope")
    entities = scorers.known_entities(case)

    assert "clobetasol cream" in entities
    assert "mild plaque psoriasis" in entities

    result = {"questions": {"Medication Review": ["Should I ask about my Clobetasol Cream too?"]}}
    assert scorers.score_groundedness(result, entities)["grounded_rate"] == 1.0
    assert scorers.score_scope(result, {"clobetasol cream"})["violation_count"] == 1


def test_cross_specialty_scope_six_questions_now_passes_format_validity():
    """The observed failure this issue was filed for: the model produced 6
    questions against a flat floor of 8. With a scope-aware floor of 4 the
    same output passes, and 3 still fails, so the check isn't vacuous."""
    case = next(c for c in GENERATION_CASES if c.id == "cross_specialty_scope")
    floor = scorers.expected_min_questions(case)

    six = {"questions": {"Condition Management": [f"q{i}" for i in range(6)]}}
    three = {"questions": {"Condition Management": [f"q{i}" for i in range(3)]}}

    assert scorers.score_format(six, min_questions=floor)["valid"] is True
    assert scorers.score_format(three, min_questions=floor)["valid"] is False


def test_medication_with_unknown_prescriber_specialty_counts_as_in_scope():
    """Absence of a scope signal isn't evidence of being off scope —
    defaulting the other way would silently deflate the floor for any
    fixture that just didn't bother tagging a prescriber."""
    case = EvalCase(
        id="untagged_prescriber", description="", profile_name="x",
        doctors=[
            DoctorFixture(key="t", name="Dr. X", specialty="Endocrinology"),
            DoctorFixture(key="u", name="Dr. Y"),  # no specialty
        ],
        target_doctor_key="t",
        appointment_purpose="p", appointment_scheduled_date="2026-01-01T10:00:00",
        medications=[
            MedicationFixture(name="Untagged Med", prescribing_doctor_key="u"),
            MedicationFixture(name="No Prescriber Med"),
        ],
    )
    assert scorers.in_scope_entities(case) == {"untagged med", "no prescriber med"}


def test_score_format_respects_custom_min_questions():
    result = {"questions": {"Condition Management": ["q1", "q2", "q3"]}}
    assert scorers.score_format(result, min_questions=3)["valid"] is True
    assert scorers.score_format(result, min_questions=8)["valid"] is False


def test_score_groundedness_excludes_lifestyle_category():
    result = {
        "questions": {
            "Condition Management": ["Ask about my diabetes."],
            "Lifestyle & Prevention": ["What general tips help with a healthy diet?"],
        }
    }
    scored = scorers.score_groundedness(result, entities={"diabetes"})
    assert scored["grounded_rate"] == 1.0
    assert scored["ungrounded_questions"] == []



def test_stage1_checks_run_and_document_the_known_72_gap():
    results = retrieval_stage1.run_all()
    by_name = {r.name.split(" (")[0]: r for r in results}

    assert by_name["same_doctor_visit_included"].passed
    assert by_name["same_doctor_only_most_recent_kept"].passed
    assert by_name["pcp_included_regardless_of_specialty"].passed
    assert by_name["unrelated_specialty_excluded"].passed
    assert by_name["related_specialty_included"].passed
    assert by_name["excluded_doctor_flag_respected"].passed
    # Documents the #72 gap — passes today because the bug exists; flip once fixed.
    assert by_name["blank_specialty_clinic_fallback_gap"].passed


def test_score_format_flags_wrong_question_count():
    result = {"questions": {"Condition Management": ["only one question"]}}
    scored = scorers.score_format(result)
    assert not scored["valid"]
    assert scored["question_count"] == 1


def test_score_format_flags_unknown_category():
    result = {"questions": {"Not A Real Category": [f"q{i}" for i in range(9)]}}
    scored = scorers.score_format(result)
    assert not scored["valid"]
    assert any("unknown category" in issue for issue in scored["issues"])


def test_score_groundedness_flags_hallucinated_entity():
    entities = {"metformin"}
    result = {"questions": {"Medication Review": ["Should I keep taking Metformin?", "Is Ozempic right for me?"]}}
    scored = scorers.score_groundedness(result, entities)
    assert scored["grounded_rate"] == 0.5
    assert scored["ungrounded_questions"][0]["question"] == "Is Ozempic right for me?"


def test_score_scope_flags_off_scope_medication():
    off_scope = {"clobetasol cream"}
    result = {"questions": {"Medication Review": ["Should I ask about my Clobetasol Cream too?"]}}
    scored = scorers.score_scope(result, off_scope)
    assert scored["violation_count"] == 1


def test_score_scope_clean_when_no_off_scope_mentioned():
    off_scope = {"clobetasol cream"}
    result = {"questions": {"Medication Review": ["Is Metformin still working?"]}}
    scored = scorers.score_scope(result, off_scope)
    assert scored["violation_count"] == 0


def test_score_scope_permits_cross_specialty_interaction_question():
    """The exact case found via DEC-042's judge work: a question asking
    whether an in-scope and an off-scope medication interact is explicitly
    required by the system prompt ("DO identify cross-condition
    interactions"), not a scope violation — even though it names the
    off-scope medication."""
    off_scope = {"clobetasol cream"}
    result = {
        "questions": {
            "Medication Review": [
                "Are there any potential interactions between Metformin and Clobetasol Cream that I should be aware of?"
            ]
        }
    }
    scored = scorers.score_scope(result, off_scope)
    assert scored["violation_count"] == 0


def test_score_scope_still_flags_direct_management_of_off_scope_medication():
    """The interaction-language exclusion must not swallow the real
    violation case: a question that names the off-scope medication with no
    interaction framing is still asking this doctor to discuss/manage a
    medication that isn't theirs to manage."""
    off_scope = {"clobetasol cream"}
    result = {"questions": {"Medication Review": ["Should I adjust my Clobetasol Cream dosage?"]}}
    scored = scorers.score_scope(result, off_scope)
    assert scored["violation_count"] == 1


def test_off_scope_medications_uses_specialty_relatedness():
    med_map = {"Metformin": "Endocrinology", "Clobetasol Cream": "Dermatology"}
    off_scope = scorers.off_scope_medications(med_map, target_specialty="Endocrinology")
    assert off_scope == {"clobetasol cream"}


def test_score_retrieval_redundancy_detects_overlap():
    phase1_dates = ["2026-05-01T10:00:00", "2026-02-01T10:00:00"]
    tool_calls = [{
        "name": "lookup_past_visits",
        "result": "### Visit with your Endocrinologist on 2026-05-01T10:00:00\nPurpose: Thyroid follow-up\n",
    }]
    scored = scorers.score_retrieval_redundancy(phase1_dates, tool_calls)
    assert scored["overlap_count"] == 1
    assert scored["phase2_lookup_visit_count"] == 1


def test_score_tool_call_necessity_not_applicable_when_case_has_no_expectation():
    case = EvalCase(
        id="no_expectation", description="", profile_name="x",
        doctors=[DoctorFixture(key="t", name="Dr. X")], target_doctor_key="t",
        appointment_purpose="p", appointment_scheduled_date="2026-01-01T10:00:00",
    )
    scored = scorers.score_tool_call_necessity(case, tool_calls=[])
    assert scored["applicable"] is False


def test_score_tool_call_convergence_true_when_agentic_path_succeeded():
    scored = scorers.score_tool_call_convergence(
        {"agentic_path": True, "fallback_reason": None}
    )
    assert scored == {"converged": True, "fallback_reason": None}


def test_score_tool_call_convergence_false_reports_fallback_reason():
    """converged must be False whenever agentic_path is, regardless of which
    FALLBACK_* reason fired — the reason is what --trials aggregation groups
    by (DEC-037's non_convergence vs. parse_error vs. unknown_tool split)."""
    scored = scorers.score_tool_call_convergence(
        {"agentic_path": False, "fallback_reason": "non_convergence"}
    )
    assert scored == {"converged": False, "fallback_reason": "non_convergence"}


def test_score_tool_call_convergence_missing_fields_default_to_not_converged():
    """A raw_result that never got as far as setting these keys (e.g. the
    outer hard-failure fallback response) must read as non-converged, not
    raise — score_tool_call_convergence is called on every case's result,
    including ones that failed before agentic_path was ever set."""
    scored = scorers.score_tool_call_convergence({})
    assert scored == {"converged": False, "fallback_reason": None}


@pytest.mark.asyncio
async def test_run_generation_case_end_to_end_with_scope_violation(eval_db):
    """Full plumbing check with a mocked model that deliberately asks an
    off-scope question — confirms build_case + prepare_visit + scorers all
    connect correctly, using the same fixture case a real run would use.
    """
    case = next(c for c in GENERATION_CASES if c.id == "cross_specialty_scope")

    mock_message = _mock_text_response({
        "questions": {
            "Condition Management": ["How is my diabetes management going?", "Any A1c changes?"],
            "Medication Review": ["Is Metformin still effective?", "Should I ask about my Clobetasol Cream too?"],
            "Lifestyle & Prevention": ["Any dietary changes recommended?"],
            "Lab Results & Monitoring": ["When should I get my next HbA1c?"],
            "Follow-up Planning": ["When should I schedule my next visit?", "Any specialists to follow up with?", "Should I get a referral?"],
        },
        "context_summary": "Patient managing Type 2 Diabetes with Metformin.",
    })

    with patch("src.agents.llm_backend.AsyncAnthropic") as mock_anthropic:
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_message)
        mock_anthropic.return_value = mock_client
        report = await run_generation_case(eval_db, case)

    assert report["format"]["valid"] is True
    assert report["scope"]["violation_count"] == 1
    assert report["scope"]["violations"][0]["medication"] == "clobetasol cream"
    assert report["groundedness"]["grounded_rate"] > 0


@pytest.mark.asyncio
async def test_run_generation_case_survives_a_judge_failure(eval_db):
    """A judge call that fails after its own retries (eval/judge.py) must
    not crash the whole multi-case, multi-trial run — recorded as
    factual_groundedness_error instead, same posture as CASE_TIMEOUT_SECONDS's
    timeout handling: surfaced, not swallowed, but not fatal either."""
    case = next(c for c in GENERATION_CASES if c.id == "cold_start")

    mock_message = _mock_text_response({
        "questions": {"Lifestyle & Prevention": ["Any general tips for allergy season?"]},
        "context_summary": "Patient has Seasonal Allergic Rhinitis.",
    })

    class AlwaysFailingJudgeBackend:
        model = "claude-opus-4-8"

        async def call(self, *args, **kwargs):
            return SimpleNamespace(text="", input_tokens=10, output_tokens=5)

    with patch("src.agents.llm_backend.AsyncAnthropic") as mock_anthropic:
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_message)
        mock_anthropic.return_value = mock_client
        report = await run_generation_case(eval_db, case, judge_backend=AlwaysFailingJudgeBackend())

    assert "factual_groundedness" not in report
    assert "factual_groundedness_error" in report
    assert report["format"]["question_count"] == 1  # rest of the report is unaffected, computed normally


@pytest.mark.asyncio
async def test_run_generation_case_cold_start_has_no_medications_to_flag(eval_db):
    case = next(c for c in GENERATION_CASES if c.id == "cold_start")

    mock_message = _mock_text_response({
        "questions": {
            "Condition Management": [f"Question about allergies {i}" for i in range(8)],
        },
        "context_summary": "Patient with seasonal allergies.",
    })

    with patch("src.agents.llm_backend.AsyncAnthropic") as mock_anthropic:
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_message)
        mock_anthropic.return_value = mock_client
        report = await run_generation_case(eval_db, case)

    assert report["scope"]["violation_count"] == 0
    assert report["tool_call_necessity"]["applicable"] is False
