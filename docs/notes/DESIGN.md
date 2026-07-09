# HealthSteward — Technical Design Document

**Snapshot as of:** DEC-015 · 2026-07-08

This is a point-in-time architecture snapshot, not a living doc — it reflects the system as understood at the DEC entry above and is re-written only when a subsequent DEC represents a genuine architectural shift (new/removed subsystem, changed trust boundary, deprecated core pattern), not on every change. See `CLAUDE.md` for the re-snapshot rule. For decision-by-decision detail, see `docs/notes/DECISIONS.md`; for narrative build history, see `docs/notes/DEVELOPMENT_LOG.md`.

This doc borrows structure from ML technical design docs (problem framing, system design, evaluation, rollout, risks), but HealthSteward isn't a trained-model system — no feature store, no hyperparameter tuning, no offline precision/recall. It's an **LLM application**: prompting + agentic tool use + deterministic parsing layered over off-the-shelf models (Claude API, local Ollama). Sections below are reinterpreted accordingly rather than applied by template.

---

## 1. Problem & Motivation

**Problem:** Patients managing fragmented care — multiple specialists, no shared record system — carry an unpaid coordination job: remembering what changed since the last visit, which labs are pending, what to raise with which doctor. This falls hardest on people with the least capacity to carry it (mid-flare, mid-crisis), and nobody on the clinical side owns it.

**Approach:** Treat it as a coordination problem, not a records problem. Ingest documents providers already give you (AVS PDFs), track what's changed and what's open, and turn that into something concrete for the next visit — running locally by default, because a tool holding this much health history shouldn't require sending it to a server to be useful.

Full motivation: see README "Motivation" section (kept there since it's the primary pitch; not duplicated here).

## 2. Goals & Non-Goals

**Goals:**
- Generate genuinely useful, specialty-relevant visit-prep questions from the patient's own data
- Keep health data local by default; anonymize anything that must leave the machine
- Turn parsed AVS data into closed-loop action (follow-ups booked, labs done, referrals scheduled), not just storage
- Degrade gracefully — a failing LLM call or unreliable tool-use backend should never block the user from getting *something* useful

**Explicit non-goals (stated once here rather than left implicit):**
- **Not a clinical decision-support tool.** Generated questions are prompts for a conversation with a real clinician, not diagnostic or treatment guidance. No automated clinical-safety validation exists or is planned — human review (the patient reading the output before a real appointment) is the only safety mechanism today.
- **Not multi-user yet.** DEC-001 (family sharing) is deferred pending a decision, not built toward.
- **Not HIPAA-scoped.** Personal/family use, not a covered entity — see DEC-001's privacy analysis.
- **No A/B testing, canary rollout, or drift-monitoring infrastructure.** Single-user local app, no population to canary against — this is a deliberate scope cut, not an oversight (contrast with the eval/monitoring gaps in §8, which *are* real gaps).
- **No real drug-interaction checking today** — `get_medication_details` exposes existing data for the model to reason over, it is not a licensed interaction database (tracked: issue #24).

## 3. System Design

```mermaid
flowchart TD
    PDF[AVS PDF<br/>data/avs/] --> OllamaParse[Ollama<br/>local, qwen2.5:7b]
    OllamaParse -->|extracted items| Review[Review & Confirm]
    Review --> DB[(SQLite)]

    DB -->|raw past visits| Select[Context Selection]
    Select -->|stage 2: relevance scoring<br/>on raw, unanonymized text| OllamaScore[Ollama<br/>local, qwen2.5:7b]
    OllamaScore --> Select
    Select -->|stage 4: anonymize| Anon[PII Anonymization]
    Anon --> Loop[Agentic Tool-Use Loop]

    Loop -->|prompt + tools| Backend[Pluggable LLM Backend<br/>Claude API or local Ollama]
    Backend -->|tool call: get_medication_details<br/>or lookup_past_visits| Tools[Visit Prep Tools]
    Tools -->|query, then anonymize| DB
    Tools -->|anonymized tool result| Backend
    Backend -->|final text, up to agent_max_turns| Loop
    Loop -->|falls back to single-shot<br/>if loop doesn't converge| DB

    DB --> API[FastAPI]
    API --> UI[React + TypeScript UI]
```

**Two LLMs, two trust boundaries:** Ollama runs locally and never touches the network — it parses raw PDFs and scores relevance of raw (pre-anonymization) visit history. The pluggable backend (Claude or local Ollama, per `LLM_PROVIDER`) only ever receives already-anonymized data — anonymization happens before the agentic loop starts, and every tool result fed back into the loop is anonymized the same way for both backends.

**Tech stack:** FastAPI + SQLAlchemy (async) + SQLite · React 19 + TypeScript + Tailwind + Vite · Claude API (Sonnet) or local Ollama for the agentic loop · Ollama (qwen2.5:7b) for PDF parsing and relevance scoring · Alembic migrations.

Full component-level detail: `docs/notes/IMPLEMENTATION.md`.

## 4. Data & Privacy

**Data sources:** `src/data/models.py` — `HealthProfile`, `Condition`, `Medication`, `Doctor`, `Appointment`, `Document`, `Vitals`, `LabOrder`, `Referral`, `FollowUp`. All primary keys are UUIDs, not sequential integers, specifically to avoid inferring record counts (DEC-004).

**Labelling / ground truth:** N/A — nothing is trained. "Labels" in this system are user-confirmed extractions: AVS-parsed items are always presented for review before being written to the profile (DEC-010), never auto-applied.

**PII boundary (DEC-006, hard constraint — see `CONTRIBUTING.md`):** structured fields get deterministic replacement (name → "Patient", DOB → age), free text goes through regex + spaCy NER. Documented as best-effort on free text, not a guarantee — genuinely novel bypasses are a `SECURITY.md`-reportable finding, not a bug ticket.

**Local-only enforcement:** `src/parsers/agent/ollama_chat.py` has a hard localhost-only safety check — PDF parsing cannot silently start talking to an external host even if misconfigured.

## 5. AI Approach (reinterpreted "Modeling")

**Baseline:** single-shot prompt-in/JSON-out generation (pre-DEC-009) is the floor every enhancement must not regress below. This is why DEC-013's agentic loop is fallback-not-hard-failure by design — if the loop can't converge within `agent_max_turns` or a backend produces malformed tool calls, `prepare_visit()` falls back to the original single-shot call. No functional regression is possible, by construction.

**Model selection:** Claude API (Sonnet) is the default agentic backend, not local Ollama, because the dev machine (M3, 8GB RAM) can only run 4-bit quantized 7-8B models, and small quantized models produce unreliable tool-calling — malformed JSON, wrong tool calls, non-convergence (DEC-009). Cost is negligible for personal use (~$1/month). Ollama remains available for simpler tasks that don't need reliable structured tool-calling: PDF parsing, context-selection relevance scoring, and as a fully-local `LLM_PROVIDER=ollama` option for visit prep with degraded reliability.

**Prompting:** two system prompt templates (specialty-aware and generic fallback) in `src/agents/visit_prep.py`, enriched with ICD-10 → specialty tagging, medication → prescribing-specialty tagging, and clinic-name specialty inference (DEC-011). These prompts are the actual product logic — see the prompt-change gap in §8.

## 6. Agentic Loop Design

Bounded tool-use loop (`_run_agentic_loop`, DEC-009/DEC-013): send context + tool specs → execute any requested tool calls → anonymize results → append → repeat until final text or `agent_max_turns` (default 6) exhausted. Two read-only tools today, deliberately bounded scope for v1: `get_medication_details`, `lookup_past_visits`. `LLMBackend` abstraction makes this work identically for Claude and Ollama.

Follow-up tool work already scoped: widen `lookup_past_visits`'s default window (#21), lab results (#22), procedures/hospitalizations (#23), drug-interaction checker (#24).

## 7. Rollout

No staged rollout — single-user local app, changes ship by pulling `main` and restarting the local server. `AGENT_TOOL_USE_ENABLED` acts as a kill switch for the agentic path specifically (falls back to always-single-shot) if a regression is suspected, without needing a full rollback.

## 8. Evaluation, Monitoring & Known Gaps

**What exists:** `ConversationLog` records every LLM call (anonymized content + token counts) for future distillation. Backend test suite (72+ tests) verifies plumbing — loop convergence, tool execution, anonymization boundaries, fallback triggering.

**What's missing (real gaps, not scope cuts):**
- **No quality evaluation of generated output.** Tests mock the LLM and verify the pipeline works, not whether generated visit-prep questions are actually good — relevant, non-redundant, correctly specialty-scoped. This is the one gap that maps to the "Success Metrics / Offline Evaluation" section of a standard ML design doc, unaddressed here.
- **No visibility into agentic-loop fallback rate.** `ConversationLog` has the data, but nothing surfaces how often the loop falls back to single-shot in practice. A silently degrading backend (e.g. a Claude API or Ollama version change that breaks tool-calling) would be invisible.
- **No frontend test coverage** (tracked: issue #27).

## 9. Alternatives Considered

Full detail lives in `docs/notes/DECISIONS.md` (DEC-001 through DEC-015) — this section is a pointer, not a duplicate. Headline calls: Claude native tool use over the Agent SDK or LangGraph (DEC-009 — no new deps, framework overhead unwarranted for a single agent); SQLite over Postgres for Phase 1 (DEC-003); UUID over integer primary keys (DEC-004); local-only Ollama for PDF parsing over any cloud OCR/vision option (DEC-005/DEC-010).

## 10. Risks

- **Clinical safety.** Neither ML-eval nor typical software-design risk framing covers this: generated output is health-adjacent guidance, and the only safety mechanism is the patient reading it before a real appointment. No automated check exists for a plausible-but-wrong suggestion (e.g. a hallucinated drug interaction, or a misread lab trend). Framed as a permanent human-in-the-loop requirement, not a gap to close via eval — but worth stating outright rather than leaving implicit in "not a replacement for clinical judgment" (README).
- **External dependency risk.** Anthropic API pricing/availability changes affect the default agentic backend directly (DEC-009 chose Claude specifically for reliable tool-calling — a price or access change has no equally-reliable local fallback today). Ollama model tags (`qwen2.5:7b`, `llama3.2`) are referenced by tag, not pinned digest — a silent upstream model update could change parsing/scoring behavior without any code change here.
- **Prompt-change management.** The specialty-aware system prompts (`SYSTEM_PROMPT_TEMPLATE`, `SYSTEM_PROMPT_GENERIC`) are the actual product behavior, but changes to them go through normal code review with no dedicated process (no prompt versioning, no before/after quality comparison). Low-stakes at current scale; worth a lightweight convention (e.g. note prompt changes explicitly in the dev log, per existing discipline) if the loop gains more agentic freedom.
- Standard risks already covered elsewhere: fallback-not-hard-failure removes most agentic-loop regression risk by construction (§5); PII anonymization gaps are `SECURITY.md`-reportable, not silent.
