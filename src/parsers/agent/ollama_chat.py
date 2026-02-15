"""Ollama /api/chat client for per-section LLM extraction."""

from __future__ import annotations

import json
import urllib.request
import urllib.error
from urllib.parse import urlparse

from src.config import get_settings


def _get_chat_url() -> str:
    """Get the Ollama chat API URL from settings."""
    base = get_settings().ollama_base_url.rstrip("/")
    return f"{base}/api/chat"


def _check_localhost(url: str) -> None:
    """Safety: ensure we only ever talk to localhost."""
    parsed = urlparse(url)
    if parsed.hostname not in ("localhost", "127.0.0.1", "::1"):
        raise RuntimeError(
            f"BLOCKED: Refusing to send medical data to non-local host: {parsed.hostname}. "
            "This parser only sends data to a local Ollama instance for privacy."
        )


def _chat_completion(messages: list[dict], model: str) -> dict:
    """Single call to Ollama /api/chat. Returns the full response dict."""
    url = _get_chat_url()
    _check_localhost(url)

    payload: dict = {
        "model": model,
        "messages": messages,
        "stream": False,
        "options": {
            "temperature": 0.1,
            "num_predict": 4096,
            "num_ctx": 8192,
        },
    }

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
    )

    try:
        with urllib.request.urlopen(req, timeout=600) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as e:
        raise RuntimeError(
            f"Cannot connect to Ollama at {url}. "
            "Make sure Ollama is running: ollama serve"
        ) from e


def _parse_json_from_content(content: str) -> dict | None:
    """Try to extract JSON from assistant message content."""
    text = content.strip()
    if "```json" in text:
        text = text.split("```json", 1)[1]
    if "```" in text:
        text = text.split("```", 1)[0]
    text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}") + 1
        if start != -1 and end > start:
            try:
                return json.loads(text[start:end])
            except json.JSONDecodeError:
                return None
    return None


def direct_chat(
    system_prompt: str,
    user_message: str,
    model: str,
) -> dict | None:
    """Single LLM call for per-section extraction.

    Returns parsed JSON or None.
    """
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
    ]
    result = _chat_completion(messages, model)
    content = result.get("message", {}).get("content", "")
    return _parse_json_from_content(content) if content else None
