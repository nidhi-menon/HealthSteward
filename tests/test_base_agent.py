"""Tests for src/agents/base.py — BaseAgent._parse_json_response and its
truncated-JSON repair helper (DEC-037).
"""

import json

from src.agents.base import BaseAgent, _repair_truncated_json


def _agent() -> BaseAgent:
    """A BaseAgent instance for calling _parse_json_response, which doesn't
    touch self or the DB — __new__ bypasses __init__'s DB session requirement
    rather than constructing a real (unused) AsyncSession for these tests.
    """
    return BaseAgent.__new__(BaseAgent)


def test_repair_truncated_json_closes_unterminated_string_and_braces():
    truncated = (
        '{\n'
        '    "questions": {\n'
        '        "Condition Management": [\n'
        '            "What are the current blood sugar targets?"\n'
        '        ]\n'
        '    },\n'
        '    "context_summary": "The patient has Type 2 Diabetes'
    )
    repaired = _repair_truncated_json(truncated)
    assert repaired is not None
    parsed = json.loads(repaired)
    assert parsed["context_summary"] == "The patient has Type 2 Diabetes"
    assert parsed["questions"]["Condition Management"] == ["What are the current blood sugar targets?"]


def test_repair_truncated_json_closes_nested_unclosed_brackets():
    repaired = _repair_truncated_json('{"a": {"b": ["x", "y')
    assert repaired == '{"a": {"b": ["x", "y"]}}'
    assert json.loads(repaired) == {"a": {"b": ["x", "y"]}}


def test_repair_truncated_json_returns_none_for_already_well_formed_text():
    """Well-formed input has nothing open — repair must be a no-op (return
    None) so the caller's normal parse path handles it, not a "repair" that
    could alter already-valid content.
    """
    assert _repair_truncated_json('{"a": 1}') is None


def test_repair_truncated_json_ignores_braces_inside_strings():
    """A brace/bracket character that's part of string content (not real
    JSON structure) must not be counted toward what needs closing."""
    repaired = _repair_truncated_json('{"a": "text with a { in it"')
    assert repaired == '{"a": "text with a { in it"}'
    assert json.loads(repaired) == {"a": "text with a { in it"}


def test_repair_truncated_json_handles_escaped_quote_inside_string():
    """An escaped quote (\\") must not be mistaken for the string's closing
    quote — otherwise the scanner would think the string already closed and
    miscount everything after it as bare JSON structure."""
    repaired = _repair_truncated_json('{"a": "she said \\"hi')
    assert repaired == '{"a": "she said \\"hi"}'
    assert json.loads(repaired) == {"a": 'she said "hi'}


def test_parse_json_response_direct_parse_succeeds_without_repair():
    agent = _agent()
    result = agent._parse_json_response('{"questions": {}, "context_summary": "ok"}')
    assert result == {"questions": {}, "context_summary": "ok"}


def test_parse_json_response_falls_through_to_repair_strategy():
    """The end-to-end path this exists for: a response that fails direct
    parse, code-block extraction, and the greedy-regex strategy (no closing
    brace present at all for the regex to match against) still parses via
    the repair strategy — this is what DEC-037's tool_call_necessity_dosing
    fix actually relies on.
    """
    agent = _agent()
    truncated = (
        '{"questions": {"Condition Management": ["Q1?"]}, '
        '"context_summary": "partial summary'
    )
    result = agent._parse_json_response(truncated)
    assert result is not None
    assert result["questions"] == {"Condition Management": ["Q1?"]}
    assert result["context_summary"] == "partial summary"


def test_parse_json_response_returns_none_for_genuinely_unrepairable_text():
    agent = _agent()
    assert agent._parse_json_response("not json at all, no braces here") is None
