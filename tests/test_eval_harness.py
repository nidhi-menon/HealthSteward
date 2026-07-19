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
from eval.fixtures import GENERATION_CASES, DoctorFixture, EvalCase
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


def test_score_format_respects_custom_min_questions():
    result = {"questions": {"Condition Management": ["q1", "q2", "q3"]}}
    assert scorers.score_format(result, min_questions=3)["valid"] is True
    assert scorers.score_format(result, min_questions=8)["valid"] is False



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
