# HealthSteward — Technical Design Document

**Snapshot as of:** DEC-042 · 2026-08-24

This is a point-in-time architecture snapshot, not a living doc — it reflects the system as understood at the DEC entry above and is re-written only when a subsequent DEC represents a genuine architectural shift (new/removed subsystem, changed trust boundary, deprecated core pattern), not on every change. See `CLAUDE.md` for the re-snapshot rule. For decision-by-decision detail, see `docs/notes/DECISIONS.md`; for narrative build history, see `docs/notes/DEVELOPMENT_LOG.md`.

This doc borrows structure from ML technical design docs (problem framing, system design, evaluation, rollout, risks), but HealthSteward isn't a trained-model system — no feature store, no hyperparameter tuning, no offline precision/recall. It's an **LLM application**: prompting + agentic tool use + deterministic parsing layered over off-the-shelf models (local Ollama, Claude API, or any custom OpenAI-compatible provider). Sections below are reinterpreted accordingly rather than applied by template.

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
- Accept structured data from other sources the patient already has (FHIR export bundles), not just AVS PDFs, without silently overwriting conflicting records
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
    PDF[AVS PDF<br/>data/avs/&lt;profile_id&gt;/] --> OllamaParse[Ollama<br/>local, qwen2.5:7b]
    OllamaParse -->|extracted items| Review[Review & Confirm]
    FHIR[FHIR Bundle<br/>file upload] -->|deterministic parse,<br/>fuzzy-dupe flag| Review
    Review --> DB[(SQLite)]

    DB -->|raw past visits| Select[Context Selection]
    Select -->|stage 2: relevance scoring<br/>on raw, unanonymized text| OllamaScore[Ollama<br/>local, llama3.2 default]
    OllamaScore --> Select
    Select -->|stage 4: anonymize| Anon[PII Anonymization]
    Anon --> Loop[Agentic Tool-Use Loop]

    Loop -->|prompt + tools| Backend[Pluggable LLM Backend<br/>Ollama default, or Claude / custom]
    Backend -->|tool call: get_medication_details<br/>or lookup_past_visits| Tools[Visit Prep Tools]
    Tools -->|query, then anonymize| DB
    Tools -->|anonymized tool result| Backend
    Backend -->|final text, up to agent_max_turns| Loop
    Loop -->|doesn't converge: another call to| Backend
    Loop -->|final questions, either path| DB

    DB --> API[FastAPI]
    API --> UI[React + TypeScript UI]
```

**Two LLMs, two trust boundaries:** Ollama runs locally and never touches the network — it parses raw PDFs and scores relevance of raw (pre-anonymization) visit history. The pluggable backend (Ollama by default, or Claude API, or any custom OpenAI-compatible provider, per `LLM_PROVIDER` — switchable at runtime from Settings, DEC-016) only ever receives already-anonymized data — anonymization happens before the agentic loop starts, and every tool result fed back into the loop is anonymized the same way regardless of backend.

**Tech stack:** FastAPI + SQLAlchemy (async) + SQLite · React 19 + TypeScript + Tailwind + Vite · pluggable agentic backend — Ollama (`llama3.2` default) by default, or Claude API (Sonnet), or any custom OpenAI-compatible provider, switchable at runtime (DEC-016) · Ollama (`qwen2.5:7b`) for PDF parsing, Ollama (`llama3.2` default, reused rather than a dedicated model) for context-selection relevance scoring · Alembic migrations.

Full component-level detail: `docs/notes/IMPLEMENTATION.md`.

## 4. Data & Privacy

**Data sources:** `src/data/models.py` — `HealthProfile`, `Condition`, `Medication`, `Doctor`, `Appointment`, `Document`, `Vitals`, `LabOrder`, `Referral`, `FollowUp`. All primary keys are UUIDs, not sequential integers, specifically to avoid inferring record counts (DEC-004). AVS source PDFs live under `data/avs/<profile_id>/` (DEC-030), partitioned per profile so cross-profile leakage is structurally impossible rather than merely filtered on the current screen; unassignable files land in `_unassigned/` rather than a silent guess. As of DEC-031, structured records can also arrive via one-time FHIR Bundle file upload (two resource types at launch), deterministically parsed with a fuzzy name-match flag against existing `Condition`/`Medication` rows surfaced in the preview UI — nothing is auto-merged, and full reconciliation across sources (issue #97) is explicitly deferred.

**Labelling / ground truth:** N/A — nothing is trained. "Labels" in this system are user-confirmed extractions: AVS-parsed and FHIR-imported items are always presented for review before being written to the profile (DEC-010, DEC-031), never auto-applied.

**Deletion:** profiles use soft-delete with a 30-day lazy-expiry cleanup, not a scheduled purge job (DEC-027) — every profile-scoped route (including export, per the #123 amendment) resolves through `get_live_profile_or_404` so a deleted profile is uniformly unreachable. AVS source files are not deleted at soft-delete time; deletion is deferred to purge time so a restore within the 30-day window doesn't come back missing its originals (DEC-030).

**Visit-prep history:** each `prepare_visit()` run is appended to a separate, read-only, unpruned history table rather than overwriting the profile's current prep (DEC-034) — regenerating never destroys a prior run.

**PII boundary (DEC-006, hard constraint — see `CONTRIBUTING.md`):** structured fields get deterministic replacement (name → "Patient", DOB → age); free text goes through regex + spaCy NER and, as of DEC-036, scoped per-entity redaction tokens rather than a flat category label — the same doctor mentioned twice in one field maps to the same token, distinct entities get distinct tokens, and tokens are guarded on output (never re-hydrated back to the real value). Documented as best-effort on free text, not a guarantee — genuinely novel bypasses are a `SECURITY.md`-reportable finding, not a bug ticket. Every redaction event (type + span + stable hashed id, never the raw value) is logged per visit-prep request for auditability (DEC-029).

**Local-only enforcement:** `src/parsers/agent/ollama_chat.py` has a hard localhost-only safety check — PDF parsing cannot silently start talking to an external host even if misconfigured.

## 5. AI Approach (reinterpreted "Modeling")

**Baseline:** single-shot prompt-in/JSON-out generation (pre-DEC-009) is the floor every enhancement must not regress below. This is why DEC-013's agentic loop is fallback-not-hard-failure by design — if the loop can't converge within `agent_max_turns` or a backend produces malformed tool calls, `prepare_visit()` falls back to the original single-shot call. No functional regression is possible, by construction.

**Model selection:** Local Ollama is the default agentic backend as of DEC-016, which supersedes DEC-009's original default choice (not its underlying finding). DEC-009's tool-reliability finding is still true — the dev machine (M3, 8GB RAM) can only run 4-bit quantized 7-8B models, and small quantized models produce unreliable tool-calling (malformed JSON, wrong tool calls, non-convergence) — but defaulting the most-used flow to an external API sat awkwardly next to the project's local-first pitch. Claude API (Sonnet) and any custom OpenAI-compatible provider (OpenAI, OpenRouter, Groq, a self-hosted server, etc.) remain fully supported as explicit opt-ins, switchable at runtime from a Settings page (DB-backed, no `.env` edit or restart needed) rather than `.env`-only. Cost for the opt-in Claude path is negligible for personal use (~$1/month). Ollama also continues to handle simpler tasks that don't need reliable structured tool-calling: PDF parsing and context-selection relevance scoring.

**Prompting:** two system prompt templates (specialty-aware and generic fallback) in `src/agents/visit_prep.py`, enriched with ICD-10 → specialty tagging, medication → prescribing-specialty tagging, and clinic-name specialty inference (DEC-011). These prompts are the actual product logic — every wording change is versioned and logged in `docs/notes/PROMPT_CHANGELOG.md` (DEC-018), and validated against the eval harness in §8 where the harness's fixtures cover the change.

## 6. Agentic Loop Design

Bounded tool-use loop (`_run_agentic_loop`, DEC-009/DEC-013): send context + tool specs → execute any requested tool calls → anonymize results → append → repeat until final text or `agent_max_turns` (default 6) exhausted. Two read-only tools today, deliberately bounded scope for v1: `get_medication_details`, `lookup_past_visits`. `LLMBackend` abstraction makes this work identically for Claude, Ollama, and any custom OpenAI-compatible provider (DEC-016).

Follow-up tool work already scoped: widen `lookup_past_visits`'s default window (#21), lab results (#22), procedures/hospitalizations (#23), drug-interaction checker (#24).

## 7. Rollout

No staged rollout — single-user local app, changes ship by pulling `main` and restarting the local server. `AGENT_TOOL_USE_ENABLED` acts as a kill switch for the agentic path specifically (falls back to always-single-shot) if a regression is suspected, without needing a full rollback.

## 8. Evaluation, Monitoring & Known Gaps

**What exists:** `ConversationLog` records every LLM call (anonymized content + token counts) for future distillation. Backend test suite (119+ tests) verifies plumbing — loop convergence, tool execution, anonymization boundaries, fallback triggering.

**Eval harness v1 (DEC-018, `eval/`), deterministic-only:** run on-demand via `python -m eval.run` against a real pipeline + real LLM backend (not mocks), at `temperature=0.0` for run-to-run comparability. Catches gross regressions (hallucination, scope violations, malformed output, retrieval rule breaks). Two eval surfaces, matching `docs/tdd.html`'s original plan:
- **Retrieval** (`eval/retrieval_stage1.py`) — Stage 1's rules-based filtering, checked by exact assertion against synthetic fixtures.
- **Generation** (`eval/scorers.py`) — format validity (question count, scaled per-case to how much real patient data the case has rather than a flat floor — see `expected_min_questions()`), a cheap entity-match groundedness pass (kept as a fast free smoke test, not the paper-citable number — see below), a deterministic specialty-scope checker, plus two observational (non-pass/fail) checks: tool-call necessity and Phase 1/Phase 2 retrieval redundancy.

Results are diffed against the prior run (`eval/results/`, gitignored) rather than checked against a fixed bar, since "better or worse than last time" is the operative question for a prompt-change review. Every prompt in the codebase is now versioned as a companion convention (`docs/notes/PROMPT_CHANGELOG.md`), so a behavior change is traceable to the exact prompt wording that caused it. Standing up v1 against a real Ollama server (not just mocks) surfaced and fixed three previously-hidden production bugs in the Ollama/custom backend path (missing `stream: false`, misplaced `temperature`, no total-call timeout) — validates that at least one real-backend run was worth including in v1 rather than unit-testing the scorers in isolation.

**LLM-judge factual-groundedness pass, shipped (DEC-042, `eval/judge.py`):** the deeper property v1's entity-match couldn't reach — whether generated claims are actually supported by the patient's data, not just whether they happen to name a known entity — is now measured by a real judge model (a separate, stronger tier than any Claude model used for generation, to avoid self-grading bias), enumerating and verdicting every distinct factual claim against the patient's actual record. Getting a trustworthy number required correcting the judge itself twice (a `context_summary` coverage gap and a rubric miscalibration both produced false "0% unsupported" readings before being found and fixed) — the full correction chain, including two prompt-level mitigations that were tried and reverted after proper validation, is in DEC-042. A **deterministic post-generation guardrail** (`src/agents/output_guardrails.py`) acts on what the judge found: it runs on every real `prepare_visit()` call (production code, not eval-only) and strips content presupposing a test, referral, medication, or past visit not on file, plus specialty-management-convention and named-external-authority claims this app has no source for anywhere. Together, real final measured rate: **1.1% unsupported-claim rate (1/91 scored claims)**, `--trials 3`, on the current 5-case fixture set — down from the original 56% entity-match figure, which was never actually a hallucination measurement to begin with.

**What's still missing (real gaps, not scope cuts):**
- **Relevance/usefulness and non-redundancy judging, not yet built.** No cheap deterministic proxy exists for either — both remain the named backlog per `docs/tdd.html`'s Evaluation Plan tab. Distinct from groundedness above, which is now covered.
- **One deliberately-deferred groundedness pattern** (issue #164): a dosage-as-"starting point" claim and a patient-age presupposition both need new fixture plumbing (the production `Medication.start_date`/`HealthProfile.date_of_birth` fields exist but eval fixtures never populate them) plus a policy decision, not a quick pattern addition — unlike every other guardrail pattern shipped, which is always-unsupported by construction.
- ~~**No visibility into agentic-loop fallback rate in production.**~~ *Closed by DEC-026 (issue #30):* every `prepare_visit()` run now records how it was actually produced — agentic loop, or single-shot fallback and why — in `ConversationLog.extra_data["run_diagnostics"]`, readable via `GET /api/diagnostics/visit-prep-fallback`. Still a read-on-demand number rather than an alert: nothing notices a rising fallback rate unless someone looks.
- **No frontend test coverage** (tracked: issue #27) — worth re-verifying before citing further; at least one frontend test file now exists (`VisitPrep.versions.test.tsx`), so this claim may itself be stale independent of this snapshot's actual scope.

## 9. Alternatives Considered

Full detail lives in `docs/notes/DECISIONS.md` (DEC-001 through DEC-042) — this section is a pointer, not a duplicate. Headline calls: Claude native tool use over the Agent SDK or LangGraph (DEC-009 — no new deps, framework overhead unwarranted for a single agent); SQLite over Postgres for Phase 1 (DEC-003); UUID over integer primary keys (DEC-004); local-only Ollama for PDF parsing over any cloud OCR/vision option (DEC-005/DEC-010); Ollama flipped to the default agentic backend over keeping Claude as default (DEC-016); deterministic-only eval harness v1 over building the full judge-dependent plan in one pass (DEC-018); soft-delete with lazy expiry over a scheduled purge job (DEC-027); FHIR import scoped to file-upload, two resource types, deferred reconciliation rather than a full ingestion/reconciliation system in one pass (DEC-031); scoped per-entity redaction tokens, guarded not re-hydrated, over the original flat-category free-text redaction (DEC-036); a deterministic post-generation guardrail over further prompt-wording iteration for hallucination mitigation, after two prompt-level attempts were tried and reverted on proper validation (DEC-042).

## 10. Risks

- **Clinical safety.** Generated output is health-adjacent guidance, and the patient reading it before a real appointment remains the primary safety mechanism — that hasn't changed. What has changed (DEC-042): an automated check now exists and is measured — the LLM-judge groundedness pass plus the deterministic output guardrail catch and remove a real, evidenced set of hallucination patterns (presupposed tests/referrals/medications, named-authority and specialty-convention claims) before a patient sees them, bringing the measured unsupported-claim rate to 1.1% on the current fixture set. This narrows but does not close the gap: it's measured against 5 synthetic fixture cases, not validated against the diversity of real patient data, and known-uncovered patterns remain (fabricated numeric specifics; the deferred issue #164 items). Still framed as a permanent human-in-the-loop requirement, not a gap eval alone can fully close — but "no automated check exists" is no longer accurate, and the interim AI-generated-content disclaimer added to visit-prep (issue #105) makes the human-in-the-loop expectation explicit in the UI itself, not just implicit in README language.
- **External dependency risk.** Ollama model tags (`qwen2.5:7b`, `llama3.2`) are referenced by tag, not pinned digest — a silent upstream model update could change parsing/scoring/visit-prep behavior without any code change here, and this now affects the default agentic backend directly since Ollama is the default (DEC-016). Anthropic API and any custom provider's pricing/availability changes only matter to whoever has opted into them from Settings.
- **Prompt-change management.** Resolved by DEC-018: every prompt in the codebase is versioned, content changes are logged in `docs/notes/PROMPT_CHANGELOG.md` with before/after eval evidence where the harness's fixtures cover the change, and `visit_prep.py`'s two prompts additionally log their version per-run via `ConversationLog.extra_data["prompt_version"]`. Residual gap: the eval harness only covers `visit_prep.py`'s generation prompts today — `context_selection.py`'s Stage 2 scoring prompt and the AVS parser's five extraction prompts are versioned for traceability but have no before/after quality signal yet if changed.
- Standard risks already covered elsewhere: fallback-not-hard-failure removes most agentic-loop regression risk by construction (§5); PII anonymization gaps are `SECURITY.md`-reportable, not silent.
