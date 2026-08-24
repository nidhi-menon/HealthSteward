"""Tests for eval/judge.py's pure-function logic (DEC-042).

Flagged as a coverage gap in code review before this branch merges — every
other eval module has unit coverage for its parsing/aggregation logic, this
didn't yet. Uses a fake backend (no real Claude call) so these don't depend
on ANTHROPIC_API_KEY or network access, same pattern as test_eval_harness.py.
"""

import pytest

from eval.fixtures import (
    ConditionFixture,
    DoctorFixture,
    EvalCase,
    LabOrderFixture,
    MedicationFixture,
    PastVisitFixture,
    VitalsFixture,
)
from eval.judge import (
    FACTUAL_GROUNDEDNESS_JUDGE_PROMPT_VERSION,
    _case_context_text,
    _parse_judge_response,
    _questions_text,
    score_factual_groundedness,
)
from src.agents.llm_backend import LLMTurnResult


def _make_case(**overrides) -> EvalCase:
    defaults = dict(
        id="test_case",
        description="A test case",
        profile_name="Test Patient",
        doctors=[],
        target_doctor_key="target",
        appointment_purpose="Thyroid check",
        appointment_scheduled_date="2026-08-02T10:00:00",
    )
    defaults.update(overrides)
    return EvalCase(**defaults)


class FakeJudgeBackend:
    """Stands in for ClaudeBackend — returns a fixed LLMTurnResult without a real call."""

    def __init__(self, text: str, model: str = "claude-opus-4-8", input_tokens=100, output_tokens=50):
        self.model = model
        self._text = text
        self._input_tokens = input_tokens
        self._output_tokens = output_tokens
        self.last_call_kwargs = None

    async def call(self, messages, system, tools=None, temperature=0.7, response_schema=None):
        self.last_call_kwargs = {"messages": messages, "system": system, "temperature": temperature}
        return LLMTurnResult(
            text=self._text,
            input_tokens=self._input_tokens,
            output_tokens=self._output_tokens,
        )


class FlakyThenGoodJudgeBackend:
    """Returns an empty/malformed response on the first call, a valid one on
    the second — for testing score_factual_groundedness's one-retry
    tolerance of a transient bad response, distinct from a persistently
    malformed one."""

    def __init__(self, good_text: str, model: str = "claude-opus-4-8"):
        self.model = model
        self._good_text = good_text
        self.call_count = 0

    async def call(self, messages, system, tools=None, temperature=0.7, response_schema=None):
        self.call_count += 1
        text = "" if self.call_count == 1 else self._good_text
        return LLMTurnResult(text=text, input_tokens=100, output_tokens=50)


class TestParseJudgeResponse:
    def test_parses_clean_json(self):
        result = _parse_judge_response('{"claims": []}')
        assert result == {"claims": []}

    def test_strips_markdown_fences(self):
        result = _parse_judge_response('```json\n{"claims": []}\n```')
        assert result == {"claims": []}

    def test_strips_bare_fences_no_language_tag(self):
        result = _parse_judge_response('```\n{"claims": []}\n```')
        assert result == {"claims": []}

    def test_raises_with_raw_text_on_malformed_json(self):
        with pytest.raises(ValueError) as exc_info:
            _parse_judge_response("not json at all")
        assert "not json at all" in str(exc_info.value)


class TestCaseContextText:
    def test_includes_appointment_purpose(self):
        case = _make_case(appointment_purpose="Diabetes follow-up")
        text = _case_context_text(case)
        assert "Diabetes follow-up" in text

    def test_includes_appointment_date_and_target_doctor(self):
        """Regression guard for a real false-positive found via DEC-042: the
        judge previously never saw the appointment date or target doctor's
        specialty at all, so it flagged cold_start's genuinely-true "Family
        Medicine specialist" and "August 3rd, 2026" claims as unsupported —
        they were true, the judge just couldn't see the fixture data that
        proved it."""
        case = _make_case(
            appointment_scheduled_date="2026-08-03T09:00:00",
            doctors=[DoctorFixture(key="target", name="Dr. Alex Kim", specialty="Family Medicine", clinic="Riverside Family Practice")],
        )
        text = _case_context_text(case)
        assert "2026-08-03T09:00:00" in text
        assert "Dr. Alex Kim" in text
        assert "Family Medicine" in text
        assert "Riverside Family Practice" in text

    def test_omits_doctor_line_when_target_doctor_not_found(self):
        case = _make_case(doctors=[], target_doctor_key="missing")
        text = _case_context_text(case)
        assert "Appointment doctor" not in text

    def test_includes_condition_detail(self):
        case = _make_case(conditions=[ConditionFixture(name="Hashimoto's Thyroiditis", icd_10="E06.3", status="active")])
        text = _case_context_text(case)
        assert "Hashimoto's Thyroiditis" in text
        assert "E06.3" in text
        assert "active" in text

    def test_includes_medication_detail(self):
        case = _make_case(medications=[
            MedicationFixture(name="Levothyroxine", dosage="75mcg", frequency="once daily", purpose="Thyroid hormone replacement"),
        ])
        text = _case_context_text(case)
        assert "Levothyroxine" in text
        assert "75mcg" in text
        assert "Thyroid hormone replacement" in text

    def test_includes_lab_orders_and_vitals_and_past_visits(self):
        case = _make_case(
            lab_orders=[LabOrderFixture(test_name="TSH", ordered_date="2026-07-15")],
            vitals=[VitalsFixture(weight="165 lbs", bmi=26.1, measured_date="2026-08-01")],
            past_visits=[PastVisitFixture(doctor_key="target", scheduled_date="2026-06-01T10:00:00", purpose="Annual checkup")],
        )
        text = _case_context_text(case)
        assert "TSH" in text and "2026-07-15" in text
        assert "165 lbs" in text and "26.1" in text
        assert "Annual checkup" in text

    def test_omits_empty_sections(self):
        case = _make_case()
        text = _case_context_text(case)
        assert "Conditions:" not in text
        assert "Medications:" not in text
        assert "Lab orders:" not in text
        assert "Vitals:" not in text
        assert "Past visits:" not in text


class TestQuestionsText:
    def test_renders_categories_and_questions(self):
        result = {"questions": {"Condition Management": ["What are my blood sugar targets?"]}}
        text = _questions_text(result)
        assert "Condition Management" in text
        assert "What are my blood sugar targets?" in text

    def test_handles_missing_questions_key(self):
        assert _questions_text({}) == ""

    def test_includes_context_summary(self):
        """Regression guard for the real gap found via DEC-042: an earlier
        judge version never scored context_summary at all, silently missing
        an unhedged 'typically managed by Pulmonology' claim that lived only
        there, not in any question."""
        result = {
            "questions": {},
            "context_summary": "Condition X, which is typically managed by Pulmonology.",
        }
        text = _questions_text(result)
        assert "typically managed by Pulmonology" in text

    def test_omits_context_summary_section_when_absent(self):
        assert "Context Summary" not in _questions_text({"questions": {}})


class TestScoreFactualGroundedness:
    @pytest.mark.asyncio
    async def test_computes_unsupported_rate_excluding_not_applicable(self):
        judge_response = {
            "claims": [
                {"category": "Condition Management", "question": "q1", "claim_text": "c1", "verdict": "grounded", "reasoning": "r1"},
                {"category": "Condition Management", "question": "q2", "claim_text": "c2", "verdict": "unsupported", "reasoning": "r2"},
                {"category": "Follow-up Planning", "question": "q3", "claim_text": "c3", "verdict": "not_applicable", "reasoning": "r3"},
            ]
        }
        import json
        backend = FakeJudgeBackend(text=json.dumps(judge_response))
        case = _make_case()
        result = {"questions": {"Condition Management": ["q1", "q2"], "Follow-up Planning": ["q3"]}}

        report = await score_factual_groundedness(case, result, backend)

        assert report["unsupported_rate"] == pytest.approx(0.5)
        assert len(report["unsupported_claims"]) == 1
        assert report["prompt_version"] == FACTUAL_GROUNDEDNESS_JUDGE_PROMPT_VERSION
        assert report["judge_model"] == "claude-opus-4-8"
        assert report["input_tokens"] == 100
        assert report["output_tokens"] == 50
        assert report["duration_s"] >= 0

    @pytest.mark.asyncio
    async def test_unsupported_rate_is_none_when_no_scored_claims(self):
        import json
        judge_response = {"claims": [
            {"category": "Follow-up Planning", "question": "q1", "claim_text": "c1", "verdict": "not_applicable", "reasoning": "r1"},
        ]}
        backend = FakeJudgeBackend(text=json.dumps(judge_response))
        case = _make_case()
        result = {"questions": {"Follow-up Planning": ["q1"]}}

        report = await score_factual_groundedness(case, result, backend)

        assert report["unsupported_rate"] is None
        assert report["unsupported_claims"] == []

    @pytest.mark.asyncio
    async def test_unsupported_rate_is_none_for_empty_claims_list(self):
        import json
        backend = FakeJudgeBackend(text=json.dumps({"claims": []}))
        case = _make_case()
        result = {"questions": {}}

        report = await score_factual_groundedness(case, result, backend)

        assert report["unsupported_rate"] is None
        assert report["claims"] == []

    @pytest.mark.asyncio
    async def test_raises_on_malformed_judge_response(self):
        backend = FakeJudgeBackend(text="not valid json")
        case = _make_case()
        result = {"questions": {}}

        with pytest.raises(ValueError):
            await score_factual_groundedness(case, result, backend)

    @pytest.mark.asyncio
    async def test_retries_once_on_transient_empty_response(self):
        import json

        backend = FlakyThenGoodJudgeBackend(good_text=json.dumps({"claims": []}))
        case = _make_case()
        result = {"questions": {}}

        report = await score_factual_groundedness(case, result, backend)

        assert backend.call_count == 2
        assert report["claims"] == []

    @pytest.mark.asyncio
    async def test_raises_after_all_attempts_fail(self):
        backend = FakeJudgeBackend(text="")
        case = _make_case()
        result = {"questions": {}}

        with pytest.raises(ValueError):
            await score_factual_groundedness(case, result, backend)
