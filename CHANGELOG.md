# Changelog

All notable changes to HealthSteward are documented here. Format loosely follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); this project doesn't yet follow strict semantic versioning (pre-1.0, `v0.x.y-alpha` releases).

For the *why* behind a change, see `docs/notes/DECISIONS.md` (architectural rationale) and `docs/notes/DEVELOPMENT_LOG.md` (narrative build history) — this file tracks *what* shipped, not the reasoning.

## [Unreleased]

### Added
- `CONTRIBUTING.md`, `SECURITY.md`, this changelog
- DEC-015: visit-prep tool scope audit — scoped follow-ups for lab results, visit-notes windowing, and procedures/hospitalizations (issues #21–23), plus a drug-interaction checker and scheduled push notifications (issues #24–25)
- `docs/tdd.html` — public technical design doc (system architecture diagram, decisions/tradeoffs, walkthrough, risks/gaps linked to issues #27/#29/#30/#31) and `docs/SITE_STYLE_GUIDE.md`, the living style reference for it and the landing page

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

[Unreleased]: https://github.com/nidhi-menon/HealthSteward/compare/v0.1.0-alpha...HEAD
[0.1.0-alpha]: https://github.com/nidhi-menon/HealthSteward/releases/tag/v0.1.0-alpha
