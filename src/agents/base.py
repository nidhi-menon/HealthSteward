"""Base agent class with Claude API integration and conversation logging."""

import json
from typing import Any, Optional

from anthropic import AsyncAnthropic
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import get_settings
from src.data.models import ConversationLog


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
    ) -> None:
        """Log conversation to database for training data collection.

        Args:
            messages: User messages sent to Claude
            response: Claude's response
            system: System prompt used
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
        """
        try:
            # Log user messages
            for msg in messages:
                log_entry = ConversationLog(
                    role=msg["role"],
                    content=msg["content"],
                    extra_data={"system": system} if system else None,
                )
                self.db.add(log_entry)

            # Log assistant response
            assistant_log = ConversationLog(
                role="assistant",
                content=response,
                extra_data={
                    "system": system,
                    "model": self.settings.anthropic_model,
                },
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

        return None
