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

**Status:** Approved — ready for implementation planning

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

**Status:** Decided (simple phase implemented)

*Last updated: 2026-07-05*
