# HealthSteward Decision Log

This document tracks architectural discussions, decisions made, and the reasoning behind them. Use this to understand why things are the way they are, and to revisit decisions later.

---

## Decision Format

Each entry includes:
- **Date** - When discussed
- **Topic** - What we were deciding
- **Context** - Why this came up
- **Options Considered** - What we evaluated
- **Decision** - What we chose (or deferred)
- **Reasoning** - Why we made this choice
- **Status** - Decided / Deferred / Revisit

---

## Decisions

### DEC-001: Multi-User Family Sharing Architecture

**Date:** 2026-02-05

**Topic:** How to turn HealthSteward from a single-user local app into a shared family health vault

**Context:** User wants family members to access, view, and edit shared health profiles together.

**Options Considered:**

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| **1. Simple shared (no auth)** | Deploy to server, anyone with URL can access | Fast to build | No security, no audit trail |
| **2. Full multi-user** | User accounts, family groups, invites, roles | Proper security, accountability | More work |
| **3. Shared password** | Basic HTTP auth, family shares one password | Quick, some security | Can't track who did what |

**Deployment Options Discussed:**

| Option | Privacy Level | Notes |
|--------|---------------|-------|
| **Self-hosted (Raspberry Pi)** | Maximum | Data stays home, no third parties |
| **European VPS (Hetzner)** | High | Encrypted, GDPR compliant |
| **US PaaS (Fly.io, Railway)** | Moderate | Convenient but US jurisdiction |

**Privacy Concerns Raised:**

1. **HIPAA applicability** - Determined NOT applicable for personal family use (not a healthcare provider)

2. **Claude API data exposure** - Health data sent to Anthropic for AI features
   - Mitigation options: anonymize data before sending, or self-host LLM (Ollama)

3. **Third-party trust** - Auth providers (Clerk), hosting providers can theoretically access data
   - Mitigation: self-host everything, or use encrypted storage

4. **Data leakage points** - Database, backups, logs, transit
   - Standard mitigations: encryption at rest, HTTPS, don't log PII

**Recommended Architecture (if proceeding):**

Self-hosted maximum privacy option:
- Raspberry Pi or home server
- Tailscale for secure remote access
- Ollama with local LLM for AI features
- No third-party services

**Decision:** DEFERRED

**Reasoning:** User wants to consult partner before deciding whether to proceed with multi-user deployment, and which privacy/convenience trade-off to accept.

**Status:** Deferred - pending family discussion

**Follow-up:** Revisit when ready to proceed. Implementation plan will depend on chosen deployment strategy.

---

### DEC-002: Frontend Framework Choice

**Date:** 2026-02-05

**Topic:** Which frontend framework to use for the UI

**Context:** Needed a UI instead of just API/curl commands

**Options Considered:**

| Option | Pros | Cons |
|--------|------|------|
| **Streamlit** | Fastest, good for demos | Separate app, less polished |
| **Plain HTML/JS** | No build step, simple | Basic, manual DOM work |
| **React + Tailwind** | Modern, component-based, polished | More setup |

**Decision:** React + Tailwind + Vite + TypeScript

**Reasoning:**
- Building a real product, not just a demo
- Component architecture scales well for health data forms
- TanStack Query handles server state elegantly
- Tailwind enables fast, consistent styling
- TypeScript catches errors early

**Status:** Decided - Implemented

---

### DEC-003: Database Choice

**Date:** 2026-02-05

**Topic:** Which database to use for Phase 1

**Context:** Needed persistent storage for health data

**Options Considered:**

| Option | Pros | Cons |
|--------|------|------|
| **SQLite** | Zero setup, file-based, portable | Single-writer, not ideal for multi-user |
| **PostgreSQL** | Production-ready, concurrent | Requires running server |

**Decision:** SQLite for Phase 1, PostgreSQL for production/multi-user

**Reasoning:**
- SQLite perfect for local development and single-user
- No additional services to run
- Easy to switch to PostgreSQL later (SQLAlchemy abstraction)
- Multi-user deployment would use PostgreSQL

**Status:** Decided - Implemented (SQLite), PostgreSQL planned for Phase 2

---

### DEC-004: UUID vs Integer Primary Keys

**Date:** 2026-02-05

**Topic:** What type to use for database primary keys

**Options Considered:**

| Option | Pros | Cons |
|--------|------|------|
| **Auto-increment integers** | Simple, compact, fast | Leaks count, not portable |
| **UUIDs** | Private, portable, no collisions | Larger, slightly slower |

**Decision:** UUIDs (stored as String(36))

**Reasoning:**
- Privacy: can't infer "you're patient #47"
- Portability: can merge databases without conflicts
- Security: can't enumerate records by guessing IDs
- Health data deserves extra privacy consideration

**Status:** Decided - Implemented

---

### DEC-005: After-Visit PDF Processing & Storage

**Date:** 2026-02-05

**Topic:** How to process after-visit notes (PDFs from patient portals) and extract new medical information to update profiles

**Context:** User receives after-visit summaries as PDFs from healthcare portals. Want to automatically extract new conditions, medication changes, vitals, and lab results, then update the health profile.

**Feature Flow:**
```
Upload PDF → Extract text → LLM parses structured data →
Compare with profile → User confirms → Update profile + archive PDF
```

**PDF Text Extraction Options:**

| Method | Best For | Privacy | Notes |
|--------|----------|---------|-------|
| **pdfplumber** | Text-based PDFs | Local | Fast, reliable |
| **Claude Vision** | Scanned/image PDFs | Sends to Anthropic | Best accuracy |
| **Tesseract OCR** | Scanned PDFs | Local | Free, self-hosted |
| **Local LLM (Ollama)** | Maximum privacy | Local | More setup |

**PDF Storage Options:**

| Option | Privacy | Cost | Scalability |
|--------|---------|------|-------------|
| **Local encrypted folder** | Maximum | Free | Limited |
| **Self-hosted MinIO** | Maximum | Self-managed | Good |
| **Backblaze B2 + encryption** | High | $0.005/GB | Excellent |
| **Encrypted S3** | Medium-High | $0.023/GB | Excellent |
| **Supabase Storage** | Medium | Free tier | Good |

**Recommended Approach:** Client-side encryption before upload
- PDF encrypted locally with user's key
- Only encrypted blob stored in cloud
- Storage provider cannot read contents
- Key never leaves user's control

**New Database Models Required:**
- `Document` - uploaded files with metadata, storage path, extracted text
- `ExtractedItem` - items parsed from documents pending user confirmation

**Privacy Considerations:**
- PDFs contain sensitive medical records → encrypt before storing
- Claude sees content during extraction → option to use local LLM instead
- Extracted text in database → encrypt that column too
- Filenames can leak info → rename to UUID on upload

**Implementation Options:**

| Option | Privacy | Accuracy | Effort |
|--------|---------|----------|--------|
| **A. Self-hosted (MinIO + Ollama)** | Maximum | Good | High |
| **B. Cloud + encryption (B2 + Claude)** | High | Best | Medium |
| **C. Convenience (Supabase + Claude)** | Medium | Best | Low |

**Decision:** DEFERRED

**Reasoning:** Feature planned for Phase 3. Decision on storage/extraction approach will depend on outcome of DEC-001 (multi-user architecture) - if self-hosting, Option A makes sense; if cloud deployment, Option B or C.

**Status:** Deferred - planned for Phase 3

**Dependencies:**
- DEC-001 (deployment architecture) should be decided first
- Affects whether to use cloud storage or self-hosted

---

### DEC-006: PII Anonymization for LLM Calls

**Date:** 2026-02-05

**Topic:** How to protect personally identifiable information when sending health data to LLM APIs

**Context:** Visit prep feature sends patient data to Claude API. Need to prevent PII leakage while maintaining useful medical context.

**Data Classification:**

| Field | Risk | Action |
|-------|------|--------|
| Patient name | High | → "Patient" |
| Date of birth | High | → Exact age (e.g., "39 years old") |
| Emergency contact | Medium | → Remove entirely |
| Doctor name | Medium | → "your [specialty]" or "Doctor" |
| Doctor phone/email | Medium | → Remove entirely |
| Doctor clinic | Low | → Keep |
| Prescribing doctor | Medium | → "Prescribing physician" |
| Conditions/medications | Low | → Keep (medically relevant) |
| Free-text notes | Varies | → Regex + NER scanning |

**Approach:** Hybrid
- Structured fields: Deterministic replacement
- Free-text fields: Regex patterns (phone, email, SSN) + spaCy NER for names
- Medical data: Always preserve

**LLM Provider Strategy:**
- Support both Claude + Anonymization and Ollama (local)
- Configurable via settings
- Same anonymization layer for both

**ConversationLog:** Log anonymized content only (not raw PII)

**Testing Strategy:**
- Unit tests for each anonymization rule
- Integration tests verifying no PII in API calls
- Regression guards to prevent bypass

**Decision:** APPROVED

**Status:** In progress

---

### DEC-007: Action Items Extraction (Phase 3)

**Date:** 2026-02-05

**Topic:** Extracting actionable items (follow-ups, labs, referrals) from visit notes and PDFs

**Context:** After appointments, users have notes like "Follow up in 3 months", "Order blood panel". These should become trackable action items.

**Feature Scope:**
- Parse `visit_notes` field for action items
- Parse uploaded after-visit PDFs for action items
- Extract: follow-up appointments, lab orders, referrals, medication changes
- User confirms before adding to profile

**New Models Required:**
- `ActionItem`: source, action_type, description, due_date, status, linked_record
- `LabTest`: test_name, ordered_date, due_date, completed_date, results

**Sources for Extraction:**
- `appointment.visit_notes` (user-entered)
- Uploaded PDFs (after-visit summaries)

**Decision:** Combined with Phase 3 (PDF Processing + Action Extraction)

**Status:** Deferred - Phase 3

---

### DEC-008: Visit Notes Structure & Intelligent Context Selection

**Date:** 2026-02-05

**Topic:** How to structure appointment notes and intelligently select relevant visit history for prep

**Context:** Users need prep notes (before) and visit notes (during/after). When preparing for a visit, need to include relevant past visit context without wasting tokens on irrelevant visits.

**Part A: Visit Notes Fields**

Model changes:
- Rename `notes` → `prep_notes` (before visit)
- Add `visit_notes` (during/after visit)
- Add `visit_notes_updated_at` timestamp
- Add `exclude_from_prep_context` flag on Doctor model

**Part B: 4-Stage Context Selection**

```
STAGE 1: Rules-Based Filter (instant, free)
├── ✓ Include: Same doctor's last visit
├── ✓ Include: All PCP/Internal Medicine visits
├── ✓ Include: Related specialties (mapping)
└── ✗ Exclude: Doctors with exclude_from_prep flag

        ↓ If > 5 visits remain

STAGE 2: Local LLM Relevance Scoring (Ollama)
├── Score each visit 1-10 for relevance
├── Keep visits scoring >= 7
└── Fallback: Skip if Ollama unavailable

        ↓

STAGE 3: Token Budget Check
├── If over budget: summarize older visits
└── Use local LLM for summarization

        ↓

STAGE 4: Anonymize + Send to Main LLM
```

**Specialty Mapping:**
```
Primary Care / Internal Medicine → Relevant to all
Endocrinology → Cardiology, Nephrology, Ophthalmology, Podiatry, Neurology
Cardiology → Endocrinology, Nephrology, Pulmonology, Vascular Surgery
Oncology → Relevant to all
(extensible)
```

**Configuration:**
- Stage 2 threshold: > 5 visits
- Relevance score cutoff: >= 7
- Fallback if Ollama unavailable: Skip Stage 2, use rules + truncation

**Decision:** APPROVED

**Status:** In progress

---

### DEC-009: Agentic Visit Prep Architecture

**Date:** 2026-02-13

**Topic:** Making the visit prep flow agentic — tool-using + conversational instead of single-shot prompt

**Context:** Current visit prep is a single-shot call: stuff all context into a prompt, get questions back. User wants the agent to be able to reason through steps, use tools (drug interactions, medical guidelines, past visit lookup), and ask the user clarifying questions interactively before generating the final prep.

**Scope:** Both tool-using and conversational agentic behavior.

**Framework Options Considered:**

| Option | Pros | Cons |
|--------|------|------|
| **Claude API tool use (native)** | Already wired up, no new deps, simple loop | Manual orchestration |
| **Anthropic Agent SDK** | Structured primitives, built for Claude | New dependency, learning curve |
| **LangGraph** | Explicit state machine, good for complex flows | Heavy abstraction, overkill for single agent |

**Decision:** Claude API native tool use

**Reasoning:**
- Claude API is already integrated in the project
- No new dependencies to install or learn
- Simple pattern: send message + tools → Claude calls tools or asks user → loop until done
- Easy to upgrade to a framework later if needed (tools are reusable)
- Single agent workflow doesn't warrant framework overhead

**Local vs Cloud LLM Options Considered:**

| Option | Feasibility | Quality | Cost |
|--------|-------------|---------|------|
| **Local Ollama (7-8B models)** | Tight on 8GB RAM M3 (4-5GB available after OS). Only 4-bit quantized models fit. | Tool use / function calling unreliable on small models — malformed JSON, wrong tool calls, loops | Free |
| **Claude API (Sonnet)** | No constraints | Reliable tool use out of the box | ~$0.03-0.10 per visit prep (~$1/month for typical use) |

**Decision:** Claude API (Sonnet) for the agentic loop

**Reasoning:**
- 8GB RAM M3 is too constrained for reliable agentic tool use with local models
- Small local models (7-8B) produce unreliable function calling — the critical capability for agentic workflows
- Claude API cost is negligible for personal use (~$1/month)
- Ollama remains available for simpler tasks (context selection summarization per DEC-008)

**Status:** Implemented (bounded scope, see DEC-013) — 2026-07-06

---

### DEC-010: AVS PDF Parser Integration

**Date:** 2026-02-14

**Topic:** Integrating the sandbox AVS PDF parser (SB-001) into HealthSteward as a full feature

**Context:** The avs-pdf-parser sandbox project proved that after-visit summary PDFs can be parsed into structured medical data using a section-routing architecture (deterministic parsers + local Ollama LLM for unstructured sections). This integration brings that capability into the main app with: new database models, upload/parse/review API, and frontend UI.

**Architecture:**

| Component | Approach |
|-----------|----------|
| Parser module | `src/parsers/` package — `SectionRouter` with deterministic + LLM pipeline |
| LLM calls | Local Ollama only (privacy: no PHI leaves machine) |
| New models | Document, Vitals, LabOrder, Referral, FollowUp |
| Existing model changes | Condition gains `icd_10` field |
| File storage | `data/avs/` scan directory — PDFs read in place, no duplication (git-ignored) |
| User flow | Drop PDF in `data/avs/` → Open Documents tab → Parse locally → Review → Confirm → Update profile |

**Key Design Decisions:**
- **Local-only parsing**: All LLM calls go through localhost Ollama, never external APIs. Safety check in `ollama_chat.py` blocks non-localhost URLs.
- **Section routing**: Deterministic parsers handle patient info, medication changes, follow-ups, appointments, and diagnoses (when ICD codes present). LLM handles vitals, lab orders, notes, referrals, and diagnoses (when no structured Assessment section).
- **Review before apply**: Parsed items are presented for user review with checkboxes per section. Nothing is auto-applied — user confirms each category.
- **Deduplication**: Diagnoses are deduplicated by name when applied (existing conditions get ICD-10 updated if missing). Medication stops match by name.

**Decision:** APPROVED and implemented

**Status:** Complete

---

## Template for New Decisions

```markdown
### DEC-XXX: Title

**Date:** YYYY-MM-DD

**Topic:** One-line description

**Context:** Why this decision is needed

**Options Considered:**

| Option | Pros | Cons |
|--------|------|------|
| **Option 1** | ... | ... |
| **Option 2** | ... | ... |

**Decision:** What was chosen

**Reasoning:** Why this option was selected

**Status:** Decided / Deferred / Revisit
```

### DEC-011: Specialty-Aware Visit Prep Context

**Date:** 2026-02-15

**Topic:** Making visit prep questions relevant to the appointment's specialty

**Context:** Visit prep was generating irrelevant questions — e.g., suggesting a patient discuss dermatology medications (topical creams) with their cardiologist. At the same time, it was missing useful cross-specialty context like how related conditions across specialties interact. Lab results and vitals trends were also absent from the context.

**Decision:** Enrich the visit prep context and make the system prompt specialty-aware:

1. **Specialty-focused system prompt** — template with `{specialty}` that explicitly tells the LLM to only generate questions relevant to this specialist, not unrelated ones
2. **ICD-10 → specialty mapping** — tag each condition with which specialties typically manage it (e.g., E11→Endocrinology, I10→Cardiology, L40→Dermatology)
3. **Medication specialty tags** — match prescribing_doctor to Doctor records to tag meds with the prescribing specialty (e.g., `[prescribed for Dermatology]`)
4. **Clinical data enrichment** — include lab orders, vitals trends, pending follow-ups, and active referrals in the LLM context
5. **Clinic-name specialty inference** — fallback when `doctor.specialty` is null but clinic name contains the specialty (e.g., "Valley Cardiology Associates" → Cardiology)
6. **Expanded specialty mapping** — added Gynecology ↔ Endocrinology cross-relevance

**Reasoning:** The LLM needs explicit guidance about what's relevant to the specific specialty being visited. Without it, it treats all conditions and medications equally. The ICD-10 and medication tags give the LLM the context to make relevance judgments itself, while the system prompt sets the filtering rules.

**Status:** Decided

---

---

### DEC-012: Patient Disengagement — Proactive Action Item Surfacing

**Date:** 2026-07-05

**Topic:** Addressing patient disengagement through timely nudges from parsed AVS data

**Context:** HealthSteward assumes an engaged patient. Once data is in the system, pending follow-ups, lab orders, and referrals are stored in the database but never surfaced proactively — they only appear if the patient navigates to them. The system needed to close the loop between "document parsed" and "patient acts on what the doctor ordered."

**Options Considered:**

| Option | Pros | Cons |
|--------|------|------|
| **A. Post-AVS action panel (simple)** | Shown at moment of engagement, no new infra | Requires patient to be in the app |
| **B. Persistent overview section (simple)** | Always visible, cross-visit accumulation | Passive — still requires patient to notice |
| **C. Scheduled push notifications (medium)** | Genuinely proactive, reaches disengaged patient | Requires scheduler, conflicts with local-first arch |
| **D. Snooze/action-completed nudge loop (medium)** | Best UX, persistent until resolved | New state model + migrations needed |

**Decision:** Implement A and B first as the foundation. C and D deferred.

- **Post-AVS action panel** — after the patient confirms parsed items, show a summary of what needs action: follow-ups to book (nudging immediately if timeframe ≤ 6 months), lab orders to get done (with reminder if an upcoming appointment exists), referrals to schedule. This surfaces nudges at the highest-engagement moment.
- **Overview tab action items** — a persistent "Needs Attention" section showing pending follow-ups, lab orders, and referrals across all documents parsed for the profile.
- **Backend API** — new endpoints for listing and updating status of follow-ups, lab orders, and referrals (previously stored but never queryable).

**Reasoning:** The post-AVS panel is the highest-leverage nudge because it fires when the patient is already engaged. The overview section catches items that accumulated from past visits. Both are pure additions on top of existing data — no new schema, no scheduler. The snooze/action-completed loop and scheduled notifications are the right long-term direction but require new infrastructure; deferred to a follow-up iteration.

**Status:** Decided (simple phase complete; medium phase — snooze/completion, i.e. option D — implemented 2026-07-05; UX polish — implemented 2026-07-05; option C — scheduled push notifications — tracked in GitHub issue #25, DEC-015)

**Medium Phase (2026-07-05):** Implemented snooze and completion state:

- **`snoozed_until` + `completed_at`** added to `FollowUp`, `LabOrder`, `Referral` — with Alembic migration
- **`NudgeState` table** — persists snooze state for computed nudges (upcoming-without-prep, past-due appointments, completed-without-avs, vitals alerts) that have no row to attach state to
- **Backend filtering** — list endpoints now exclude completed and actively-snoozed items by default; PATCH endpoints auto-stamp `completed_at` on status transition
- **Frontend** — all action items now have a "Snooze 1w" secondary button alongside the existing primary action button; `ActionItemsSection` queries no longer pass explicit status filters (the backend handles it)

**UX Polish Phase (2026-07-05):** Addressed three minor UX gaps:

- **Resolved history** — "Show/Hide resolved" toggle in the Needs Attention card header; backend `?include_resolved=true` param returns completed items (capped at 20, ordered by `completed_at` desc); resolved items rendered muted with strikethrough and completion date; queries lazy-load only when toggle is on
- **Previously snoozed indicator** — any active item with a non-null `snoozed_until` was previously snoozed (backend filters actively-snoozed items, so the field's presence on an active item means the snooze expired); shown as a small clock icon + "snoozed" badge inline with the item name; no backend changes required
- **Flexible snooze** — single "Snooze 1w" button replaced with a [1w][2w][1m] pill group everywhere snooze appears (`ActionItemsSection` and `PostAvsActionPanel`); covers longer-horizon items like referrals without requiring a date picker

---

### DEC-013: Pluggable LLM Backend + Agentic Tool-Use Implementation

**Date:** 2026-07-06

**Topic:** Implementing DEC-009's agentic tool-use loop, designed from the start to work behind a pluggable backend for both Claude API and local Ollama

**Context:** GitHub issue #11 asked for a pluggable LLM backend so visit prep could run fully local as well as on Claude. Investigation found DEC-009 (agentic visit prep) had been approved but never implemented — `prepare_visit()` was still single-shot prompt-in/JSON-out, with no tool-calling anywhere in the codebase. A basic provider toggle (`settings.llm_provider`) already existed but only switched which LLM generated that single-shot response.

**Decision:** Build both together — the actual agentic tool-use loop, behind a new `LLMBackend` abstraction (`src/agents/llm_backend.py`) implemented for both `ClaudeBackend` and `OllamaBackend`.

**Scope (deliberately bounded for v1):**
- Two read-only tools (`src/agents/tools.py`): `get_medication_details` (on-demand structured medication lookup — not a real drug-interaction database/API, which would be a separate, bigger feature) and `lookup_past_visits` (on-demand deeper visit history query)
- **Descoped:** a real drug-interaction checker (needs a licensed external API) and a user-facing pause-to-ask-clarifying-questions flow (needs new DB state, a new API endpoint, and new frontend UI) — tracked in GitHub issues #24 (drug-interaction checker, DEC-015) and #15 (clarifying-question conversation)
- **Fallback, not hard failure:** if the loop can't converge within `agent_max_turns` (default 6) or a backend raises `ToolCallParsingError` (malformed/missing tool-call data — expected on small quantized local models per DEC-009), `prepare_visit()` falls back to the existing non-agentic single-shot call. No regression risk.
- **Anonymization:** tool results are anonymized before being fed back into the loop for both backends, consistent with how `prepare_visit()` already anonymizes the main context regardless of provider
- No DB schema changes, no API response shape changes, no frontend changes — `prepare_visit()`'s return shape is unchanged

**Status:** Implemented

---

### DEC-014: Packaging Strategy for Non-Terminal Users

**Date:** 2026-07-08

**Topic:** How to let someone go from the new marketing landing page to a running app without opening a terminal

**Context:** The landing page (built to broaden reach beyond the GitHub repo) pitches HealthSteward to people outside the current audience, but setup still requires a terminal — cloning the repo, running pip/pnpm/alembic commands, and installing and running Ollama separately. That's a real barrier for non-technical users the landing page is meant to attract.

**Options Considered:**

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| **1. One-line install script** | `curl \| sh` checks/installs Docker, pulls the image, runs it, opens the browser | Low effort, fast to ship | Still technically "terminal," just one command instead of many |
| **2. Native desktop app** | Tauri/Electron wrapper + PyInstaller-bundled backend, packaged as .dmg/.exe/.AppImage | Real double-click installer, closest to "non-technical user" experience | Ollama's multi-GB model download has to be bundled or fetched on first run; cross-platform code signing/notarization ($99/yr Apple, Windows signing) and auto-updates make this a multi-week undertaking with ongoing packaging maintenance |
| **3. Thin native launcher over Docker Desktop** | Small native app that checks Docker is running, runs `docker-compose up`, opens the browser | Hides most complexity without bundling Python/Ollama | Still requires Docker Desktop installed once; not truly terminal-free |

**Decision:** Start with Option 1 (one-line install script). Options 2 and 3 deferred until there's signal that people want this enough to justify the ongoing packaging maintenance burden.

**Reasoning:** A native installer (Option 2) is the best end-state for the stated goal of reaching people unfamiliar with terminals, but Ollama's model-download size and the cross-platform signing/notarization/update pipeline make it a significant, ongoing commitment for a pre-product-market-fit project. The install script is a cheap, reversible step that meaningfully lowers the barrier today; it can be superseded by a native installer later without having wasted the work.

**Scope note:** This also requires `docker-compose.yml` to actually work end-to-end — it currently provisions Postgres/Redis/ChromaDB, but the app defaults to SQLite, and there's no Ollama service in compose. That needs fixing regardless of which installer approach is picked, and blocks Option 1 as much as Options 2/3.

**Status:** Decided (simple phase — install script — not yet started; tracked in GitHub issue "Packaging: one-step installer for non-terminal users")

---

### DEC-015: Visit Prep Tool Scope — What Data Would Actually Be Useful to Prep With

**Date:** 2026-07-08

**Topic:** Revisiting the visit-prep agentic loop's tool scope (DEC-009/DEC-013) by asking what context is actually useful for prepping a visit, regardless of whether a human or an agent is doing the prepping

**Context:** DEC-013 shipped the agentic loop with two deliberately narrow, read-only tools (`get_medication_details`, `lookup_past_visits`) chosen because they could be built from data already in the schema, not because they were the right end state. Revisiting from first principles: what's actually useful to prep for a visit is current medications, test results since relevant to the upcoming provider, visit notes from other providers since the last visit with this one, and any surgeries/hospital admissions/procedures since then. Checking each against `src/data/models.py` surfaced that the tool layer and the data layer have different gaps.

**Findings per item:**

| Need | Status | Gap |
|------|--------|-----|
| Current medications | Supported today | `get_medication_details` already returns all current meds when `medication_name` is omitted — no change needed |
| Visit notes from other providers since last visit with target provider | Data exists, tool doesn't | `Appointment.visit_notes` + `Doctor` relationship exist; `lookup_past_visits` filters by specialty/keyword but has no date window — needs a query change, not new data |
| Test results | Data doesn't exist | `LabOrder` only records that a test was *ordered* (`test_name`, `ordered_date`, `status`) — there is no result value, reference range, or result date field anywhere in the schema. The AVS parser doesn't extract results either. |
| Surgeries / hospital admissions / procedures | Data doesn't exist | No model at all — not `Condition`, not `Document`. The AVS parser's section-routing architecture (DEC-010) has no branch for this. |

**Decision:** Split into three independent follow-ups rather than one combined rework, tracked as GitHub issues (see below):

1. **Widen `lookup_past_visits`'s default window** to "since the patient's last completed visit with the target provider, across all providers" when no explicit `specialty`/`keyword` filter is given, while keeping the existing filters composable on top. Small, tool-layer-only change.
2. **Add lab results to the schema and AVS parser** (`LabOrder.result_value`/`result_date`/`reference_range` or similar), windowed to whichever is shorter: since the last visit with the target provider, or the last 6 months — avoids surfacing stale results when visits are far apart. Needs schema + parser work, not just a tool wrapper.
3. **Add a procedures/hospitalizations model and parser branch**, then a corresponding tool. New table, new AVS section-router branch, biggest lift of the three.

**Reasoning:** Consistent with DEC-013's bounded-scope pattern — ship what's cheap now, treat schema/parser changes as their own scoped projects rather than inflating one PR. Splitting also reflects that these three have genuinely different costs (query change vs. schema+parser vs. new model+parser+tool), so bundling them would obscure that in planning and review.

**Status:** Decided — tracked in GitHub issues (visit-notes default window, lab results schema+parser, procedures/hospitalizations schema+parser)

---

### DEC-016: Default LLM Provider Flipped to Ollama; Add Custom OpenAI-Compatible Provider; Runtime-Editable Settings

**Date:** 2026-07-09

**Topic:** Which LLM backend visit prep uses by default, whether users can connect any LLM they want (not just Claude/Ollama), and whether switching providers requires editing `.env` and restarting.

**Context:** DEC-009 chose Claude API as the *default* agentic backend, reasoned specifically from the dev machine's constraints (8GB RAM M3 can only run 4-bit quantized 7-8B Ollama models, which produce unreliable tool-calling). That reasoning is about the dev machine, not about what should ship as the default for end users generally — and it sits awkwardly next to the project's own privacy-first pitch (landing page, TDD): "stays on device" was the *opt-in* behavior, not the default, for the flow (visit prep) most likely to be used regularly. Separately, the `LLMBackend` abstraction built in DEC-013 only supported exactly two providers, and there was no way to change the provider without editing `.env` and restarting the server — no settings UI or API existed at all.

**Options Considered:**

| Option | Pros | Cons |
|--------|------|------|
| Keep Claude as default, add a "custom" provider only | Smaller change; no default-provider risk | Default stays out of step with the local-first pitch; the flow most people use daily still defaults off-device |
| Flip default to Ollama, add a "custom" provider | Privacy-first positioning holds by default; DEC-013's fallback already covers the reliability gap | More installs hit small-model tool-calling unreliability by default (mitigated by the existing fallback, not eliminated) |
| Bespoke adapter per third-party provider (OpenAI, OpenRouter, Groq, etc.) individually | Could special-case quirks per provider | Unbounded maintenance surface for "any LLM you want"; almost all of these already speak the same OpenAI-compatible wire format, so per-provider adapters would mostly duplicate each other |
| One generic OpenAI-compatible adapter (`CustomOpenAICompatibleBackend`) | One adapter covers the large majority of hosted and self-hosted options; consistent with DEC-013's bounded-scope precedent | Providers with a genuinely different wire format (e.g. a native Gemini/Vertex adapter) would still need their own class later |
| Keep settings `.env`-only, just document the new default/provider | No new DB table, API routes, or frontend page | Switching still requires editing `.env` and restarting — not "easy" per the explicit ask, and a real barrier for non-terminal users (DEC-014) |
| DB-backed runtime settings (`AppSettings` singleton row, overlaid on env defaults) | Switching takes effect on the next request, no restart; UI-editable | A second source of truth (DB overlay vs. env) that needs care to keep legible |

**Decision:**
1. Flip `llm_provider`'s default from `"claude"` to `"ollama"` (`src/config.py`). Claude remains fully supported, now as an explicit opt-in rather than the default.
2. Add a third provider, `"custom"` — `CustomOpenAICompatibleBackend` (`src/agents/llm_backend.py`), for any endpoint speaking OpenAI's `/chat/completions` + tool-calling wire format (OpenAI itself, OpenRouter, Groq, Together, a self-hosted vLLM/LM Studio server, etc.). Ollama's `/api/chat` already mirrors this format, so the tool-spec adapter (`ollama_tools()`) and dispatch pattern needed no new shape, just a new branch.
3. Consolidated the LLM-provider dispatch in `src/agents/visit_prep.py`, which previously checked `settings.llm_provider == "ollama"` via string equality in three separate places (agentic-loop tool selection, single-shot fallback, model-name-for-logging). All three now go through `get_llm_backend()` / `get_tools_for_provider()`, so adding the third provider required one new backend class instead of a fourth branch in three places.
4. Made provider choice a **runtime, DB-backed setting** rather than `.env`-only: new singleton `AppSettings` table (`src/data/models.py`), `src/services/settings_service.py` (`get_effective_settings()` overlays non-null DB values onto the env-based `Settings`), and `GET`/`PUT /api/settings` (`src/api/settings.py`, secrets masked on read). A new frontend Settings page (`frontend/src/pages/Settings.tsx`) lets a user switch providers and re-run visit prep without restarting the backend.

**Reasoning:**
- DEC-009's tool-reliability finding (small quantized local models are unreliable at function-calling) is still true and unchanged — it's exactly why DEC-013's fallback-to-single-shot behavior exists and now matters more, since more installs will hit it by default. This decision supersedes DEC-009's *default provider choice*, not its technical finding.
- End-user hardware varies; defaulting to the option that's honest about the privacy trade-off (fully local, at the cost of potentially flakier tool use with the fallback covering that gap) is more consistent with the project's stated positioning than defaulting to the option that's more reliable on one specific underpowered dev machine.
- "Any LLM the user wants" was interpreted as "any OpenAI-compatible endpoint" rather than building bespoke adapters per provider — this covers the overwhelming majority of hosted and self-hosted options with one adapter, consistent with DEC-013's bounded-scope precedent.
- Settings needed to be runtime-editable (not `.env`-only) for switching to actually be "easy," per the user's explicit ask — a `.env` edit + restart is a real barrier for anyone not comfortable with a terminal, which cuts against the same non-terminal-user consideration raised in DEC-014.

**Status:** Implemented

---

### DEC-017: Unified Brand Palette Across App, Docs, Favicon, and Marketing Assets

**Date:** 2026-07-16

**Context:** The app (frontend) and the docs/marketing surface (`docs/index.html`, `docs/tdd.html`, favicon, GitHub social preview card) had grown two independent, disconnected color systems. The app used Tailwind defaults reached for during fast development — `emerald-600/700` as a loose primary accent, plus `blue`/`green`/`purple` scattered across different UI states, on a `gray-50`/`white` background. The docs site used a deliberately designed, WCAG-checked custom palette (`docs/SITE_STYLE_GUIDE.md`) — teal (`#20464c`/`#2f626a`) semantically meaning "runs locally," amber (`#8a5a17`) meaning "crosses the anonymization/external trust boundary," on a warm cream (`#efeee6`) background. Preparing a GitHub social preview card and a LinkedIn brand asset surfaced the inconsistency (teal logo mark vs. emerald app UI) directly.

**Options Considered:**

| Option | Pros | Cons |
|--------|------|------|
| Standardize on the app's emerald | Matches the literal running product UI | Emerald was never a deliberate brand choice — just Tailwind defaults; also the single most common "clinical app" color family alongside blue, offering no differentiation |
| Standardize on the docs' existing teal/amber system | Already deliberately designed, WCAG-AA checked, semantically mapped to the actual privacy architecture (local vs. crosses-boundary); already shipped in favicon, social card, LinkedIn description | Requires updating the app's Tailwind usage across many components |
| Keep both systems, just align background color | Smaller change | Doesn't resolve the actual "teal vs. emerald" brand inconsistency that prompted this |
| Full uniformity: one palette everywhere (app, docs, favicon, marketing) | Genuinely one brand, no more asking "which color is HealthSteward" | Largest surface area to change; requires care not to collapse *unrelated* semantic UI colors (e.g. appointment-status blue, document-category purple) into the brand accent, which would reduce UI clarity rather than improve brand consistency |

**Decision:**
1. The docs site's existing teal/amber system becomes the single canonical brand palette everywhere — not the app's incidental emerald.
2. Background moves from the docs' warm cream (`#efeee6`) to a near-white (`#fafaf9`), and from the app's cool-toned `gray-50` to the same `#fafaf9` — chosen over pure white to avoid the sterile/cold feel of stark white while staying clearly distinct from the old cream. `--paper-raised` moves from `#f7f6ef` to `#ffffff` to preserve "raised = lighter than base" now that base itself is near-white.
3. App: added a Tailwind v4 `@theme` block (`frontend/src/index.css`) defining `brand-teal`, `brand-teal-bright`, `brand-amber`, `brand-paper`, `brand-ink` as the exact docs hex values. Bulk-replaced every `emerald-*` class (the app's actual primary/interactive accent — buttons, focus rings, active nav state) with the matching brand-teal token. Replaced the top-level page background (`Layout.tsx`, `bg-gray-50`) with `bg-brand-paper`.
4. One additional *semantic* fix beyond the mechanical rebrand: the "Parsing document with local LLM" indicator (`ProfileDetail.tsx`) was using Tailwind `blue`, despite directly representing the exact concept the brand system already assigns to teal ("runs locally"). Changed to `brand-teal`/`brand-teal-bright` for real semantic consistency, not just cosmetic matching.
5. Deliberately left other `blue`/`purple` usages untouched — appointment status ("scheduled"), document-category tags, ICD-10 code chips. These represent distinct categorical meanings unrelated to brand identity; collapsing them into the brand accent would reduce UI clarity, not improve brand consistency. Similarly left component-level `gray-50` tints untouched (disabled inputs, nested sub-panels) — these need to read as different from the page background for visual hierarchy and aren't a brand concern.
6. Verified via computed WCAG contrast (not eyeballed, per the style guide's own rule) that the lighter background only improves contrast for every existing text/accent token — no regressions.
7. Updated `docs/SITE_STYLE_GUIDE.md`'s documented palette values and rationale, README's badge colors and status text, and the GitHub social preview card to match.
8. **Same-day hue correction:** a visual smoke test of the running app surfaced that the originally-chosen teal (`#1f4a42`/`#2f6a5e`, hue ≈168°) read as dark forest green rather than teal — confirmed computationally (HSL hue math, not just eyeballed), since `G > B` in both values pushed them notably toward green. Shifted hue to 188° (`#20464c`/`#2f626a`) — clearly blue-leaning — while holding saturation/lightness constant, which actually *improved* contrast against the new background (9.85 and 6.54 vs. 9.50 and 6.01). Applied everywhere the original values had just been rolled out (app theme tokens, docs site, favicon, style guide, social card) before this PR merged.

**Reasoning:**
- The docs palette was the only one of the two that was ever a deliberate design decision — promoting it to canonical is strictly less work and strictly higher quality than reverse-engineering a system out of the app's incidental Tailwind defaults.
- Full uniformity was the explicit goal (not a partial/background-only fix), but "uniform brand" means the same *brand* accent and background everywhere — it does not mean collapsing every incidental UI color into two tokens regardless of what that color currently communicates. Status/category colors that aren't about brand identity were left alone on purpose.
- Also updated the `status` badge text from "early development" to "active development" across README and the social card — "early" undersold a project whose core agentic architecture (DEC-009/DEC-013/DEC-016) is implemented and running; "active" is accurate without overclaiming stability the eval harness and installer (issue #18) don't yet have.

**Status:** Implemented

---

### DEC-018: Evaluation Harness v1 — Deterministic-Only, Plus Project-Wide Prompt Versioning

**Date:** 2026-07-19

**Context:** Issue #29 (no quality evaluation of visit-prep output) had been open since early in the project — the backend test suite verifies plumbing (loop convergence, tool execution, anonymization boundaries), not whether generated questions are actually good. `docs/tdd.html`'s Evaluation Plan tab (entry 26 in `DEVELOPMENT_LOG.md`) had already laid out a full plan splitting visit prep into two eval surfaces — retrieval (`ContextSelector`, Stages 1-2) and generation (`VisitPrepAgent.prepare_visit`) — with a tiered, judge-dependency-ranked build order. This DEC covers actually building the first tier.

**Options Considered:**

| Option | Pros | Cons |
|--------|------|------|
| Build the full plan (deterministic + LLM-as-judge) in one pass | Complete coverage immediately | Judge reliability is its own unsolved problem (self-grading bias, judge variance); blocks shipping anything on that being solved first |
| Deterministic-only v1, judge tier explicitly deferred | Ships a real regression signal now with zero new trust dependencies; judge-reliability work can happen independently later | Doesn't measure the properties that most need a judge (relevance, non-redundancy) |
| Skip a harness, rely on manual spot-checking | No build cost | Exactly the gap issue #29 was filed to close — no repeatable "did this prompt change help or hurt" signal |

**Decision:**
1. **Deterministic-only v1**, matching `docs/tdd.html`'s own tier-1/tier-2 items: format validity, a specialty-scope checker (reusing `med_specialty_map`/ICD-10 tags already computed in code), a cheap groundedness entity-match pass, and Stage 1 retrieval rule assertions (no LLM involved). Explicitly labeled a smoke test, not a quality measure, in both `eval/__init__.py` and its own README-equivalent — catches gross regressions (hallucination, scope violations, malformed output), says nothing about whether output is actually *good*. LLM-as-judge (relevance/usefulness, non-redundancy, deeper groundedness) stays a named v2 backlog item.
2. **Two additional checks beyond the original plan**, added after tracing the pipeline in detail while scoping this: a **tool-call necessity** check (did the agentic loop's Phase 2 on-demand retrieval call the tool a case was designed to make useful) and a **Phase 1/Phase 2 retrieval redundancy** check (did a `lookup_past_visits` tool call re-surface a visit `ContextSelector` already selected) — both observational in v1, not hard pass/fail, since neither is a deterministic requirement of good behavior, just a signal worth tracking. Matched on `scheduled_date` since `AnonymizedAppointment` carries no original id to correlate the two retrieval phases by anything sturdier.
3. **Fixed sampling temperature (0.0) for all eval calls**, threaded as a new `temperature` parameter through `LLMBackend.call()` → `VisitPrepAgent.prepare_visit()` — production's default (0.7) is untouched; eval-only override. Without this, a single eval run's pass/fail is meaningless noise.
4. **Diagnostics exposed on `VisitPrepAgent`** (`self.last_context_selection`, `self.last_tool_calls`) after `prepare_visit()` returns, rather than changing its return contract — lets the harness inspect Phase 1/Phase 2 retrieval without duplicating pipeline logic or breaking the existing API route's expectations.
5. **Results are diffed against the prior run**, not just checked against a fixed pass/fail floor — `eval/run.py` writes a timestamped JSON report (gitignored, not checked in) and prints a diff summary against the most recent prior result, since "better or worse than last time" is the actual question a prompt-change review needs answered.
6. **Project-wide prompt versioning, started alongside this** (not originally scoped, added when the first real eval run immediately motivated a prompt change and there was nowhere to record why): every prompt in the codebase — `visit_prep.py`'s two system prompts, `context_selection.py`'s Stage 2 scoring prompt, `parsers/agent/prompts.py`'s five AVS extraction prompts — gets a version tag, with content changes logged in the new `docs/notes/PROMPT_CHANGELOG.md`. `visit_prep.py`'s prompts additionally log their version into `ConversationLog.extra_data["prompt_version"]` on every real run; the other two locations don't have a per-run log to thread into yet (noted as an open gap in the changelog, not silently skipped).

**Found while building this** (not part of the decision, but material context for why v1 shipped with real teeth): running the harness against a real local Ollama server — not just mocks — surfaced three previously-hidden production bugs, all fixed on the same branch: (a) the Ollama/custom backend never sent `stream: false`, so `response.json()` broke on any real multi-chunk response, likely silently degrading most/all Ollama-backed calls straight to the generic fallback; (b) `temperature` was sent top-level for `OllamaBackend`, which Ollama's native `/api/chat` ignores (needs nesting under `options`); (c) the backend's HTTP timeout only bounded gaps between chunks, not total request duration, so a slow/trickling response could hang indefinitely with no error — fixed with an `asyncio.wait_for` wall-clock ceiling. A fourth non-production bug (an undisposed `AsyncEngine` in `eval/run.py` itself) caused the harness process to hang ~17 minutes in asyncio shutdown after already finishing its work — fixed by disposing the engine explicitly.

**Reasoning:** A harness that only ever runs against mocks would have shipped without finding any of the three real production bugs above — validates deliberately including at least one real-backend run as part of standing up v1, not just unit-testing the scorers in isolation. Deterministic-first was the right sequencing call per `docs/tdd.html`'s own build order: it shipped a working regression signal immediately and — concretely, not hypothetically — that signal caught a real prompt-count regression on its very first run, which then got fixed and re-validated through the same harness within the same session.

**Status:** Implemented (v1). LLM-as-judge tier, and closing the two prompt-version-without-a-log gaps noted above, remain open follow-ups.

---

### DEC-019: Explicit Ollama `num_ctx`, Sized as an Env-Only Setting

**Date:** 2026-07-20

**Context:** Issue #71, filed while scoping the #29 eval harness (DEC-018): `_OpenAIStyleHTTPBackend.call` never set `num_ctx` in the request payload sent to Ollama's `/api/chat`. Without it, Ollama silently falls back to its own runtime default for whatever model is configured — commonly 2048 tokens for a freshly-pulled model unless its Modelfile overrides it — completely independent of this app's own `context_max_tokens` budget (default 2000), which itself only bounds past-visit history text before the system prompt, patient data, and any agentic tool-call round trips are added on top. This predates any of the agentic loop's growth: the single-shot fallback path could already be silently truncating context on local models today, with no error surfaced.

**Options Considered:**

| Option | Pros | Cons |
|--------|------|------|
| Hardcode a fixed `num_ctx` in the request | Simplest possible fix | No way to tune per-model without a code change |
| New `Settings.ollama_num_ctx` field, explicit default, env-overridable | Coordinates with existing `context_max_tokens`/`agent_max_turns` budget; fixable without a code change per deployment; matches the pattern of every other Ollama tunable in `config.py` | Doesn't (yet) expose runtime editing via Settings.tsx the way `ollama_model`/`ollama_base_url` do |
| Compute `num_ctx` dynamically from `context_max_tokens` + `agent_max_turns` at call time | Self-coordinating, no separate value to drift out of sync | Needs real measurement of system-prompt + per-turn tool-call overhead first (issue #56 territory) to size correctly — guessing a formula now risks a false sense of precision |

**Decision:**
1. Added `Settings.ollama_num_ctx: int = 8192` (`src/config.py`), and passed it through `OllamaBackend._sampling_payload`'s `options` dict (`src/agents/llm_backend.py`). The default is derived from a documented formula rather than an arbitrary round number: `context_max_tokens` (2000, visit-history text) + an estimated ~1500 tokens of system prompt/patient-data overhead + ~500 tokens/turn × `agent_max_turns` (6) ≈ 6500, rounded up to the next power-of-two Ollama context size.
2. Since the 1500/500-token overhead figures are estimates, not measured, added a best-effort safety net rather than waiting on real profiling: `OllamaBackend._context_budget_warning` estimates a request's token count (chars/4 heuristic over the serialized messages + tools) and logs a warning via loguru if it crosses 75% of `ollama_num_ctx`, naming the estimate and suggesting the two knobs (`ollama_num_ctx`, `context_max_tokens`/`agent_max_turns`) to adjust. This is deliberately a visibility mechanism, not a hard gate — an approximate heuristic shouldn't block an otherwise-working request on a false positive — but it directly satisfies the issue's "fails loudly" expected behavior rather than leaving it as a follow-up.
3. Scoped `ollama_num_ctx` as env-only for now, not added to `settings_service.py`'s runtime-editable allowlist or the Settings API/UI — matching `ollama_model`'s prior gap (issue #59) rather than compounding it silently; making it runtime-editable is a natural companion to #59 if picked up together, not bundled into this fix.

**Reasoning:** A formula-grounded default plus a runtime overflow warning closes both halves of the issue's expected behavior — an explicit, reasoned `num_ctx`, and loud failure when a request is actually likely to exceed it — without requiring a separate profiling project to trust the number. `num_ctx` is Ollama-specific (not a standard OpenAI-compatible field), so the fix is scoped to `OllamaBackend` only, not the shared `_OpenAIStyleHTTPBackend` base class `CustomOpenAICompatibleBackend` also uses.

**Status:** Implemented. Replacing the chars/4 heuristic with real per-model tokenizer counts (if warning false-positive/negative rates in practice warrant it), and exposing `ollama_num_ctx` as runtime-editable alongside #59, remain open follow-ups.

---

### DEC-020: Surface LLM Backend Failure to the User via a Persisted `used_fallback` Flag

**Date:** 2026-07-20

**Context:** Issue #47: when the configured LLM backend fails entirely (unreachable/misconfigured URL, or any other failure that survives both the agentic loop and its single-shot fallback), `VisitPrepAgent._get_fallback_response()` returns hardcoded generic placeholder questions — but `prepare_visit` never raises past that point, so the frontend receives what looks like a normal 200 response. `VisitPrep.tsx`'s existing error banner never fires, because nothing actually errored from its perspective. The fallback mechanism itself is working as designed (DEC-009/DEC-013's convergence handling) — it just had no visibility.

**Options Considered:**

| Option | Pros | Cons |
|--------|------|------|
| Ephemeral flag only in the POST response (not persisted) | No migration needed | Reloading the Visit Prep page (GET) loses the warning — user could reasonably think a stale generic result is a fresh, personalized one |
| Persist `used_fallback` on `VisitPrep`, surfaced on both POST and GET | Warning survives a page reload/reopen until the user successfully regenerates; consistent state regardless of which route served the data | Needs an Alembic migration |
| Infer fallback status client-side by pattern-matching `context_summary`/`generated_questions` content | No backend/schema change at all | Fragile — string-matching hardcoded copy is exactly the kind of implicit contract a rename or copy edit silently breaks |

**Decision:** Added `VisitPrep.used_fallback: bool` (`src/data/models.py`, migration `73a1532778f1`, default `False`), threaded through `VisitPrepAgent.prepare_visit`'s return dict (`True` only from `_get_fallback_response()`'s outer-exception path; `False` for every other return, including the agentic-loop-doesn't-converge single-shot fallback (DEC-009/013), which is a real LLM-generated result and not a failure), persisted on both create and update in `src/api/visits.py`, and exposed via `VisitPrepResponse`. `VisitPrep.tsx` shows an amber warning banner (matching `ParsedItemsReview.tsx`'s existing edit-count banner styling) linking to Settings when `used_fallback` is true.

**Reasoning:** A persisted, explicit boolean is the only option of the three that's both durable (survives reload) and robust (doesn't depend on copy text staying in sync with a string-match check). The distinction between "single-shot fallback" (DEC-013, still real model output) and "used_fallback" (issue #47, no model output at all) is deliberate — conflating them would make every graceful DEC-009/013 convergence failure look like a backend outage to the user, when only the latter actually is one.

**Status:** Implemented.

---

### DEC-021: Ollama Auto-Discovery — Explicit "Detect" Button, Not Automatic on Page Load

**Date:** 2026-07-21

**Context:** Issue #48: the Settings page's Ollama Base URL field is a plain text input with no help finding the right value — in practice it's almost always `localhost:11434` for this app's target use case (single local machine, per DEC-009), so most users shouldn't need to type anything. The issue explicitly posed two open design questions: (1) should discovery re-run automatically on every Settings page load, or only on an explicit action, and (2) how to keep the candidate-address list easy to extend as new environments (e.g. WSL) come up.

**Options Considered (question 1 — when discovery runs):**

| Option | Pros | Cons |
|--------|------|------|
| Auto-run on every Settings page load | Zero-click default case | Unexpected network probing every time a user opens Settings, even if they never touch the Ollama field — surprising for a privacy-first app whose whole pitch is "nothing happens without you asking" |
| Auto-run once, only if the field is empty | Helps a genuinely fresh install | Still implicit background network activity a user didn't ask for; also indistinguishable from "user deliberately cleared the field" |
| Explicit "Detect" button only | No surprise network activity; user-initiated, matches this app's local-first trust posture | One extra click versus the zero-click ideal |

**Decision:**
1. **Explicit "Detect" button only** (`frontend/src/pages/Settings.tsx`) — discovery never runs automatically, including on page load. `GET /api/settings/discover-ollama` (`src/api/settings.py`) probes a short list of well-known candidate addresses (`src/utils/ollama_discovery.py`) via Ollama's existing health-check pattern (`/api/tags`, matching `OllamaClient.is_available()`), with a short 1.5s per-candidate timeout so a firewalled/hung candidate doesn't stall the whole scan.
2. **Candidate list kept as a flat, ordered constant** (`CANDIDATE_OLLAMA_URLS`) rather than branching logic — `localhost`, `127.0.0.1`, `host.docker.internal`, and Docker's default bridge gateway `172.17.0.1`. Adding a new candidate (e.g. a WSL-specific address) is a one-line addition, not a code change.
3. **Guided fallback when discovery finds nothing**: an in-UI panel with actionable, copy-pasteable guidance for the three real-world non-default cases identified in the issue — a different machine, a different port, or Docker — rather than an empty field with no explanation.

**Reasoning:** An explicit button costs one click in the common case but keeps network activity strictly user-initiated, consistent with the project's local-first, privacy-first positioning — auto-probing on every page visit would be a small but real departure from that posture for a feature whose only job is convenience. The found/not-found result is surfaced in the form state (auto-filling the field on success, showing the guide on failure) but not auto-saved — the user still confirms via the existing Save button, so a bad auto-fill can't silently take effect.

**Status:** Implemented.

---

*Last updated: 2026-07-21*
