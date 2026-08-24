"""Tests for _run_agentic_loop's tool-result content budget, exact-duplicate
short-circuiting, and _render_gathered_tool_results (DEC-037/DEC-038).

Uses a fake LLMBackend and a monkeypatched VisitPrepTools.execute so these
run without a real Ollama server or real patient data — the loop's own
budget/dedup bookkeeping is what's under test, not tool execution itself.
"""

from unittest.mock import AsyncMock, patch

import pytest

from src.agents.llm_backend import LLMTurnResult, ToolCall
from src.agents.visit_prep import (
    _BUDGET_EXCEEDED_PLACEHOLDER,
    _DUPLICATE_CALL_PLACEHOLDER,
    _render_gathered_tool_results,
    VisitPrepAgent,
)
from src.config import Settings


def _fake_backend(call_results: list[LLMTurnResult]):
    """A minimal stand-in LLMBackend whose .call() returns each of
    call_results in order — one per turn of the loop under test."""
    backend = AsyncMock()
    backend.call = AsyncMock(side_effect=call_results)
    backend.build_assistant_message = lambda result: {
        "role": "assistant", "content": result.text or "", "tool_calls": None,
    }
    backend.build_tool_result_message = lambda tool_call, result_content: {
        "role": "tool", "tool_call_id": tool_call.id, "content": result_content,
    }
    return backend


@pytest.fixture
def agent(db_session):
    a = VisitPrepAgent(db_session)
    a.settings = Settings(llm_provider="ollama", ollama_num_ctx=8192, agent_max_turns=6)
    return a


class TestExactDuplicateCalls:
    @pytest.mark.asyncio
    async def test_second_identical_call_is_not_re_executed(self, agent):
        """Same tool name + same args, twice in one turn — the second must
        get the duplicate placeholder instead of a fresh execute() call."""
        dup_call = ToolCall(id="1", name="get_medication_details", input={"medication_name": "Metformin"})
        dup_call_2 = ToolCall(id="2", name="get_medication_details", input={"medication_name": "Metformin"})
        turn1 = LLMTurnResult(text=None, tool_calls=[dup_call, dup_call_2], stop_reason="tool_use")
        turn2 = LLMTurnResult(text='{"questions": {}, "context_summary": "done"}', tool_calls=[], stop_reason="end_turn")

        execute_mock = AsyncMock(return_value="Metformin 500mg")
        with patch("src.agents.visit_prep.get_llm_backend", return_value=_fake_backend([turn1, turn2])), \
             patch("src.agents.tools.VisitPrepTools.execute", execute_mock):
            response = await agent._run_agentic_loop(
                "profile-1", [{"role": "user", "content": "ctx"}], "system prompt",
            )

        assert execute_mock.call_count == 1  # only the first, real call hit the tool
        assert agent.last_tool_calls[0]["result"] == "Metformin 500mg"
        assert agent.last_tool_calls[1]["result"] == _DUPLICATE_CALL_PLACEHOLDER
        assert response == '{"questions": {}, "context_summary": "done"}'

    @pytest.mark.asyncio
    async def test_duplicate_across_separate_turns_also_short_circuits(self, agent):
        """The cache must persist across turns, not just within one — a
        call repeated on turn 2 that was already answered on turn 1 is
        exactly as wasteful as a repeat within the same turn."""
        call_a = ToolCall(id="1", name="lookup_past_visits", input={})
        call_b = ToolCall(id="2", name="lookup_past_visits", input={})
        turn1 = LLMTurnResult(text=None, tool_calls=[call_a], stop_reason="tool_use")
        turn2 = LLMTurnResult(text=None, tool_calls=[call_b], stop_reason="tool_use")
        turn3 = LLMTurnResult(text='{"questions": {}, "context_summary": "done"}', tool_calls=[], stop_reason="end_turn")

        execute_mock = AsyncMock(return_value="visit history text")
        with patch("src.agents.visit_prep.get_llm_backend", return_value=_fake_backend([turn1, turn2, turn3])), \
             patch("src.agents.tools.VisitPrepTools.execute", execute_mock):
            await agent._run_agentic_loop("profile-1", [{"role": "user", "content": "ctx"}], "system prompt")

        assert execute_mock.call_count == 1
        assert agent.last_tool_calls[1]["result"] == _DUPLICATE_CALL_PLACEHOLDER


class TestToolResultBudget:
    @pytest.mark.asyncio
    async def test_call_beyond_budget_gets_placeholder_not_executed(self, agent):
        """A tiny num_ctx leaves almost no room for tool-result content —
        a genuinely new (non-duplicate) call that would exceed it must get
        the budget-exceeded placeholder instead of hitting the tool."""
        agent.settings = Settings(llm_provider="ollama", ollama_num_ctx=50, agent_max_turns=6)
        call = ToolCall(id="1", name="get_medication_details", input={})
        turn1 = LLMTurnResult(text=None, tool_calls=[call], stop_reason="tool_use")
        turn2 = LLMTurnResult(text='{"questions": {}, "context_summary": "done"}', tool_calls=[], stop_reason="end_turn")

        execute_mock = AsyncMock(return_value="a" * 5000)  # far bigger than the tiny budget
        with patch("src.agents.visit_prep.get_llm_backend", return_value=_fake_backend([turn1, turn2])), \
             patch("src.agents.tools.VisitPrepTools.execute", execute_mock):
            await agent._run_agentic_loop("profile-1", [{"role": "user", "content": "ctx"}], "system prompt")

        assert execute_mock.call_count == 0
        assert agent.last_tool_calls[0]["result"] == _BUDGET_EXCEEDED_PLACEHOLDER

    @pytest.mark.asyncio
    async def test_calls_within_budget_execute_normally(self, agent):
        """Regression guard for the other direction: a generous num_ctx must
        not throttle ordinary, well-within-budget tool calls — the budget
        mechanism replaced a per-turn call-count cap specifically so this
        would keep working (see DEC-037's "don't cap at 1" reasoning)."""
        call = ToolCall(id="1", name="get_medication_details", input={})
        turn1 = LLMTurnResult(text=None, tool_calls=[call], stop_reason="tool_use")
        turn2 = LLMTurnResult(text='{"questions": {}, "context_summary": "done"}', tool_calls=[], stop_reason="end_turn")

        execute_mock = AsyncMock(return_value="short result")
        with patch("src.agents.visit_prep.get_llm_backend", return_value=_fake_backend([turn1, turn2])), \
             patch("src.agents.tools.VisitPrepTools.execute", execute_mock):
            await agent._run_agentic_loop("profile-1", [{"role": "user", "content": "ctx"}], "system prompt")

        assert execute_mock.call_count == 1
        assert agent.last_tool_calls[0]["result"] == "short result"


class TestRenderGatheredToolResults:
    def test_renders_name_and_result_for_each_call(self):
        rendered = _render_gathered_tool_results([
            {"name": "get_medication_details", "input": {}, "result": "No matching medications found."},
        ])
        assert "[get_medication_details]" in rendered
        assert "No matching medications found." in rendered

    def test_skips_duplicate_and_budget_placeholders(self):
        """Placeholders add nothing — the real result is already included
        once, and a "budget exceeded" marker isn't information to forward
        to the fallback call, it would just be noise."""
        rendered = _render_gathered_tool_results([
            {"name": "get_medication_details", "input": {}, "result": "No matching medications found."},
            {"name": "get_medication_details", "input": {}, "result": _DUPLICATE_CALL_PLACEHOLDER},
            {"name": "lookup_past_visits", "input": {}, "result": _BUDGET_EXCEEDED_PLACEHOLDER},
        ])
        assert rendered.count("[get_medication_details]") == 1
        assert "[lookup_past_visits]" not in rendered

    def test_empty_input_renders_empty_string(self):
        assert _render_gathered_tool_results([]) == ""
