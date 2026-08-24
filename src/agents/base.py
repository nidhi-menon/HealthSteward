"""Base agent class with Claude API integration and conversation logging."""

import json
from typing import Any, Optional

from anthropic import AsyncAnthropic
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import get_settings
from src.data.models import ConversationLog
from src.utils.anonymization import RedactionEvent


def _repair_truncated_json(text: str) -> Optional[str]:
    """Best-effort repair for JSON text that looks cut off mid-generation —
    an unterminated string and/or unclosed braces/brackets at the point
    generation stopped, everything before that point otherwise well-formed.

    Not a general JSON fixer: it only appends what's still open when the
    text ends (closing quote, then closing brackets/braces in the order
    they'd need to close), it doesn't correct malformed content earlier in
    the string. Found via eval/run.py's tool_call_necessity_dosing case —
    a small local model (llama3.2, agentic loop with several tool round-
    trips) hit its own end-of-turn stop token after finishing its last
    string value but before emitting the JSON's closing punctuation, giving
    otherwise-complete, well-grounded content that every prior parse
    strategy rejected outright as invalid.

    Returns the repaired text, or None if nothing looked open (repair
    wouldn't change anything, so let the caller's normal parse handle it).
    """
    open_stack: list[str] = []
    in_string = False
    escape = False
    for ch in text:
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch in "{[":
            open_stack.append(ch)
        elif ch in "}]":
            expected = "{" if ch == "}" else "["
            if open_stack and open_stack[-1] == expected:
                open_stack.pop()

    if not in_string and not open_stack:
        return None

    closers = {"{": "}", "[": "]"}
    repaired = text + ('"' if in_string else "")
    repaired += "".join(closers[opener] for opener in reversed(open_stack))
    return repaired


class BaseAgent:
    """Base agent class providing Claude API access and conversation logging."""

    def __init__(self, db: AsyncSession):
        """Initialize the agent with database session."""
        self.db = db
        self.settings = get_settings()
        self.client = AsyncAnthropic(api_key=self.settings.anthropic_api_key)

    async def _call_claude(
        self,
        messages: list[dict[str, str]],
        system: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: float = 0.7,
    ) -> str:
        """Call Claude API and log the conversation.

        Args:
            messages: List of message dicts with 'role' and 'content' keys
            system: Optional system prompt
            max_tokens: Maximum tokens in response (defaults to settings)
            temperature: Sampling temperature (0.0 to 1.0)

        Returns:
            The assistant's response text
        """
        max_tokens = max_tokens or self.settings.anthropic_max_tokens

        try:
            # Make API call
            response = await self.client.messages.create(
                model=self.settings.anthropic_model,
                max_tokens=max_tokens,
                system=system or "",
                messages=messages,
                temperature=temperature,
            )

            # Extract response content
            response_text = response.content[0].text

            # Log the conversation
            await self._log_conversation(
                messages=messages,
                response=response_text,
                system=system,
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
            )

            return response_text

        except Exception as e:
            logger.error(f"Claude API call failed: {e}")
            raise

    async def _log_conversation(
        self,
        messages: list[dict[str, str]],
        response: str,
        system: Optional[str] = None,
        input_tokens: Optional[int] = None,
        output_tokens: Optional[int] = None,
        model: Optional[str] = None,
        tool_calls: Optional[list[dict[str, Any]]] = None,
        prompt_version: Optional[str] = None,
        run_diagnostics: Optional[dict[str, Any]] = None,
        redaction_events: Optional[list[RedactionEvent]] = None,
    ) -> None:
        """Log conversation to database for training data collection.

        IMPORTANT: Per DEC-006, only anonymized content should be passed to this method.
        The caller is responsible for anonymizing any PII before logging.

        Args:
            messages: User messages (should be anonymized)
            response: LLM response
            system: System prompt used
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            model: Model used (defaults to anthropic_model from settings)
            tool_calls: Agentic-loop tool calls made while producing this response
            prompt_version: Version tag of the system prompt used
            run_diagnostics: Per-run diagnostics stored under
                `extra_data["run_diagnostics"]` on the assistant row — how this
                response was actually produced (agentic loop vs. single-shot
                fallback, and why). See DEC-026 and `src/api/diagnostics.py`.
            redaction_events: PII redaction events aggregated across this
                whole visit-prep request, stored under
                `extra_data["redaction_events"]` on the assistant row — type
                + span + stable per-entity id only, never the matched
                substring (issue #16, DEC-006).
        """
        try:
            model_name = model or self.settings.anthropic_model

            # Log user messages
            for msg in messages:
                log_entry = ConversationLog(
                    role=msg["role"],
                    content=msg["content"],
                    extra_data={
                        "system": system,
                        "anonymized": True,  # Per DEC-006
                    } if system else {"anonymized": True},
                )
                self.db.add(log_entry)

            # Log assistant response
            assistant_extra_data = {
                "system": system,
                "model": model_name,
                "anonymized": True,  # Per DEC-006
            }
            if tool_calls:
                assistant_extra_data["tool_calls"] = tool_calls
            if prompt_version:
                assistant_extra_data["prompt_version"] = prompt_version
            if run_diagnostics:
                assistant_extra_data["run_diagnostics"] = run_diagnostics
            if redaction_events:
                assistant_extra_data["redaction_events"] = [
                    e.to_dict() for e in redaction_events
                ]

            assistant_log = ConversationLog(
                role="assistant",
                content=response,
                extra_data=assistant_extra_data,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            )
            self.db.add(assistant_log)

            await self.db.flush()

        except Exception as e:
            logger.warning(f"Failed to log conversation: {e}")
            # Don't fail the main operation if logging fails

    def _parse_json_response(self, response: str) -> Optional[dict[str, Any]]:
        """Parse JSON from Claude's response with fallback handling.

        Attempts multiple parsing strategies:
        1. Direct JSON parse
        2. Extract JSON from code blocks
        3. Return None if all fail

        Args:
            response: Claude's response text

        Returns:
            Parsed JSON dict or None if parsing fails
        """
        # Try direct parse
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            pass

        # Try extracting from code blocks
        import re

        # Match ```json ... ``` or ``` ... ```
        code_block_pattern = r"```(?:json)?\s*([\s\S]*?)\s*```"
        matches = re.findall(code_block_pattern, response)

        for match in matches:
            try:
                return json.loads(match)
            except json.JSONDecodeError:
                continue

        # Try finding JSON object in text
        json_pattern = r"\{[\s\S]*\}"
        matches = re.findall(json_pattern, response)

        for match in matches:
            try:
                return json.loads(match)
            except json.JSONDecodeError:
                continue

        # Try repairing an apparently-truncated response — see
        # _repair_truncated_json's docstring. Only reachable once every
        # exact-parse strategy above has failed, so this never masks a
        # response that was already well-formed.
        start = response.find("{")
        if start != -1:
            repaired = _repair_truncated_json(response[start:])
            if repaired:
                try:
                    return json.loads(repaired)
                except json.JSONDecodeError:
                    pass

        return None
