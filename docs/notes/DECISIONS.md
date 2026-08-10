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

**Status:** In progress. **Amendment (2026-08-06, #126):** the "Regex patterns + spaCy NER for names" line above describes the intended design, not what a fresh clone actually runs — `spacy` was never added to `requirements.txt`/`environment.yml`, so `SPACY_AVAILABLE` is `False` by default and the effective shipped behavior for free-text fields is **regex-only**. This gap was found via PR #124's benchmark (regex: 63/67 PII caught, 24/24 clinical text intact; regex+ner: 66/67 caught, 23/24 intact) and sized further on #125: `en_core_web_sm` tags common drug names as `PERSON` in **69% of tested contexts (8% in every context)**, e.g. `"Started Rosuvastatin last month."` → `"[REDACTED] last month."` — destroying the most clinically load-bearing token in the sentence. Adding spaCy to the manifests to match this entry's original wording would buy +3/67 name catches at that cost, turning a defect that is currently latent (nobody runs the NER path today) into one live on every install. **Decision: regex-only is the effective default and documented reality; spaCy NER remains optional/aspirational** until #125's item (2) — a false-positive mitigation for the `PERSON` over-redaction — is resolved. Revisit adopting spaCy only after item (2) lands.

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

### DEC-022: Specialty Relevance Mapping Sourced from an External, Publicly-Licensed Pipeline

**Date:** 2026-07-21

**Context:** `src/utils/context_selection.py`'s `SPECIALTY_MAPPING` (Stage 1 of DEC-008's context selection) has been a small, hand-authored `dict[str, set[str]]` since it was introduced — manually enumerated specialty pairs, including broad `{"*"}` wildcards for Primary Care/Internal Medicine/Oncology. This doesn't scale past a handful of specialties and isn't grounded in any external source. Research into replacing it surfaced that no public dataset directly answers "which specialties share clinical context" (as opposed to referral or shared-patient-volume data, which measure a different thing) — building one requires a real pipeline: LLM-assisted generation cross-checked against disease ontologies (Disease Ontology, Mondo, Wikidata) and an empirical anchor (CMS shared-patient data). That pipeline touches several data sources with meaningfully different licenses (CC0, CC BY 4.0, federal public domain, and — explicitly excluded — UMLS/SNOMED and state Medicaid data, which carry redistribution/derivative-work restrictions incompatible with a public artifact).

**Options Considered:**

| Option | Pros | Cons |
|--------|------|------|
| Keep hand-authoring the dict in this repo | No new dependency | Doesn't scale, no external grounding, `{"*"}` wildcards are known-crude, requires domain expertise the maintainer doesn't have |
| Build the generation pipeline inside HealthSteward (`scripts/` or similar) | Everything in one repo | Entangles a general-purpose, publicly-citable dataset artifact with a patient-facing app's codebase and licensing; couples the mapping's release cadence to HealthSteward's |
| **Build the pipeline in a separate, standalone public repo; HealthSteward consumes only the small derived dict** | Dataset is independently citable/reusable, cleanly licensed (CC BY 4.0, matching its CC0/CC-BY-sourced inputs) separate from HealthSteward's own license; versioned independently; the actual generation pipeline and its large raw source data never need to touch this repo | Two repos to maintain; HealthSteward's mapping is now externally sourced rather than self-contained |

**Decision:** Built as a separate repository, intended to go public once the dataset itself is ready — [`nidhi-menon/clinical-specialty-relevance-graph`](https://github.com/nidhi-menon/clinical-specialty-relevance-graph) (currently private; displayed as "SpecialtyBridge" — repo slug kept descriptive for discoverability/citation, display name reserved for the README title and any future paper) (pipeline: LLM-generation cross-checked against Disease Ontology/Mondo/Wikidata, empirically anchored against CMS Physician Shared Patient Patterns data via NBER, with a small clinician-reviewed held-out validation set). HealthSteward's `SPECIALTY_MAPPING` in `context_selection.py` will be replaced with the small derived dict that pipeline produces, with a comment pointing to the source repo for methodology and full licensing detail (see that repo's `docs/SOURCES_AND_DECISIONS.md` for the complete source-by-source accounting).

**Reasoning:** The mapping is genuinely general-purpose — useful to anyone building multi-specialty medical context retrieval, not specific to HealthSteward — so it deserves independent citability and its own license rather than being buried in an app repo. Keeping the two repos separate also avoids licensing entanglement: several candidate sources (UMLS/SNOMED, state Medicaid claims data) were evaluated and excluded entirely, from both the published output and the development process, because their terms prohibit derivative works/redistribution — a determination made explicit and durable in the pipeline repo's own decisions log rather than left as tribal knowledge.

**Status:** Decided. Pipeline repo scaffolded; generation pipeline itself not yet implemented. `SPECIALTY_MAPPING` in this repo still holds the original hand-authored dict pending the pipeline's first output.

---

### DEC-023: Why Context Selection Is a Separate Deterministic Pipeline, Not an Agent Tool

**Date:** 2026-07-22

**Context:** DEC-008's 4-stage context-selection pipeline (rules filter → capped Ollama relevance scoring → token-budget packing → anonymize) runs entirely *before* the agentic tool-use loop (DEC-009/DEC-013) starts, rather than being exposed to the loop as an on-demand retrieval tool the way `get_medication_details`/`lookup_past_visits` are (DEC-013/DEC-015). This split was never separately justified in writing — DEC-008 specifies the mechanism, DEC-009 covers tool-calling reliability, DEC-006 covers anonymization ordering, but no entry states *why* retrieval itself isn't just another tool call. Worth closing that gap explicitly rather than leaving it to be reconstructed by reading three DEC entries side by side.

**Options Considered:**

| Option | Pros | Cons |
|--------|------|------|
| Fold context selection into the agentic loop as a `search_past_visits`-style tool the model calls on demand | One retrieval mechanism instead of two; more "agentic" in spirit | Relevance judgment competes with everything else for the same bounded `agent_max_turns` (6, DEC-009) on a backend already flagged as unreliable at multi-turn tool use on small local models; the agent has no context to reason from in its *first* turn unless something is pre-loaded anyway; makes retrieval quality non-deterministic and harder to eval in isolation (DEC-018 scores retrieval and generation as separate surfaces precisely because they fail differently) |
| **Keep it a separate deterministic pre-processing pipeline; let the agentic loop's tools handle only on-demand "go deeper" lookups** | Baseline context is available before the loop's first turn by construction; relevance judgment happens once, outside the turn budget, so it can't be starved by tool-call unreliability; deterministic stages (1, 3, 4) are exactly assertable in eval (DEC-018) without a judge model; anonymization ordering (DEC-006: nothing leaves the machine unanonymized) is enforced once at a single choke point instead of per-tool-call | Two retrieval paths to reason about (pipeline-selected baseline vs. agent-requested lookups); DEC-018 has to explicitly check `lookup_past_visits` doesn't just redundantly re-surface what Stage 1 already selected |

**Decision:** Context selection stays a separate, deterministic 4-stage pipeline that runs to completion before the agentic loop is invoked. The agentic loop's tools (`get_medication_details`, `lookup_past_visits`) are scoped to supplement that baseline on demand, not to replace or duplicate its retrieval judgment — DEC-018's eval harness treats redundant re-surfacing by `lookup_past_visits` as a signal worth tracking, confirming the two are meant to be complementary layers rather than overlapping ones.

**Reasoning:** Two constraints from earlier decisions compound here. First, DEC-009's finding that small local models produce unreliable tool-calling means anything load-bearing for output quality shouldn't be made to depend on the agent choosing to call it correctly, within a small turn budget, on the default local backend — Stage 1–3 relevance judgment is exactly that kind of load-bearing step, so it runs deterministically outside the loop instead. Second, the loop needs *some* context in its first prompt to reason from at all — full agent-driven retrieval would still need a bootstrapping mechanism, at which point most of the pipeline's value has already been re-invented, just less reliably. Making retrieval quality deterministic and pre-computed also lines up with DEC-018's eval design, which specifically separates retrieval (checkable by exact assertion) from generation (needs a judge) — folding retrieval into the agent loop would blur that line and make Stage 1–3 much harder to eval in isolation.

**Status:** Documented (retroactive — describes the rationale behind the existing DEC-008/DEC-009/DEC-013 architecture; no code change).

---

### DEC-024: Enforce Retrieval Non-Redundancy Between Context Selection and `lookup_past_visits`

**Date:** 2026-07-22

**Context:** DEC-023 describes context selection and the agentic loop's tools as intentionally complementary, non-overlapping layers — but that separation was never actually enforced. `lookup_past_visits` (`src/agents/tools.py`) queried all completed appointments independently, with no awareness of which visits DEC-008's 4-stage pipeline had already selected into the base prompt. `eval/scorers.py`'s `score_retrieval_redundancy` only measured overlap after the fact (its own docstring called it "Observational") — a nonzero overlap rate was a quality signal to notice, not something the system prevented. Auditing whether this was cheap to fix found the original `Appointment.id` was already in scope right up until Stage 4's anonymization step (`context_selection.py`); it just wasn't threaded any further.

**Options Considered:**

| Option | Pros | Cons |
|--------|------|------|
| Leave as observational-only, rely on eval to catch regressions | No code change | The gap was silent — an agent could burn part of its bounded `agent_max_turns` (DEC-009) re-fetching a visit already in its own prompt, with nothing surfacing that as a bug rather than a quality footnote |
| **Thread selected-visit ids from context selection through to the tool executor; filter them out of the `lookup_past_visits` query** | Closes the gap at its root (SQL-level exclusion, not a post-hoc check); trivial given the id was already in scope pre-anonymization; makes DEC-023's "complementary layers" claim actually true | One more field on `ContextSelectionResult` and one more constructor param to keep in sync if either side changes shape |

**Decision:** Added `ContextSelectionResult.selected_visit_ids: list[str]` (`src/utils/context_selection.py`), populated from the pre-anonymization `Appointment.id`s at the same point Stage 4 anonymizes them. Threaded through `VisitPrepAgent._run_agentic_loop`'s new `exclude_appointment_ids` param (`src/agents/visit_prep.py`) into `VisitPrepTools.__init__` (`src/agents/tools.py`), which filters them out of `_lookup_past_visits`'s query via `Appointment.id.notin_(...)`. `eval/scorers.py::score_retrieval_redundancy`'s docstring was updated to reflect that overlap is now a regression signal (the exclusion filter broke) rather than a quality-tuning signal (the model chose to re-fetch). Added `tests/test_agent_tools.py::test_lookup_past_visits_excludes_context_selection_visits`.

**Reasoning:** The fix doesn't cross the anonymization trust boundary (DEC-006) — the excluded-id list is derived from real `Appointment.id`s before anonymization, but only ever used as a SQL filter inside the tool executor; it's never rendered into anything the LLM sees. Since the id was already sitting in scope for free, there was no reason to leave this as an eval-only signal once the gap was noticed.

**Status:** Implemented.

---

### DEC-025: Harden the Hand-Rolled PII Regex List Rather Than Adopt a PII-Detection Library

**Date:** 2026-08-03

**Context:** `PII_PATTERNS` (`src/utils/anonymization.py`) was a hand-authored list of 5 regexes — phone, email, SSN, MM/DD/YYYY date, and a street-address pattern its own comment labelled "simplified" — applied to every free-text field before it crosses DEC-006's trust boundary to an external LLM provider. Unlike a coverage gap in a quality-affecting table, a gap here is a privacy failure: unredacted PII reaches the provider silently, with no error and no visibility. An audit of the 5 patterns against plausible AVS/clinic text found 23 distinct shapes passing through unredacted, including international phone numbers, PO boxes, apartment/unit addresses, most USPS street suffixes beyond the original 9, medical record numbers, insurance member/policy/group IDs, day-first and ISO-8601 and written-out dates, and 2-digit-year birthdates. Two shapes were *partially* redacted, which is its own leak: an international number kept its country and area code ("+44 20 7[REDACTED]"), and a ZIP+4 kept its first two digits, because `phone`'s 7-digit branch consumed the tail first.

**Options Considered:**

| Option | Pros | Cons |
|--------|------|------|
| **Harden the existing hand-rolled regex list in place** | No new dependency; contained entirely to one module and its tests; each added pattern is individually reviewable and testable; ships now | Still fundamentally regex-based — cannot catch PII that has no distinctive lexical shape (names, unlabeled identifiers), so it remains best-effort by construction |
| Adopt an established PII-detection library (Microsoft Presidio, `scrubadub`) | Far broader coverage, actively maintained, NLP-backed rather than shape-matching | New external dependency on the anonymization critical path — a DEC-worthy choice in its own right per the issue's own scope note; heavier install; needs its own evaluation of false-positive behavior against clinical text |
| Leave as-is, document the limitation | Zero risk of over-redaction | Leaves a known privacy gap open on a path DEC-006 designates a hard constraint |

**Decision:** Hardened the existing regex list in place; did not adopt a library. Explicitly the repo owner's call, made in writing on [issue #73](https://github.com/nidhi-menon/HealthSteward/issues/73#issuecomment-5162050035) ("go with Option A — harden the existing regex list ... no new dependency, no schema change"). Library adoption is tracked separately as [issue #92](https://github.com/nidhi-menon/HealthSteward/issues/92) so it can be evaluated deliberately rather than decided under this run's time pressure.

Two structural choices inside that scope are worth recording, since both constrain how the list can be extended later:

1. **Identifier patterns are label-anchored, not shape-anchored.** MRNs and insurance IDs have no distinctive shape — they are bare digit or alphanumeric runs. An unanchored "long digit run" pattern would redact platelet counts, dosages, and lab values. Both patterns therefore require an adjacent label (`MRN:`, `Member ID:`, `Policy #:`) and capture it in a named group, so the label survives redaction and the anonymized text reads `MRN: [REDACTED]`.

   **Amendment (2026-08-03, during PR #114 review):** the repo owner revisited the accepted "unlabeled MRN not caught" gap and judged it the wrong tradeoff on a hard trust boundary — over-redacting an occasional unlabeled clinical value was preferred to missing a real unlabeled MRN. Added `mrn_unlabeled`: a bare 7-10 digit run with no label, excluded when immediately followed by a clinical unit (`mg`, `mmHg`, `IU`, etc.) so measurement-shaped values aren't caught, and placed last in `PII_PATTERNS` so it can't steal digits from a label-anchored match. The length band (7-10) keeps 6-digit values like a typical platelet count out of range; this is a heuristic, not a guarantee — an unlabeled value that happens to be 7-10 digits with no adjacent unit will still be redacted.
2. **Pattern order is load-bearing.** `anonymize_text` applies patterns in declaration order, so a pattern matching a superset must precede one matching a fragment. `zip_code` and `phone_intl` run before `phone` for exactly this reason. This is now stated in a comment on `PII_PATTERNS`, because it is not obvious and a future reordering would silently reintroduce partial-redaction leaks.

**Reasoning:** The issue framed this as a choice between a contained hardening pass and a dependency-adding investigation, and the owner picked the former — correctly, since the two aren't mutually exclusive and the hardening closes 23 concrete leaks now without prejudicing the library evaluation later. The over-redaction risk is the real constraint on how aggressive these patterns can be: this runs on clinical free text, where dose ranges ("25-50 mg"), ratios ("120/80"), fractions ("1/2 tablet"), and lab panels are all date- or identifier-shaped, so every widened pattern is paired with negative test cases asserting clinical content survives. That is also why bare 5-digit ZIPs, bare month-and-year references ("follow up January 2026"), and the street-suffix words most likely to appear in ordinary prose (Park, Point, Row, Run, Path, Bend) are deliberately *not* matched. Redacting a follow-up month would degrade visit prep for no privacy gain.

**Status:** Implemented, including the `mrn_unlabeled` amendment above. Free-text anonymization remains best-effort by design (as README/CONTRIBUTING already state) — this narrows the gap, it does not close it. Library evaluation pending in #92.

---

### DEC-026: Record Visit-Prep Run Path on `ConversationLog.extra_data` Rather Than a Dedicated Counter Table

**Date:** 2026-08-04

**Context:** DEC-013's agentic tool-use loop is fallback-not-hard-failure by design — if it can't converge within `agent_max_turns`, or a backend emits a malformed tool call, `prepare_visit()` (`src/agents/visit_prep.py`) catches the exception and quietly re-runs the request single-shot. That is the right behavior for the patient (no broken visit prep), but it means a backend degrading specifically at tool use — an Ollama or Claude version change that breaks tool-calling reliability — produces no error, no user-visible symptom, and no record. The app just silently stops using the feature DEC-009 exists to provide. `docs/notes/DESIGN.md` §8 listed this as one of three real remaining gaps, mapping to a standard ML design doc's "Model Drift / Alerting" section. Issue #30.

**Options Considered:**

| Option | Pros | Cons |
|--------|------|------|
| **Record per-run diagnostics in `ConversationLog.extra_data`** | No migration — the column is already a flexible JSON blob carrying `system`, `model`, `prompt_version`, `tool_calls`; same shallow-cost pattern issue #16 proposes for redaction events; aggregation is a single indexed-by-timestamp query | JSON-keyed reads aren't indexable, so a large-N aggregate query is a table scan; querying it needs `json_extract`, which is SQLite/MySQL syntax rather than portable SQL |
| A dedicated counter/event table | Indexable, cheap aggregate queries, schema-enforced shape | A migration and a second write path for something a single-user local app reads by hand, at most, a few times a year |
| Log-only (loguru), no persistence | Zero storage cost | Not readable back through the app at all — the existing `logger.warning` on the fallback path is exactly what proved insufficient |

**Decision:** Store `{"agentic_path": bool, "fallback_reason": str | None}` under `extra_data["run_diagnostics"]` on the assistant `ConversationLog` row for every `prepare_visit()` run, and read it back via `GET /api/diagnostics/visit-prep-fallback?limit=N` (`src/api/diagnostics.py`), which reports the rate over a rolling window of the last N runs broken down by reason. Explicitly the repo owner's call, made in writing on [issue #30](https://github.com/nidhi-menon/HealthSteward/issues/30#issuecomment-5175382279) ("reuse `ConversationLog.extra_data`, as planned ... a dedicated counter table is only worth it once there's an actual need for indexed/aggregate queries at scale, which a single-user app doesn't have").

Two choices inside that scope constrain how this can be extended:

1. **The reasons are an enumerated vocabulary, not free text**, and non-convergence gets its own exception type. `_run_agentic_loop` previously raised a bare `RuntimeError` on turn exhaustion, which `prepare_visit` caught alongside `RuntimeError`s raised by the backend itself — so the expected, benign outcome and a genuine defect were literally the same exception. `AgenticLoopNotConvergedError(RuntimeError)` now separates them, and `_classify_agentic_failure` maps each caught exception to one of `tool_use_disabled` / `non_convergence` / `parse_error` / `unknown_tool` / `loop_error` / `backend_unavailable`. Issue #30's third point — "log the failure reason distinctly ... so a real tool-execution bug isn't indistinguishable from expected non-convergence" — is only satisfiable if that distinction exists at the raise site.
2. **The hard-failure path writes its own log row.** When both the loop and single-shot fail, no LLM response exists, so `_log_conversation`'s normal call sites never run and the run would leave no trace at all — the *worst* outcome would have been the one invisible to a feature built to surface bad outcomes. `_log_hard_failure` writes a content-free row carrying only the diagnostics, and preserves any preceding agentic failure as `prior_agentic_failure` so a backend that breaks tool use on its way down doesn't read as a plain outage.

**Reasoning:** The deciding factor is who reads this and how often. This is a single-user local app; the realistic access pattern is a human checking "is tool use still working" after noticing prep output got worse, not a monitoring system polling continuously. At that cadence a table scan over a few hundred JSON blobs is irrelevant, and the migration a counter table would need is real cost paid now against a benefit that only materializes at a scale this app doesn't have. The reverse is also cheap: if aggregate queries ever do matter, the JSON rows are a complete history to backfill a real table from.

Deliberately *not* overloading the existing `VisitPrep.used_fallback` column (DEC-020) for this, despite the name collision being tempting: that flag means "the model produced nothing and these are hardcoded placeholder questions," and drives a user-facing warning banner. Agentic → single-shot fallback still produces a real, personalized answer, so setting `used_fallback` for it would show the patient a "these are generic default questions" warning over questions that are nothing of the sort.

**Status:** Implemented. Read-on-demand only — nothing alerts on a rising fallback rate, which remains open (`DESIGN.md` §8).

---

### DEC-027: Soft-Delete Profiles with Lazy Expiry Cleanup, Not a Scheduled Job

**Date:** 2026-08-04

**Context:** `delete_profile` (`src/api/health_profile.py`) was a true, immediate `db.delete(profile)`, cascading through every related table. The frontend guards it with a type-to-confirm modal (`DeleteConfirmModal` — the user must type the exact profile name), which is a genuinely high bar, but there was no recovery path once that bar was cleared: no undo, no window, nothing. For the target caregiver persona — tracking a parent's or child's health over months or years, including hand-entered notes that exist in no other system — one mis-aimed confirmation destroys everything irrecoverably. Low probability, maximum severity. Issue #50.

Export-before-delete was considered and explicitly rejected on the issue before implementation: it addresses a different use case (leaving the app, switching devices — now tracked as #93) and would not have helped the person who just deleted the wrong profile.

**Options Considered:**

| Option | Pros | Cons |
|--------|------|------|
| **Soft-delete (`deleted_at`) + lazy cleanup on next profile-list access** | Recovery path with no new infrastructure; cleanup runs exactly when someone is already querying profiles; nothing under the profile is altered at delete time, so restore is a single field write | Expiry is only enforced when the app is used — a profile can outlive its 30 days on disk if nobody opens the app |
| Soft-delete + a background scheduler | Expiry happens on time regardless of use | No job-scheduling infrastructure exists in the app; building it here means building it speculatively for #25 (scheduled push notifications), which isn't scoped or started |
| Keep hard delete, add an export-before-delete step | No schema change | Doesn't address the actual failure mode — the person who deleted the wrong profile still has nothing to restore from |

**Decision:** Added a nullable `HealthProfile.deleted_at` (migration `c8f2b41d7e93`). `DELETE /api/profiles/{id}` sets it instead of deleting the row; every profile lookup filters `deleted_at IS NULL`; `GET /api/profiles/deleted` lists soft-deleted profiles with a computed countdown; `POST /api/profiles/{id}/restore` clears the field. After `SOFT_DELETE_RETENTION_DAYS` (30), `purge_expired_profiles()` performs the real cascading delete, invoked lazily from the two list endpoints.

Lazy cleanup over a scheduler is explicitly the repo owner's call, made in writing on [issue #50](https://github.com/nidhi-menon/HealthSteward/issues/50#issuecomment-5175382109) ("go with lazy cleanup on next relevant access ... Building shared scheduler infrastructure speculatively for #25 would be premature here"), with a cross-link left on #25 so the migration path isn't lost if a real scheduler is ever built.

Three choices inside that scope constrain how this can be extended:

1. **No cascade at soft-delete time.** Conditions, medications, documents and the rest are left exactly as they are, merely unreachable. This is what makes restore a single field write rather than an undo log, and it is why the recovery window can be extended or shortened later without touching any child table.
2. **Restore deliberately does not purge first.** A profile past its window but not yet cleaned up is still restorable. The alternative — running cleanup on the restore path — means a restore click could destroy the very profile it was trying to bring back, which inverts the point of the feature.
3. **Child routers filter too, but two routers were left out of scope.** `conditions`/`medications`/`doctors`/`appointments` all resolve the profile through `verify_profile_exists` and now 404 for a soft-deleted one, so a stale open tab can't keep reading or writing. `action_items.py` and `documents.py` never verified the profile at all (an unknown id returns `200 []` there today), so bringing them in line is a behavior change beyond soft-delete — filed as [issue #119](https://github.com/nidhi-menon/HealthSteward/issues/119) rather than folded in silently.

**Reasoning:** The deciding constraint is that the failure mode being defended against is rare but total. That argues for the cheapest mechanism that makes it recoverable, not the most complete one — hence a nullable timestamp and a filter, rather than an audit log, a tombstone table, or a versioned-record scheme. Lazy cleanup's known weakness (expiry not enforced while the app sits unused) affects *when data is destroyed*, never *when it stops being visible*, so the user-facing contract holds regardless; the residual risk is data lingering on disk longer than 30 days, which is strictly the safer direction to fail in for a recovery feature.

Scoped to profile-level deletion only, per the issue. Individual conditions/medications are single-item deletes where manual re-entry is a reasonable recovery path, and giving every table a recovery window would be a much larger change than the failure mode justifies.

**Status:** Implemented. Follow-up gap tracked in [#119](https://github.com/nidhi-menon/HealthSteward/issues/119).

*Amended 2026-08-06 ([issue #123](https://github.com/nidhi-menon/HealthSteward/issues/123)):* **profile export is not exempt from the filter.** `export_profile` (DEC-028) was written before this entry landed and kept its own unfiltered `select(HealthProfile).where(id == profile_id)`, which made it the one profile route still serving a soft-deleted profile — fully exportable by anyone holding the URL while every other route 404'd. It now resolves through `get_live_profile_or_404` like everything else, so "deleted means unreachable" holds without exception. The repo owner's call on #123, choosing consistency over the "grab a copy before the purge" use case: that use case is real but wants a discoverable affordance on the "Recently deleted" view ([#130](https://github.com/nidhi-menon/HealthSteward/issues/130)), not a URL-only backdoor. Recorded here rather than as its own DEC entry because it settles a boundary this entry and DEC-028 left ambiguous between them, rather than making a new choice.

---

### DEC-028: Profile Export Format — Full-Fidelity JSON Dump, Metadata-Only for Documents

**Date:** 2026-08-04

**Context:** HealthSteward holds the only copy of a user's health history, on one machine that probably isn't backed up. "Your data never leaves your machine" cuts both ways: it also means if the machine dies, the record dies with it. No export path existed at all — not structured, not human-readable. Issue #93.

Three scoping questions were resolved by the repo owner in writing on [issue #93](https://github.com/nidhi-menon/HealthSteward/issues/93#issuecomment-5175381931) before implementation: **per-profile** rather than one-click-everything (matching the per-profile scoping DEC-027 uses for deletion); **plaintext** rather than encrypted, since no encryption-at-rest mechanism exists yet to hang it off (#92 is unstarted) and encrypting the export alone would be a partial, misleading guarantee; and a **local file the user manages themselves**, with no cloud destination, since a cloud target would need its own trust-boundary discussion rather than arriving as a quiet default.

**Options Considered:**

| Option | Pros | Cons |
|--------|------|------|
| **Full-fidelity dump: every profile-scoped table, every column, keys included** | Restorable into a faithful copy; nothing silently missing; the shape is mechanical, so a column added to a model is exported automatically | Larger file; exposes internal ids and `file_path`s to anyone reading the backup |
| Curated "user-meaningful fields only" export | Smaller, more readable by hand | Drops the foreign keys, so which appointment was with which doctor is unrecoverable — the file stops being a backup and becomes a summary |
| Embed uploaded PDFs as base64 | Genuinely complete — a restore on a new machine has the source documents | Multiplies file size by the entire document corpus; makes the export unreadable as text; the parsed contents (which is what the app actually uses) are already included |

**Decision:** One `GET /api/profiles/{id}/export` endpoint returning a JSON document with `export_format_version`, `exported_at`, `app_version`, the profile's own fields, and a top-level list per profile-scoped table — conditions, medications, doctors, appointments, documents, vitals, lab orders, referrals, follow-ups, nudge states — plus `visit_preps`, which hangs off appointments rather than the profile. Primary and foreign keys are included. Served with `Content-Disposition: attachment` so the browser saves it rather than rendering it.

Three choices worth recording:

1. **`export_format_version` ships in v1, before anything needs it.** It is the one field that is genuinely expensive to add later — files already written to disk won't have it, so a future importer would have to guess a document's shape from its contents. Cheap now, impossible retroactively.
2. **Serialization is driven off the SQLAlchemy mapper, not a hand-written field list.** A column added to a model is exported automatically. The failure mode of the alternative is silent and only discovered at restore time: a new field simply wouldn't be in anyone's backup, and nothing would say so.
3. **Documents are metadata + parsed contents, not the source PDFs.** The parsed contents are what the app actually reads; the PDFs are large, opaque as base64, and still sitting on disk where `file_path` records them. This is a real limitation, so the export states it in a `documents_note` field inside the file itself rather than leaving a reader years later to infer it from an absence.

Nothing is redacted. DEC-006's anonymization exists to protect data crossing a boundary to an external LLM provider; this file is written by the user, for the user, and never leaves their machine — anonymizing it would corrupt the backup to defend against a threat model that doesn't apply.

**Reasoning:** The value of a backup is measured entirely at restore time, and every reduction in fidelity is a restore that silently produces something less than what was lost. That argues for dumping everything and accepting a larger file, rather than curating — the curated version is a *report*, which is a legitimate but different feature (the human-readable export in #99). The one place fidelity was traded away, the source PDFs, is the one place where the alternative is a category change in file size for content the application doesn't read back.

**Status:** Export implemented. **Import deliberately not implemented** — its semantics (merge into an existing profile, replace that profile's contents, or create a new profile from the document) determine whether a restore can duplicate or destroy a user's only copy of their history, and the three readings lead to materially different features. Raised as an open question on [issue #93](https://github.com/nidhi-menon/HealthSteward/issues/93) rather than guessed at; #93 stays open until it lands.

---

---

### DEC-029: Log Redaction Events (Type + Span + Stable Hashed ID) Per Visit-Prep Request

**Date:** 2026-08-05

**Context:** `Anonymizer.anonymize_text()` (DEC-006's implementation) did the regex/NER substitution and discarded what it matched. There was no record of what was found and redacted for a given visit-prep call, so a name or identifier slipping past the regex/NER net was unauditable after the fact — a Reddit comment on the pluggable-backend post put it as "redaction recall is the whole ballgame ... worth logging what got redacted so you can audit misses." Issue #16.

A community follow-up on the issue clarified two points before implementation: the correct aggregation granularity is **per visit-prep request**, not per-document — AVS PDFs are parsed entirely locally by Ollama and never anonymized at all, since nothing derived from them leaves the machine at that stage; redaction only happens on live profile/appointment data at the moment it's about to reach whichever LLM is generating visit prep. And entities should carry a **stable per-entity ID**, not just an aggregate count, so a later write-back-capable agentic tool could be checked against exactly which entities a given run could and couldn't see.

**Options Considered:**

| Option | Pros | Cons |
|--------|------|------|
| **Return `(text, list[RedactionEvent])` from every anonymize_* method; aggregate per-request in `ConversationLog.extra_data`** | No schema migration (`extra_data` is already a flexible JSON column); type+span is auditable without ever re-exposing the matched value; stable ids support future write-back auditing | Threads a second return value through every call site (`anonymize_profile`, `anonymize_doctor`, `anonymize_appointment`, `VisitPrepTools`, Stage 4 of context selection) |
| Log a per-pattern redaction *count* only | Simplest possible change | Can't answer "did entity X make it into this specific run" — the exact question a future write-back tool would need answered, per the issue's follow-up discussion |
| Log the matched substring alongside its type | Maximally useful for auditing false negatives by hand | Directly defeats DEC-006's purpose — logging the very PII that redaction exists to keep off the LLM's — and off disk's — audit trail |
| Random UUID per redaction event | Simple to generate | Not reproducible — two runs against the same unchanged field would log unrelated ids, making "is this the same entity as last time" unanswerable |

**Decision:** `anonymize_text()` now returns `(anonymized_text, list[RedactionEvent])`; `RedactionEvent` carries `entity_id`, `entity_type` (the `PII_PATTERNS` key or `"PERSON"` for NER), `start`/`end` span offsets, `field_name`, and an optional `document_id`. `entity_id` is `sha256(profile_id | field_name | entity_type | occurrence_index)`, truncated — deterministic and reproducible across runs against the same underlying field, never derived from the matched content. Every anonymize_* method (`anonymize_text`, `anonymize_profile`, `anonymize_doctor`, `anonymize_appointment`) and both call sites that use them (`VisitPrepTools` in `src/agents/tools.py`, Stage 4 of `context_selection.py`) now return/aggregate events. `VisitPrepAgent.prepare_visit` collects everything into `self.last_redaction_events` across the whole request — profile/appointment anonymization, Stage 4 context selection, and any agentic-loop tool-result anonymization — and `_log_conversation` (`src/agents/base.py`) writes it to the assistant `ConversationLog` row under `extra_data["redaction_events"]`.

Where the underlying record has a `document_id` column (`Vitals`, `LabOrder`, `Referral`, `FollowUp` per `src/data/models.py`), an event can be tagged with it — `RedactionEvent.document_id` is threaded through as an optional parameter for exactly this. `Condition`, `Medication`, and `Appointment` have no `document_id` column and none was added — per the issue's explicit non-goal, most PII-bearing free text (visit notes, additional concerns) is user-typed and was never document-sourced to begin with, so a full migration wouldn't fully solve "per-document" traceability anyway. Fields with no document lineage — including all of today's actual anonymize_text call sites (condition/doctor notes, appointment purpose/notes, additional_concerns) — log `RedactionEvent.to_dict()`'s explicit `"document_link": "none"` rather than omitting the key or fabricating a value.

**Reasoning:** The deciding factor is that this is an audit feature, and a redaction audit that logs the very thing it's trying to prove was removed is worse than no audit at all — so type+span+stable-id was the only shape on the table that doesn't reopen DEC-006's trust boundary while still being genuinely useful (a person or future tool can ask "was entity `<hash>` present in this run" without ever reconstructing what it was). Threading a second return value through every anonymize_* call site is real code churn, but it's a one-time cost paid once at the boundary that already exists (DEC-006's), rather than a new boundary.

A pre-existing duplication was also fixed in passing: `VisitPrepAgent._build_anonymized_context` was calling `anonymize_text` on `condition.notes` a second time (the first being inside `anonymize_profile`, whose result went unused for that field). Left as-is it would have doubled every condition-notes redaction event; fixed by reusing `anonymize_profile`'s already-anonymized notes instead of re-anonymizing.

**Status:** Implemented. No UI surfacing (matches the precedent set by #30/DEC-026's diagnostics fields) — the data is queryable directly from `extra_data`. New tests added to `tests/test_anonymization.py`, `tests/test_agent_tools.py`, and `tests/test_visit_prep.py` covering: type/span never the raw value; stable entity ids across repeated runs and distinct ids across different field names; `document_id` tagging when supplied and honest `"document_link": "none"` when not; and end-to-end aggregation into `ConversationLog.extra_data["redaction_events"]`.

---

### DEC-030: Partition `data/avs/` Per Profile, with Opt-In File Deletion Deferred to Purge Time

**Date:** 2026-08-05

**Context:** `data/avs/` was a single flat folder scanned for every profile. `scan_documents` (`src/api/documents.py`) listed every PDF in it unconditionally and only overlaid profile-scoped status by matching against `Document` records — the scan itself was never filtered by profile. This caused two real cross-profile problems, not just an inconvenience: a PDF already parsed and applied to Profile A still showed as "New" under Profile B (nothing stopped it being parsed and applied a second time, to an unrelated profile — a real risk for the caregiver persona this app targets, e.g. a parent tracking multiple kids); and `delete_profile` cascade-deleted `Document` rows but never touched the file on disk, so a deleted profile's PDF reappeared as "new" in the shared folder and could be picked up by a different profile than the one it originally belonged to. Issue #49.

Separately, AVS PDFs are the user's own source documents (obtained from a clinic, not generated by the app) — deleting a profile shouldn't silently delete those originals. Issue #50/DEC-027 had already made profile delete a 30-day-recoverable soft delete by the time this was implemented, which changed the natural place for any opt-in file deletion to hook in.

**Options Considered:**

| Option | Pros | Cons |
|--------|------|------|
| **Partition by `profile_id` subfolder; delete files only at purge time, opt-in** | Cross-profile visibility becomes structurally impossible, not just filtered; file deletion inherits the soft-delete's 30-day recoverability for free — no separate undo path needed | Needs a one-time migration for existing installs; adds a DB column + migration |
| Partition by a human-readable slug instead of `profile_id` | Nicer for anyone poking around `data/avs/` directly | Needs collision/rename handling that `profile_id` gets for free; no functional benefit over the id |
| Delete AVS files immediately at soft-delete time (opt-in) | Simpler — one write, no second hook needed | Directly contradicts DEC-027's recovery guarantee: a profile restored inside its 30-day window would come back missing its source documents, silently worse than before deletion |
| Keep the flat folder; filter `scan_documents` by profile server-side only | Smallest change, no migration | Files are still physically visible/movable across profiles on disk; doesn't fix the "can be applied to a second profile" risk, only hides it from one screen |

**Decision:** AVS files live at `data/avs/<profile_id>/` instead of a flat `data/avs/`. `scan_documents` and `parse-file` (`src/api/documents.py`) both scope to the requesting profile's subfolder. A new nullable-defaulting `HealthProfile.purge_avs_files_on_expiry` boolean column (migration `50e07994bbfe`, chained off `c8f2b41d7e93`), default `false`, is set via an opt-in checkbox in `DeleteConfirmModal` (`frontend/src/pages/ProfileDetail.tsx`) at soft-delete time — captured then, but not acted on then. The actual `shutil.rmtree` of `data/avs/<profile_id>/` happens inside `purge_expired_profiles` (`src/api/health_profile.py`) only for profiles that are both past the 30-day window and have the flag set; a profile restored before expiry keeps its files regardless of the flag, since `restore_profile` just clears `deleted_at` and purge never runs against a live profile.

A one-time migration script, `scripts/migrate_avs_per_profile.py`, moves each existing top-level file into `data/avs/<profile_id>/` by matching its existing `Document.profile_id` (same `(original_filename, file_size_bytes)` key `scan_documents`/`parse_file` already use); files with no matching `Document` record — today's "new/unclaimed" files — move to `data/avs/_unassigned/` rather than guessing an owner. It is idempotent: only top-level files are ever considered "unmigrated," and a destination-name collision is skipped with a warning rather than overwritten.

**Reasoning:** Partitioning by `profile_id` rather than scanning-and-filtering is the only option that makes cross-profile leakage structurally impossible instead of merely hidden from the current screen — matching how every other profile-scoped table in this app already works. Deferring deletion to purge time was the deciding call once DEC-027's soft-delete existed: deleting files at soft-delete time would make "restore" a lie for exactly the users who opted into deletion, and there is no version of "opt-in delete, but only sometimes recoverable" that isn't more confusing than just gating on the same 30-day window every other cascade already respects. `_unassigned/` over guessing is the same non-goal DEC-006 and DEC-025 already established elsewhere in this codebase: silent wrong guesses about a user's PII/health documents are worse than an explicit "unresolved" bucket a human can sort by hand.

**Status:** Implemented. Tests in `tests/test_avs_partitioning.py` cover scan isolation between profiles, migration partitioning (claimed → `<profile_id>/`, unclaimed → `_unassigned/`) and idempotency, opt-in deletion firing only when the flag is set *and* the profile actually purges (not at soft-delete time), and a restored profile keeping its files untouched even with the flag set.

---

### DEC-031: FHIR Bundle Import — File-Upload Only, Two Resource Types, Deferred Reconciliation

**Date:** 2026-08-06

**Context:** Issue #101 asked for a way to import records from Apple Health / FHIR bundles, since manual entry is currently the only on-ramp for a new user's data besides AVS PDF parsing — high friction, high abandonment risk for a new caregiver setting up a profile. FHIR (Fast Healthcare Interoperability Resources) is a large, general-purpose standard with well over 100 resource types; a real-world bundle (from a hospital portal's Patient Access API export, or eventually an Apple Health companion app) can carry anything from conditions and medications to insurance claims and imaging reports. Scoping what this project actually imports, and how, needed its own decision before implementation — a new external data format entering the system, per DEC-006's precedent for anything crossing a trust boundary.

**Options Considered:**

| Option | Pros | Cons |
|--------|------|------|
| **File-upload FHIR bundle import, `Condition` + `MedicationStatement` only, reusing the existing AVS preview/apply flow** | Smallest slice that's still useful; reuses `documents.py`'s proven parse→preview→apply pattern instead of inventing a new one; validates field-mapping and duplicate-detection questions cheaply before any Apple/iOS investment | Only covers two resource types out of the many FHIR supports; still requires the user to obtain a FHIR file themselves, which most patient portals don't make an obvious, one-click, non-technical operation |
| Also build the Apple Health companion app (`HKClinicalRecord.fhirResource`) in this same slice | Removes the "where do I even get a FHIR file" friction that undercuts the backend-only slice's real-world usefulness | Separate engineering surface (Swift, HealthKit entitlements, Apple Developer Program membership, iOS build/release process) bundled into what should be a backend-scoped decision; conflates two independently shippable pieces |
| Wait for live SMART-on-FHIR OAuth (direct provider connection) before shipping anything | Best end-state UX — no file wrangling by the user at all | Per-EHR-vendor OAuth registration, ongoing token/sync maintenance, a new persistent external-connection trust boundary; large, open-ended scope with no incremental deliverable — the wrong thing to gate the first slice on |
| Map all plausible resource types in the first pass (`Condition`, `Medication`, `Vitals`, `LabOrder`, `Referral`, `Doctor`, `AllergyIntolerance`, `Immunization`, `Procedure`) | One PR instead of many; "does everything FHIR can do" from day one | Each resource type is its own mapping decision, not boilerplate (see Reasoning); several have real structural mismatches against existing tables (`Vitals` is one `Observation` per vital sign, not one bundled resource; `LabOrder` conflates FHIR's order-vs-result split) that are better worked through one at a time with real bundles in hand, not guessed at upfront |

**Decision:** Ship a backend-only FHIR bundle import path, file-upload triggered (not live OAuth, not Apple HealthKit — those are separate follow-on issues, #137 and #138), covering exactly two resource types in this first slice: `Condition` and `MedicationStatement` (implementation tracked as issue #135). It reuses the existing AVS-style parse→preview→apply flow in `src/api/documents.py` rather than inventing a new review UX. Every other clinically relevant resource type (`Vitals`, `LabOrder`, `Referral`, `Doctor`/`Practitioner`, `AllergyIntolerance`, `Immunization`, `Procedure`) is out of scope for this DEC and tracked as follow-on issue #136, to be worked through incrementally, one resource type at a time, once this slice's plumbing (parser dispatch, preview/apply integration) exists to build on.

**Field-mapping decisions for the two resource types in scope:**
- `Condition.icd_10` is **not** assumed to hold an ICD-10 code. FHIR `Condition.code` is commonly SNOMED CT, not ICD-10 — the column stores whatever code the bundle provides, and a new nullable `coding_system` column (e.g. `"http://snomed.info/sct"`, `"http://hl7.org/fhir/sid/icd-10"`) is added alongside it so downstream consumers know which vocabulary they're looking at rather than assuming.
- `Medication.purpose` and `Medication.side_effects` are left `NULL` on FHIR-sourced rows. Neither has a reliable home in `MedicationStatement` — `side_effects` in particular would come from `AllergyIntolerance`/`AdverseEvent` resources, which are out of scope here. This is a documented gap, not a silent drop: the import preview UI should indicate these fields weren't populated from the source, the same way AVS-sourced rows already distinguish parsed-vs-blank fields.
- A new `source` field (or equivalent provenance marker, exact shape TBD at implementation time) distinguishes FHIR-imported rows from AVS-parsed or manually-entered ones, so future reconciliation work (see below) has something to key off.

**Reconciliation is explicitly deferred, not solved, here.** Issue #97 (reconcile conflicting records across sources) is itself unscoped and unbuilt — its own issue text says it needs an audit before sizing, and the underlying problem (silent overwrite on apply) already exists today between manual entry and AVS parsing, tracked separately as issue #46. FHIR import doesn't introduce a new category of problem, it just makes an existing, already-open one more frequent (a condition entered manually as "Type 2 Diabetes" and the same condition arriving via FHIR as SNOMED-coded "Type 2 Diabetes Mellitus" won't string-match). Rather than block this slice on #97, it ships with one narrow, deterministic mitigation: a fuzzy name-match check against the profile's existing `Condition`/`Medication` rows, surfaced as a "possible duplicate of existing entry" flag in the preview UI. The user decides merge/skip/add-new; nothing is auto-merged. This is a stopgap consistent with DEC-023's precedent for deterministic-over-agentic on load-bearing steps, not a general solution — #97, once scoped, may supersede it.

**Reasoning:** Two resource types, not the full plausible set, because each FHIR-to-table mapping is a real design decision rather than boilerplate — `Vitals` needs aggregation logic to fold multiple `Observation` resources into one row per visit, `LabOrder` needs a decision about FHIR's order-vs-result split that doesn't cleanly map onto this table's snooze/complete lifecycle, and `Doctor` needs joining three separate resources (`Practitioner`, `PractitionerRole`, `Organization`). Doing all of that speculatively, without real-world bundles in hand to validate against, risks guessing wrong on several mappings at once instead of learning from the first two and applying that to the rest. `Condition` and `MedicationStatement` were picked specifically because they have the cleanest 1:1 resource-to-table shape and match the issue's own "smallest viable slice" framing. File-upload over Apple HealthKit or SMART-on-FHIR because both alternatives bundle a materially larger, independently-schedulable engineering surface (an iOS app with its own Apple Developer Program cost and release process; or per-vendor OAuth registration and an ongoing token-sync relationship) into what should be a backend-scoped decision — shipping the backend path first also means the harder unknowns (field mapping, duplicate detection) get validated cheaply before any of that investment happens. This mirrors DEC-006's boundary-first instinct: get the trust and mapping questions right before widening how data can get in.

**Status:** Proposed. Not yet implemented. Implementation tracked as issue #135. Follow-on issues: #136 (additional FHIR resource types), #137 (Apple Health companion app via `HKClinicalRecord`), #138 (live SMART-on-FHIR OAuth, deferred indefinitely pending real user demand for the file-upload path first).

---

### DEC-032: Care Circle Escalation — Scoped Contacts, Local Scheduler, Own-Account SMTP, No Automatic Loop-Closure

**Date:** 2026-08-06

**Context:** A LinkedIn post surfacing the PACT framework (Khairat & Safran, npj Health Systems, 2026) prompted a review of HealthSteward's follow-up tracking against its five elements for accountable post-visit action: owner, channel, confirmation rule, escalation trigger, outcome measure. `FollowUp`/`LabOrder`/`Referral` (`src/data/models.py:362-446`) already cover confirmation rule (status/completed_at/snoozed_until) reasonably well, but have no owner, no outbound channel, and no escalation trigger — DEC-012 explicitly deferred push notifications as conflicting with the local-first architecture (issue #25), and DEC-027 reaffirmed that no job-scheduling infrastructure exists and building one speculatively would be premature. This DEC scopes what a genuinely automatic (not click-through) escalation path would look like, and what it would newly cost the trust boundary, without committing to build it yet.

**Options Considered:**

| Option | Pros | Cons |
|--------|------|------|
| **Care-circle contacts (scoped by task category) + local OS scheduler (`launchd`) + SMTP via the patient's own email account** | No third-party vendor touches message content; trigger fires without the app open; contact routing is structured (dropdown-driven task category) instead of free text, so escalation logic can join deterministically | Still genuinely new infrastructure — first HealthSteward component that runs outside the app process and sends data on its own; SMTP credential storage needs care (OS keychain, not plaintext) |
| Third-party notification API (Twilio/SendGrid) | Simplest to build; reliable delivery | A vendor HealthSteward doesn't control receives message content on every send — a new data-sharing relationship that contradicts the "nothing leaves your machine" positioning and would need its own privacy-notice update |
| Manual/click-through escalation only (patient-triggered `mailto:` link, no scheduler) | Zero new infrastructure, zero new trust boundary | Doesn't solve the actual problem — PACT's escalation trigger exists specifically for the disengaged-patient case, and a mechanism that depends on the disengaged patient clicking something doesn't address that. Considered and rejected as insufficient at this decision point, though it may still ship as a smaller interim step. |
| Do nothing; leave escalation on issue #25 indefinitely | No cost | Leaves owner/channel/escalation permanently unaddressed; the PACT review surfaced these as HealthSteward's clearest structural gaps |

**Decision:** If built, escalation should take the first shape: a `CareContact` table (name, relationship, email, one or more `task_category` scopes — `appointment`/`lab_order`/`referral`/`medication`/`all` — chosen from a fixed enum, not free text, so routing logic can join deterministically against overdue items) checked daily by a `launchd`-scheduled local job, sending via SMTP through credentials the patient supplies for their own email account (stored via OS keychain, not the app DB). This is **not yet approved for implementation** — it is scoped here so the trust-boundary tradeoff is on record before anyone starts building, per this project's documentation-before-implementation convention for anything crossing a boundary (DEC-006's precedent).

**Known limitations, not fully solved by this design (carried forward from the PACT review discussion):**
- **No identity/authority verification.** HealthSteward cannot distinguish a licensed care coordinator from a well-meaning relative — both are the same row in `CareContact`. Whatever authority a contact has to actually act (rebook, override, call the clinic) is a real-world fact the app has no visibility into and can't grant or verify.
- **No automatic loop-closure.** Even if a contact acts on an escalation, HealthSteward has no account/API for them to write back automatically — closing this fully would require the recipient to have some way to write into the app, which is a bigger architectural shift than this feature alone warrants.
- **Consent/PHI exposure to an unverified recipient.** An automated email to an address the patient typed in once, with no confirmation the recipient wants or expects it, is a thinner consent basis than the family-notifying-family case, and a professional recipient's own institution may have policies about unsolicited automated clinical email.

**Mitigations, revised to reuse the same SMTP account for IMAP polling rather than relying on non-bounce:**

Since the patient already supplies credentials to their own email account for sending, that same account can be polled via IMAP by the `launchd` job on its regular run — no new vendor, no publicly-reachable server, no inbound webhook. This is a materially better mitigation than the original bounce/opt-out-only design:

- **Conscious opt-in, not passive non-bounce.** The first message to any new `CareContact` asks for an explicit reply (e.g. "Reply YES to receive updates about [patient]'s care") rather than treating silence as consent. Automated sends to that contact begin only after a matching affirmative reply is polled, not merely after the message fails to bounce.
- **Digest cadence, one thread per (contact, period), not one thread per task.** Rather than a separate email/thread per escalation, each contact gets a single periodic digest (e.g. weekly) listing every task currently in scope for them as numbered line items ("1. Dad's cardiology referral (due Aug 3)", "2. Mom's lab order pickup (due Aug 5)", ...). This is a revision of the earlier per-task-thread design: task correlation now happens via a task-ID token per line inside one message, not via separate `Message-ID`/`References` threads — fewer, more infrequent touchpoints for the contact, and no thread-proliferation problem for contacts scoped to multiple categories or profiles.
- **Two reply paths, preferred-then-fallback.** (1) *Preferred:* each line item carries two `mailto:` links ("Yes, done" / "Not yet"), pre-filled with a task-ID tag in the subject and a fixed "YES"/"NO" body — one click, no typing, and parsing on receipt is trivial (exact string match, not natural-language interpretation) since the app authored the entire reply itself. (2) *Fallback:* the digest also accepts a single inline-edited reply-all covering every line (recipient fills in YES/NO next to each numbered item and sends once) for contacts who'd rather answer everything together — parsed with a tolerant per-line pattern matcher.
- **Fail-safe parsing, not best-effort guessing.** A matching reply (via either path) updates a distinct `reported_by_contact` sub-state — **not** `completed` directly; the patient's in-app confirmation remains the sole source of truth for `status`. Any line or reply the parser can't confidently interpret is left unanswered rather than guessed. Given free-text inline-edit replies are inherently less reliable than the pre-authored `mailto:` path (quoted-reply formatting, top-posting, partial edits), the inline-edit fallback should ship behind a "here's what I understood — reply CONFIRM if correct" round-trip until its real-world parse accuracy across common mail clients is validated, rather than trusted silently from day one.
- **Message content minimization**, unchanged from the original design: escalation emails carry task category and how-overdue, not clinical detail (e.g. "a referral is overdue" not "referral to Dr. X for [condition]"), regardless of who the recipient turns out to be.

This narrows, but does not eliminate, the no-automatic-loop-closure limitation: the real-world action (rebooking, calling the clinic) still happens entirely outside HealthSteward, and a contact's reply — by either path — is only ever a self-report the app treats as unverified. What changes is that a report of that action can now flow back into the app via a mechanism the patient consciously opted into, instead of leaving the outcome purely unrecorded.

**Outcome measure (separate, lower-cost, addressed regardless of whether escalation ships):** per-profile × per-task-category completion rate, computed from existing `status`/`completed_at`/`target_date` fields with no schema change and no scheduler. This is HealthSteward's structural analog to PACT's stratified outcome measure — PACT stratifies by language/digital-access because it targets a health-system population; HealthSteward has no population, but it does have multiple profiles per operator (DEC-027's caregiver persona — one person tracking a parent's and a child's records), so stratifying by profile and task category is the axis that actually exists here, not a retrofit of PACT's original axis.

**Reasoning:** SMTP-via-own-account over a third-party notification API because it's the only channel option that doesn't introduce a vendor relationship HealthSteward doesn't control — consistent with the existing "no cloud, nothing leaves your machine" tagline. `launchd` over an in-process scheduler (e.g. APScheduler) because a locally-run app that isn't always open needs a trigger that survives the app being closed — an in-process scheduler only fires while the server happens to be running. Scoped `task_category` dropdown over free-text "what to contact them about" because deterministic routing (join overdue items against contact scopes) is a prerequisite for any of this being real automation rather than another manual step; free text can't be safely mapped to actions. The known-limitations section is included in the decision itself, not left implicit, because both the identity-verification gap and the no-write-back gap are structural to local-first/no-accounts, not implementation shortcuts — future readers should know the ceiling was understood up front, not discovered later.

**Terminology — NOTICE, not PACT:** PACT (owner, channel, confirmation rule, escalation trigger, outcome measure) assumes a health-system backend with staff to route tasks to; HealthSteward has no such backend, so borrowing PACT's terms directly overstates what this design guarantees. Going forward, HealthSteward's own adapted framework is named **NOTICE** — *Named contact, Opt-in channel, Task confirmation, Informal notify (not escalate), Completion by profile/category.* The rename from "escalate" to "notify" is deliberate: HealthSteward can only notify a chosen contact, never guarantee authoritative action the way PACT's escalation trigger implies. Use "NOTICE" in future docs/decisions/content describing this feature area rather than re-applying PACT's terms.

**Status:** Proposed. Not implemented. Filed as #139 (Care Circle core: contacts, scheduler, own-account SMTP — supersedes #25) and #140 (two-way email: IMAP opt-in polling, digest, one-click replies — depends on #139).

---

### DEC-033: The Eval Question-Count Floor Counts In-Scope Entities Only, and Fixtures Declare Condition Scope Themselves

**Date:** 2026-08-08

**Context:** Issue #75. `expected_min_questions()` (`eval/scorers.py`) scales the format-validity floor by `len(known_entities(case)) * 2`, floored at 3 and capped at 8 — DEC-018's fix for `cold_start` failing a flat 8-question bar with almost nothing to ask about. `cross_specialty_scope` kept failing anyway (6 questions against 8), and the issue asked which of two failure modes it was: a genuinely data-sparse fixture the scaling should cover, or a model under-delivering questions it could legitimately generate.

It is the first, and the reason was hidden by an entity count that looked healthy. `known_entities()` unions conditions + medications + lab orders with no scope filter, so `cross_specialty_scope` counts 4: Type 2 Diabetes Mellitus, Metformin, Mild Plaque Psoriasis, and Clobetasol Cream. `4 * 2 = 8`, so the case gets the *full* flat floor and no scale-down at all. But the last two are dermatology material on an endocrinology visit — precisely what the v3 prompt forbids the model from raising, and the entire reason this fixture exists. The case is as data-sparse *in scope* as `cold_start`; it just didn't look it. The model producing 6 questions is arguably correct behaviour being scored as a failure, the same tension with the anti-hallucination rules DEC-018 already recorded.

That also answers the issue's open question — yes, the count needs to be scope-aware — but only for the floor.

**Options Considered:**

| Option | Pros | Cons |
|--------|------|------|
| Narrow `known_entities()` itself to in-scope entities | One function, no new concept | Breaks its other caller. `score_groundedness()` needs *all* real entities: drop Clobetasol and a question about it scores as ungrounded — a hallucination — when it's a real entry in the patient's record that `score_scope()` already flags, correctly, as a scope violation. One failure would be counted twice under two names, and the scope checker's own signal would be destroyed |
| **Add `in_scope_entities()` for the floor; leave `known_entities()` scope-blind for groundedness** | Each scorer asks the question it actually means — "how much is there legitimately to ask about" vs. "did the model invent this" | Two similar-looking functions someone could reach for the wrong one of; mitigated by docstrings on both saying why the other exists |
| Derive condition scope from `icd_10` against `ICD10_SPECIALTY_MAP` | Reuses data already in the repo; scorer derives scope rather than being told it | That map is the hand-authored surface #72/#74 are mid-consolidation on. Building the eval harness's floor on it couples the harness to known debt and means a consolidation change silently moves eval thresholds |
| **Add an explicit `in_scope` flag to `ConditionFixture`** | The fixture already exists to encode a scope distinction; stating it is clarifying rather than redundant, and dependency-free | It is the fixture grading itself — a fixture author could mislabel and quietly lower the bar. Bounded: it only ever moves a floor, never a pass/fail verdict, and the pinned per-case floors make any change visible in a diff |
| Scope medications only, accept conditions are over-counted | No fixture change at all | Gives a floor of 6, which `cross_specialty_scope` still fails at 6 questions — doesn't resolve the case it was filed for |

**Decision:**
1. Add `in_scope_entities(case)` and have `expected_min_questions()` count it. `known_entities()` is unchanged and stays the input to `score_groundedness()`.
2. Scope each entity type the way it already encodes scope. **Medications:** compare the prescriber's specialty to the target doctor's via the same `are_specialties_related()` the runtime scope logic uses. A medication with no prescriber, or a prescriber with no specialty, counts as **in** scope — absence of a scope signal is not evidence of being off scope, and defaulting the other way would silently deflate the floor for any fixture that just didn't tag one. **Conditions:** an explicit `ConditionFixture.in_scope: bool = True`, set `False` only on `cross_specialty_scope`'s psoriasis. **Lab orders:** always counted.
3. Pin every case's resulting floor in `tests/test_eval_harness.py` (`EXPECTED_FLOORS`), with a companion test asserting every fixture case appears in that map, so a new case can't skip the check by omission.

**Consequences worth stating plainly:** `cross_specialty_scope`'s floor drops from 8 to 4, so format validity is close to vacuous for this one case — it mostly stops testing question *volume* there. That is arguably correct, since the interesting signal for this fixture is the scope checker rather than the count, but it is a real reduction in what the case checks and shouldn't be discovered later as a surprise. Separately, two of five cases now scale below the documented flat 8 (three, counting `groundedness_labs_vitals`, which was already at 6 before this change and is unaffected by it) — the exceptions are becoming the pattern, and whether 8 is still the right documented default is a question this DEC leaves open rather than answering. Filed as #154.

**Reasoning:** Splitting the two callers rather than mutating the shared one is the whole substance here: "what may this question reference" and "what should this question have covered" look like the same set and are not, and collapsing them costs the harness a distinct scorer. Fixture-declared condition scope over ICD-10 derivation because the harness's job is to be a trustworthy measuring stick — coupling it to a map that is actively being consolidated means eval thresholds move when unrelated work lands, which is exactly the property a measuring stick must not have. The self-grading objection is real but bounded, and pinned floors convert it from invisible to reviewable.

No prompt changed, so no version bump and no `PROMPT_CHANGELOG.md` entry.

**Status:** Implemented (#75).

---

### DEC-034: Visit-Prep History Lives in a Separate Append-Only Table, Read-Only, Unpruned

**Date:** 2026-08-08

**Context:** Issue #54, piece 2. `prepare_visit` (`src/api/visits.py`) reassigned `generated_questions`/`context_summary` on an existing `VisitPrep` in place, so one click on "Regenerate Questions" (`VisitPrep.tsx`) permanently destroyed whatever the previous run produced — including any hand-edits the patient had made to it under issue #14. Not a missing feature: silent, unrecoverable destruction of user content from a prominent button. Entry 56 (#46) had already deferred "the history table" as a substrate #12, #54 and #97 would each want, explicitly to avoid designing it three times. This decides its shape for the visit-prep case.

**Scope: piece 2 only.** #54 also asks for a review gate before first persistence (piece 1). That is a product decision #12 explicitly claims — it plans an append-only per-claim table that doubles as the review surface. Building an interim Save/Discard step now means building a review surface twice and deleting one, which is the throwaway work #12's own write-up warns against. Piece 2 needs no product decision, and an append-only version history is a prerequisite for #12's per-claim table rather than a competitor to it, so nothing built here is discarded when #12 lands. #54 stays open for piece 1.

**Options Considered:**

| Option | Pros | Cons |
|--------|------|------|
| Append rows to `visit_preps` itself, dropping the unique constraint on `appointment_id` | One table; history and current row are literally the same shape | `appointment_id` being unique is what makes "the current prep" a single `scalar_one_or_none()` in `visits.py`, `appointments.py` (checklist) and `profile_export.py`. Dropping it changes what `GET /api/visits/{id}/prep` *means* and every one of those callers becomes a latent "which row did I get?" bug |
| Add `previous_questions`/`previous_summary` columns to `visit_preps` | Smallest possible change; no new table | Keeps exactly one generation back. Two regenerations and the older one is destroyed anyway — the same bug with a longer fuse |
| **Separate `visit_prep_versions` table, written only by the regenerate path** | `visit_preps` keeps its shape, its constraint and every existing reader; history is unbounded; additive migration with nothing to backfill | Two places to look for prep content; a join to read history |
| Warn before overwriting instead of preserving | No schema change at all | The issue offers this as a *minimum*, and it protects nothing if the user clicks through — which is the case that produces the loss |

**Decision:**
1. **New `visit_prep_versions` table** (`visit_prep_id` FK, `version_number`, `generated_questions`, `context_summary`, `used_fallback`, `content_updated_at`, `created_at`). Written by one helper, `_snapshot_prep_version`, called immediately before the reassignment in `prepare_visit` — after `agent.prepare_visit()` returns, so a failed generation leaves the prep untouched and archives nothing.
2. **`version_number` is 1-based and monotonic per prep**, assigned `max(existing) + 1`, where version 1 is the *first content displaced* (i.e. the original generation). Not derived from a count on read, so the number stays stable if versions ever become individually deletable.
3. **Both timestamps kept.** `content_updated_at` (the displaced prep's `updated_at`) answers "when was this written"; `created_at` answers "when was it replaced". Keeping only one loses the other, and silently dropping a timestamp is the same class of loss this table exists to prevent.
4. **`used_fallback` is snapshotted per version.** Without it a real generation is indistinguishable from the hardcoded placeholder issue #47 produces when the backend is unreachable, which would make the history actively misleading rather than merely incomplete.
5. **Read-only history.** `GET /api/visits/{appointment_id}/prep/versions`, newest first, plus a collapsed "Previous versions (N)" disclosure in `VisitPrep.tsx`. No restore, no diff. Restore re-raises the same overwrite question one level up — does restoring clobber the current prep, or snapshot it too? — and the data-loss harm is gone once the old content is visible and copyable. Cheap to add later; hard to un-ship if the semantics are wrong.
6. **No retention policy; nothing is pruned.** Every regenerate keeps a row forever. At single-user scale that's a handful of small JSON blobs per appointment, and a pruning rule would silently delete exactly the content this table exists to protect.
7. **Empty content is not archived.** A prep row with neither questions nor a summary has nothing worth preserving, and a version row for it would put a "Previous versions (1)" affordance in front of the user that opens onto nothing.
8. **No backfill in the migration.** Generations overwritten before this table existed are gone; synthesising a "version 1" from current content would fabricate a history that never happened.
9. **PATCH (`/prep`, issue #14) does *not* create a version.** This issue is about regeneration destroying content silently, not about undoing the patient's own deliberate edits. Pinned by a test so the boundary is explicit rather than incidental. Note the snapshot still captures the *edited* state when a regenerate displaces it, which is the content that actually had value.
10. **Version history is included in profile export** (`EXPORT_FORMAT_VERSION` 1 → 2). Beyond the plan on the issue, and justified by the same reasoning as the table: an export that dropped history would re-introduce the loss at backup time. The bump is for an additive key, made anyway because only the version number distinguishes "no history was kept" from "this export predates history being kept".

**Verified not to break other readers:** the #110 pre-visit checklist reads `VisitPrep.generated_questions` via `scalar_one_or_none()` on `visit_preps` (`src/api/appointments.py`), and `profile_export.py` selects preps by `appointment_id`. Both keep working unchanged because `visit_preps` is untouched — which is the entire argument for option 3 over option 1.

**Reasoning:** The unique constraint on `appointment_id` is load-bearing in a way that isn't obvious from the model definition — it's what lets three separate modules treat "the prep for this appointment" as a single row without ordering or filtering. Storing history in place would trade a contained schema addition for a diffuse correctness risk across all of them. Read-only over restore, and unpruned over a retention policy, are the same instinct twice: this feature exists because content was being destroyed, so every ambiguous call resolves toward keeping more and doing less to it.

**Status:** Implemented (#54, piece 2). Piece 1 (review gate before first persistence) remains open on #54, pending #12.

---

### DEC-035: An Apply Never Reports a Change It Didn't Make — Unreadable Stop Dates Fall Back to the Visit Date, or Skip Visibly

**Date:** 2026-08-09

**Context:** `apply_items` handled a parsed AVS "medication stop" by writing `Medication.end_date = _parse_date_string(med.date)` (`src/api/documents.py`). `_parse_date_string` returns `None` for any string outside its four known formats (`%m/%d/%Y`, `%Y-%m-%d`, `%B %d, %Y`, `%B %d %Y`) — so `"last week"`, `"6/1/26"`, or a blank/garbled OCR date all produced `None`. `None` is exactly what an active medication's `end_date` already holds, so the write was a genuine no-op while the plan still reported `action: update`, `reason: "marks this medication stopped"`, and counted it under `medications_stopped`. The user was told a medication was recorded as stopped while the profile still listed it as active. Issue #149; surfaced by #143's pre-apply diff, which rendered it as `end_date: (empty) → (empty)` instead of hiding it in a silent write.

The narrow bug is one branch, but the policy question generalises to every field apply parses: what should `_build_apply_plan` do when a parsed value can't be interpreted? The de-facto answer was "write the null and report success", and that answer will be wrong the same way for the next date or numeric field added.

**Options Considered:**

| Option | Pros | Cons |
|--------|------|------|
| **Fall back to the visit date when it's readable, name the inference in the plan `reason`; skip visibly when it isn't** | The medication actually ends up stopped, which is what the document asserted; the visit date is the document's own anchor, already used by the `_is_newer` guard; the preview shows a real value change rather than `(empty) → (empty)`, so the inference is reviewable before it's committed | Stores a date the document never stated — a downstream reader of `end_date` alone can't tell an inferred date from a transcribed one |
| Always skip and flag, never infer a date | Nothing inferred is ever written to a medical record | Leaves the medication active in the profile when the document plainly says it was stopped — the profile stays wrong about something clinically load-bearing, which is the more consequential of the two errors |
| Widen `_parse_date_string` to accept more formats | Fixes the `"6/1/26"` class of input at the source | Doesn't fix the general case (`"last week"` has no reference point), and a permissive parser that quietly guesses wrong is a worse-hidden version of the same bug. Rejected as a substitute; a narrow format addition remains available later on its own merits |
| Leave it; treat the `(empty) → (empty)` preview row from #143 as sufficient warning | Zero change | Depends on the user reading a diff row that renders as no change at all, and the reported count still says a medication was stopped |

**Decision:** A medication stop resolves its `end_date` through one helper, `_stop_end_date(date_str, visit_dt)`, which returns `(date | None, reason)`:

- Parseable stop date → that date, with today's unchanged reason string.
- Unreadable or missing stop date, visit date readable → the visit date, with a reason that names both the problem and the substitution (e.g. `marks this medication stopped — stop date "last week" couldn't be read, using the visit date 2099-12-31`).
- Unreadable or missing stop date, visit date also unreadable → `action: skip` under the existing `medications_stopped` skip bucket, with a reason saying the stop couldn't be applied. No write, and the count no longer claims one.

The rule this generalises to, for future parsed fields: **an apply never reports a change it didn't make.** Prefer a visible approximation, named as an approximation, over a silent no-op; where no honest approximation exists, skip visibly rather than writing a value indistinguishable from "unset".

Deliberately **not** generalised to medication *creates*, which use the same `_parse_date_string(med.date)` for `start_date`. A null `start_date` on a new medication honestly reads as "start date unknown" — it isn't confusable with a different, wrong state the way a null `end_date` is confusable with "still active" — so creates keep today's behaviour, pinned by a test.

**Reasoning:** The two error directions are not symmetric. Writing the visit date is wrong by however far the real stop date was from the visit — usually days, and the document itself is the closest anchor available. Writing nothing is wrong about whether the patient is on the medication at all, which is the fact downstream care decisions actually read. Since #143 the inference is also reviewable before it commits: the preview shows the substituted date and the reason that explains it, so the user can reject a fallback they disagree with instead of discovering it later. Both alternatives the issue itself offered (reject-and-flag, or fall back to a sensible default) were acceptable to the reporter; this takes the fallback where one exists and the rejection where one doesn't, so neither case ends in a silent no-op.

**Status:** Implemented. Tests in `tests/test_documents_apply.py` cover: unreadable, malformed, empty and absent stop dates all falling back to the visit date; the preview naming the inference and showing a real `end_date` change; the no-visit-date case skipping rather than counting; and medication creates still accepting an unreadable `start_date` unchanged.

---

*Last updated: 2026-08-09*
