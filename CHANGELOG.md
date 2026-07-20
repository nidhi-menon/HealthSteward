# Changelog

All notable changes to HealthSteward are documented here. Format loosely follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); this project doesn't yet follow strict semantic versioning (pre-1.0, `v0.x.y-alpha` releases).

For the *why* behind a change, see `docs/notes/DECISIONS.md` (architectural rationale) and `docs/notes/DEVELOPMENT_LOG.md` (narrative build history) — this file tracks *what* shipped, not the reasoning.

## [Unreleased]

### Added
- Deterministic evaluation harness (v1) for visit-prep output quality — format validity, groundedness, specialty-scope, tool-call necessity, and Phase 1/Phase 2 retrieval-redundancy checks, runnable on-demand against the real pipeline (#29, DEC-018)
- Project-wide prompt versioning — every LLM prompt now carries a version tag, with change history in `docs/notes/PROMPT_CHANGELOG.md` (DEC-018)

### Fixed
- An unrecognized tool name called by the model during the agentic visit-prep loop was silently absorbed as a fake tool result instead of triggering the existing single-shot fallback (#53)
- Tool calls made during the agentic visit-prep loop were never recorded in `ConversationLog`, despite the field existing, so a completed run's tool-call trace was unrecoverable (#52)
- The Ollama/custom LLM backend never sent `stream: false`, so a real (multi-chunk) response body could raise an uncaught `json.JSONDecodeError`, likely degrading most real Ollama-backed visit-prep calls straight to the generic fallback response with no visible error
- `temperature` was sent top-level for the Ollama backend, which Ollama's native `/api/chat` silently ignores (needs nesting under `options`) — sampling temperature had no effect for Ollama-backed calls
- The agentic loop's backend HTTP call had no total wall-clock timeout, only a per-chunk read timeout, so a slow/trickling response could hang indefinitely with no error or fallback triggered
- The visit-prep system prompt's own stated 8-15 question requirement and its grounding guidance were being under-followed by local models — reinforced prompt wording, validated via the new eval harness (before/after: 0/5 → 3/5 cases passing format validity on identical fixtures)

## [0.2.0-alpha] - 2026-07-10

### Added
- `CONTRIBUTING.md`, `SECURITY.md`, this changelog
- DEC-015: visit-prep tool scope audit — scoped follow-ups for lab results, visit-notes windowing, and procedures/hospitalizations (issues #21–23), plus a drug-interaction checker and scheduled push notifications (issues #24–25)
- `docs/tdd.html` — public technical design doc (system architecture diagram, decisions/tradeoffs, walkthrough, risks/gaps linked to issues #27/#29/#30/#31) and `docs/SITE_STYLE_GUIDE.md`, the living style reference for it and the landing page
- `docs/DESIGN.md` — point-in-time technical design snapshot, plus a rewritten Personal Note centered on the coordination failure rather than specific diagnoses
- Deep-dive visuals for `docs/tdd.html`'s accordion sections, including a pipeline diagram for the 4-stage context selection walkthrough
- DEC-016: local Ollama is now the default agentic backend for visit prep (Claude and a new custom OpenAI-compatible provider are opt-ins); provider choice is now a runtime, DB-backed setting editable from a new Settings page, instead of `.env`-only
- `CODE_OF_CONDUCT.md` and `.github/` issue/PR templates, wired into the README and CONTRIBUTING
- README screenshots and a star ask for visibility
- Documented the five computed nudge types (past-due appointments, upcoming-without-prep, 14-day no-AVS window, vitals-trend alerts, unresolved follow-ups/labs/referrals) in `docs/tdd.html`'s proactive action items section (#40)

### Fixed
- Secrets of 8 characters or fewer returned unredacted from `GET /api/settings/` instead of masked
- An empty-string settings field (e.g. a cleared "Ollama Base URL") could silently override a working default instead of falling back to it
- `get_llm_backend()` and the agentic loop's tool-spec selection could disagree on which wire format to use for an unrecognized `llm_provider` value
- Restored a fast (~5s) connect-timeout for Ollama requests, lost when the agentic loop's HTTP client was consolidated — an unreachable/hung Ollama host no longer blocks a request for the full 120s generation timeout
- Token usage counts were no longer logged for the single-shot fallback path after the per-provider dispatch was consolidated

## [0.1.0-alpha] - 2026-07-06

Initial working build. Core feature set:

### Added
- Health profile management — conditions (ICD-10), medications, doctors, appointments
- AI visit preparation with intelligent 4-stage context selection (DEC-008)
- Specialty-aware visit prep — questions filtered/tagged to the relevant specialist (DEC-011)
- Agentic tool-use loop for visit prep, with pluggable Claude/Ollama backend and automatic fallback to single-shot generation (DEC-009, DEC-013)
- AVS PDF parsing — local-only Ollama parsing with section-routing architecture, review-before-apply flow (DEC-010)
- Proactive action items — post-AVS action panel and persistent "Needs Attention" overview section, with snooze/completion state (DEC-012)
- PII anonymization for external LLM calls — deterministic field replacement, regex, spaCy NER (DEC-006)
- Public landing page and brand mark (DEC-014)

[Unreleased]: https://github.com/nidhi-menon/HealthSteward/compare/v0.2.0-alpha...HEAD
[0.2.0-alpha]: https://github.com/nidhi-menon/HealthSteward/compare/v0.1.0-alpha...v0.2.0-alpha
[0.1.0-alpha]: https://github.com/nidhi-menon/HealthSteward/releases/tag/v0.1.0-alpha
