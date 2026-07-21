"""Auto-discovery of a reachable Ollama base URL for the Settings page (issue #48).

Most users run Ollama on the same machine at its default address, so the
Settings page's Base URL field shouldn't require typing anything in that
case. This probes a short, ordered list of well-known candidate addresses
and returns the first one that responds to Ollama's own health check.
"""

import httpx

# Ordered by likelihood for this app's target use case (single local
# machine, per DEC-009) — kept as a simple flat list so a new candidate
# (e.g. a WSL-specific address) is a one-line addition, not a logic change.
CANDIDATE_OLLAMA_URLS = [
    "http://localhost:11434",
    "http://127.0.0.1:11434",
    "http://host.docker.internal:11434",  # Ollama on the host, app in Docker
    "http://172.17.0.1:11434",  # Docker's default bridge gateway on Linux
]

# Short per-candidate timeout — discovery probes several addresses in
# sequence, most of which won't exist on a given machine, and a hung/
# firewalled candidate shouldn't make the whole scan noticeably slow.
_PROBE_TIMEOUT_SECONDS = 1.5


async def probe_ollama_url(base_url: str) -> bool:
    """True if `base_url` responds to Ollama's health check (/api/tags)."""
    try:
        async with httpx.AsyncClient(timeout=_PROBE_TIMEOUT_SECONDS) as client:
            response = await client.get(f"{base_url}/api/tags")
            return response.status_code == 200
    except (httpx.RequestError, httpx.TimeoutException):
        return False


async def discover_ollama_url() -> str | None:
    """Return the first candidate URL that responds, or None if none do."""
    for candidate in CANDIDATE_OLLAMA_URLS:
        if await probe_ollama_url(candidate):
            return candidate
    return None
