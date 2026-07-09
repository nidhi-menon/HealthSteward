# Security Policy

## Reporting a vulnerability

If you find a security issue in HealthSteward — anything from a way to bypass the PII anonymization layer, to a path that leaks patient data to a place it shouldn't, to a standard web vulnerability (injection, auth bypass, etc.) — please report it privately rather than opening a public issue.

**Preferred:** Use [GitHub's private vulnerability reporting](https://github.com/nidhi-menon/HealthSteward/security/advisories/new) for this repo (Security tab → "Report a vulnerability").

**Alternative:** Open a GitHub Discussion asking for a private channel to reach the maintainer, without describing the vulnerability itself in public.

Please include:
- What you found and why it's a security issue (not just a bug)
- Steps to reproduce, if applicable
- The affected version/commit

There's no bug bounty — this is a pre-1.0, single-maintainer, open-source project — but reports are taken seriously and credited in the fix.

## What's in scope

HealthSteward handles personal health data, so the security posture that matters most is the **privacy boundary**, not just conventional web-app security:

- **PII anonymization bypass** — any way that unanonymized patient data (name, DOB, contact info, etc.) reaches the Claude API when anonymization should have caught it. See `src/utils/anonymization.py` and DEC-006 for the intended guarantees. Note this is documented as *best-effort*, not a hard guarantee, for free-text NER detection — genuinely novel bypasses of the deterministic/regex layers are still worth reporting.
- **Local-only boundary violations** — any way that document/PDF parsing data reaches a non-localhost endpoint. `src/parsers/agent/ollama_chat.py` has a safety check for this; a way around it is a real finding.
- **Tool-result leakage in the agentic loop** — the visit-prep agentic loop (`src/agents/tools.py`) anonymizes tool results before feeding them back to the LLM; a path where raw data slips through is in scope.
- **Standard web vulnerabilities** — SQL injection, auth bypass, XSS, path traversal (especially around file upload/parsing in `src/api/documents.py`), SSRF, etc.
- **Dependency vulnerabilities** with a realistic exploit path in this app's usage.

## What's out of scope

- The app is currently designed for local, single-user use (see DEC-001 — multi-user/family sharing is deferred). Reports assuming a hardened multi-tenant deployment aren't applicable yet.
- Physical access to the machine running HealthSteward (the threat model is network/remote, not "someone has your laptop unlocked").
- Issues in third-party dependencies without a demonstrated impact on this app specifically (report those upstream instead).

## Supported versions

Pre-1.0 — only the latest release/`main` is supported. There's no backport policy yet.
