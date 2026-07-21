# HealthSteward Development Chat History

This document captures the complete development conversation for the HealthSteward project, including questions, answers, options discussed, and decisions made.

**Last Updated:** 2026-07-06

---

## Table of Contents

1. [Project Kickoff](#1-project-kickoff)
2. [Phase 1 Planning](#2-phase-1-planning)
3. [Implementation Discussion](#3-implementation-discussion)
4. [Documentation Requests](#4-documentation-requests)
5. [Frontend Discussion](#5-frontend-discussion)
6. [Multi-User Architecture (DEC-001)](#6-multi-user-architecture-dec-001)
7. [PDF Processing Discussion (DEC-005)](#7-pdf-processing-discussion-dec-005)
8. [Privacy and Anonymization (DEC-006)](#8-privacy-and-anonymization-dec-006)
9. [Visit Notes Structure (DEC-008)](#9-visit-notes-structure-dec-008)
10. [Intelligent Context Selection](#10-intelligent-context-selection)
11. [AVS PDF Parser Integration (DEC-010)](#11-avs-pdf-parser-integration-dec-010)
12. [Specialty-Aware Visit Prep (DEC-011)](#12-specialty-aware-visit-prep-dec-011)
11. [Implementation Summary](#11-implementation-summary)
16. [Pluggable LLM Backend + Agentic Tool-Use (DEC-013)](#16-pluggable-llm-backend--agentic-tool-use-dec-013)

---

## 1. Project Kickoff

### Initial State

**User:** The basic environment is set up. `http://localhost:8000/health` shows the API running with database and AI agent "not_configured". Asked to start building the project based on the plan in README.md.

**Assistant:** Reviewed the README and existing codebase structure. Found FastAPI running, Docker services configured, and all dependencies installed, but the entire business logic layer was empty scaffolding.

The README outlined the build order:
1. Health data schema in `src/data/`
2. Claude agent in `src/agents/`
3. API endpoints for doctor visit prep
4. Interview system
5. Calendar integration
6. Training data collection

---

## 2. Phase 1 Planning

### Planning Questions

Before designing the implementation plan, the assistant asked:

**Question 1: Scope for Phase 1**
- Focus on local-first development
- Skip Docker complexity for now
- Use SQLite instead of PostgreSQL

**Question 2: Build Approach**
- User confirmed preference for iterative approach with testable steps

### Phase 1 Plan Overview

**Goal:** Build the first vertical slice - health data entry + AI-powered doctor visit preparation using Claude API.

**Build Order (9 steps):**

| Step | Component | Description |
|------|-----------|-------------|
| 0 | Dependencies | Add aiosqlite, alembic; update anthropic pin |
| 1 | Config + Logging | Pydantic Settings, loguru setup |
| 2 | Database | Async SQLAlchemy engine, 7 ORM models |
| 3 | Migrations | Alembic setup with async support |
| 4 | Schemas | Pydantic Create/Update/Response schemas |
| 5 | API Routes | CRUD for profiles, conditions, medications, doctors, appointments, visits |
| 6 | Claude Agent | BaseAgent + VisitPrepAgent |
| 7 | Wire main.py | Add lifespan, routers, health check |
| 8 | Tests | conftest, CRUD tests, visit prep tests |
| 9 | Update .env | SQLite default, Phase 2+ sections commented |

### Key Design Decisions from Planning

- **UUIDs as primary keys** - Privacy-friendly, portable across databases
- **Async everywhere** - aiosqlite driver, AsyncAnthropic, async route handlers
- **Separation of models** - `src/models/` for Pydantic schemas, `src/data/` for ORM models
- **Conversation logging** - Every Claude call logged with token counts for future distillation
- **Profile-nested routes** - `/api/profiles/{id}/conditions/` naturally enforces ownership

---

## 3. Implementation Discussion

### Implementation Completed

The Phase 1 implementation was completed with:

**Backend (16 new files):**
- Configuration and utilities
- Database layer with 7 ORM models:
  - HealthProfile
  - Condition
  - Medication
  - Doctor
  - Appointment
  - VisitPrep
  - ConversationLog
- Full CRUD API routes
- Claude agent integration

**Tests:** 15 tests all passing

**Verification:**
- Server responds at `/health` with `{"database": "connected", "ai_agent": "not_configured"}`
- Database tables created via Alembic migration

---

## 4. Documentation Requests

### Request 1: Implementation Details

**User:** "Can we maintain these implementation details summary in a file as we go along so that I can refer to it later to make sense of the project?"

**Action:** Created `docs/notes/IMPLEMENTATION.md` with:
- Project overview and tech stack
- Phase 1 summary with all files created
- Architecture diagrams showing request flow
- Component deep dives
- API reference
- Testing strategy
- Future phases placeholder
- Common tasks guides

### Request 2: Usage Instructions

**User:** "Can you also add these instructions to a file as we go along so that I know how to use the tool?"

**Action:** Created `docs/notes/USAGE.md` with:
- Starting instructions
- First-time setup
- Step-by-step usage guide
- API examples
- Troubleshooting
- File locations reference

---

## 5. Frontend Discussion

### UI Options Presented

**User:** "Yes, I would like a demo. But first, can we not do all of this via the UI?"

**Response:** Explained two options:

| Option | Pros | Cons |
|--------|------|------|
| **Swagger UI** (`/docs`) | Already available, interactive | Basic styling |
| **Build a Frontend** | Polished experience | More work |

**Frontend Options:**

| Option | Pros | Cons |
|--------|------|------|
| **Streamlit** | Fastest to build, great for demos | Separate app, less polished |
| **Simple HTML/JS** | Single page, no build step | Basic styling |
| **React + Tailwind** | Modern, polished | More setup, separate dev server |

### User's Choice

**User:** "I prefer the react + tailwind option. Would you recommend it?"

**Response:** Recommended React + Tailwind if:
- Building this as a real product
- Want polished experience for health data entry
- Comfortable with or want to learn JS/React

**Follow-up Questions:**
1. Package manager preference? → pnpm
2. Inside this repo or separate? → `frontend/` folder (monorepo)
3. UI preferences? → Minimal/clean design

**User:** "Yes, proceed with that for now"

### Frontend Implementation

Created complete React frontend with:
- Vite + React 19 + TypeScript + Tailwind CSS 4
- TanStack Query for server state
- React Router 7 for navigation
- Components: Layout, Button, Card, Input, Modal
- Pages: ProfileList, ProfileDetail, VisitPrep

**Demo Flow:**
1. Create a profile - Enter name and health details
2. Add health data - Conditions, medications, doctors via tabs
3. Schedule appointment - Pick doctor and date
4. Generate AI questions - Click "Prepare Visit"

---

## 6. Multi-User Architecture (DEC-001)

### The Question

**User:** "How can I turn this into something that my family can use together - like a shared medical digital vault of sorts that any member with access can view, edit, etc?"

### Options Presented

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| **Quick & Simple** | Deploy to server, no auth | Fast, no login | Anyone with URL can access |
| **Full Multi-User** | Add auth + family groups | Proper security, accountable | More work |
| **Simple Shared Password** | Basic HTTP authentication | Some security | Can't track who did what |

### Deployment Options

| Where | Cost | Complexity |
|-------|------|------------|
| **Raspberry Pi at home** | ~$50 one-time | Medium |
| **VPS (DigitalOcean)** | ~$5-10/month | Low |
| **Fly.io / Railway** | Free tier available | Low |
| **Your own server** | Varies | Medium |

### Architecture Diagram for Full Multi-User

```
┌─────────────────────────────────────────────────────┐
│                     Vercel                          │
│                  (React Frontend)                   │
└─────────────────────┬───────────────────────────────┘
                      │ API calls
                      ▼
┌─────────────────────────────────────────────────────┐
│                     Fly.io                          │
│                (FastAPI Backend)                    │
│                                                     │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐ │
│  │   Clerk     │  │  PostgreSQL │  │   Claude    │ │
│  │   (Auth)    │  │    (Data)   │  │   (AI)      │ │
│  └─────────────┘  └─────────────┘  └─────────────┘ │
└─────────────────────────────────────────────────────┘
```

### Privacy Concerns Raised

**User:** "Help me think this through first - I don't want data leaking at any point which is my biggest worry with deployment. Next, do I have to worry about HIPAA and other stuff if we move away from local deployment?"

### HIPAA Analysis

**Short answer:** Probably doesn't apply.

HIPAA applies to:
- Healthcare providers (doctors, hospitals)
- Health insurance companies
- Their business associates

HIPAA does **NOT** apply to:
- Personal health tracking apps you build for yourself
- Family health records you maintain privately
- Apps not connected to healthcare providers

**But:** Even without HIPAA, health data should be treated with care.

### Data Leakage Points

| Where | Risk | Mitigation |
|-------|------|------------|
| **Database at rest** | Server/disk access | Encrypt database |
| **Data in transit** | Man-in-the-middle | HTTPS everywhere |
| **Backups** | Backup file stolen | Encrypt backups |
| **Logs** | Health data in logs | Don't log PII |
| **Auth provider** | They see email/name | They don't see health data |
| **Hosting provider** | Admin access | Use encrypted volumes |
| **Claude API** | Health data sent | **Biggest concern** |

### Claude API Privacy Options

| Option | Privacy | Effort | AI Quality |
|--------|---------|--------|------------|
| **Accept Anthropic's terms** | Medium | None | Best |
| **Anonymize before sending** | High | Low | Good |
| **Self-host LLM (Ollama)** | Maximum | Medium | Decent |
| **No AI features** | Maximum | None | N/A |

### Deployment Privacy Spectrum

**Tier 1: Maximum Privacy (Self-Hosted)**
- Raspberry Pi / Home Server
- All data stays in your home
- No third parties
- Trade-off: Harder remote access

**Tier 2: High Privacy (Encrypted VPS)**
- Hetzner / OVH (European, privacy-focused)
- Encrypted disk (you hold keys)
- Provider can't read data
- Trade-off: Trusting infrastructure

**Tier 3: Moderate Privacy (US Cloud)**
- Fly.io / Railway / DigitalOcean
- Data encrypted in transit + at rest
- Convenient, well-managed
- Trade-off: US jurisdiction, provider access possible

### Recommendation

For a **family health vault** with maximum practical privacy:
1. Self-host on Raspberry Pi or home NAS
2. Access via Tailscale (encrypted tunnel)
3. Use Ollama with Llama 3 for AI (local)
4. Skip third-party auth (simple family password)

### Decision Outcome

**User:** "Let's hold off on this train of thought for now... the reason is I want to consult my partner before deciding if/which route to go with."

**Status:** Deferred (DEC-001)

---

## 7. PDF Processing Discussion (DEC-005)

### The Question

**User:** "I often get after visit notes via portal (downloadable as PDFs). How can we process this data and add what is new and relevant to a user's continued medical records?"

### Processing Flow Diagram

```
Upload PDF
    │
    ▼
┌─────────────────────────────────────┐
│ 1. Extract text from PDF            │
│    (pdfplumber or Claude Vision)    │
└─────────────────┬───────────────────┘
                  │
                  ▼
┌─────────────────────────────────────┐
│ 2. LLM extracts structured data     │
│    - New diagnoses                  │
│    - Medication changes             │
│    - Vitals / lab results           │
│    - Follow-up instructions         │
└─────────────────┬───────────────────┘
                  │
                  ▼
┌─────────────────────────────────────┐
│ 3. Compare with existing profile    │
│    - What's new?                    │
│    - What changed?                  │
└─────────────────┬───────────────────┘
                  │
                  ▼
┌─────────────────────────────────────┐
│ 4. User reviews & confirms          │
│    "Add Lisinopril 10mg? [Yes/No]"  │
└─────────────────┬───────────────────┘
                  │
                  ▼
┌─────────────────────────────────────┐
│ 5. Update profile + store PDF       │
└─────────────────────────────────────┘
```

### PDF Text Extraction Options

| Method | Best For | Privacy | Notes |
|--------|----------|---------|-------|
| **pdfplumber** | Text-based PDFs | Local | Fast, reliable |
| **Claude Vision** | Scanned/image PDFs | Sends to Anthropic | Best accuracy |
| **Tesseract OCR** | Scanned PDFs | Local | Free, self-hosted |
| **pdf2image + local LLM** | Maximum privacy | Local | More setup |

### PDF Storage Options

| Option | Privacy | Cost | Scalability |
|--------|---------|------|-------------|
| **Local encrypted folder** | Maximum | Free | Limited |
| **Self-hosted MinIO** | Maximum | Self-managed | Good |
| **Backblaze B2 + encryption** | High | $0.005/GB | Excellent |
| **Encrypted S3** | Medium-High | $0.023/GB | Excellent |
| **Supabase Storage** | Medium | Free tier | Good |

### Recommended Approach

Client-side encryption:
```
PDF → Encrypt locally → Upload encrypted blob → Store
                ↓
         Key stays with you (never uploaded)
```

### What This Would Enable

- Upload after-visit PDF
- See extracted items: "Found 2 new items:"
  - New medication: Lisinopril 10mg daily
  - Updated diagnosis: Hypertension
- Click "Add to Profile" for each
- Original PDF archived and searchable

### Decision Outcome

**Status:** Deferred for Phase 3, dependent on DEC-001 (deployment decision)

---

## 8. Privacy and Anonymization (DEC-006)

### The Question

**User:** "Do we have guardrails in place so that no PII or sensitive data is leaked in the Claude API call? Also, is Claude API the best one to use for this use case?"

### Current State (Honest Assessment)

**Answer:** No guardrails currently exist. The `_build_context` method in visit_prep.py sends:
- Patient name (PII)
- Date of birth (PII)
- Doctor names (could be sensitive)
- Full medical conditions and medications

### Data Anonymization Analysis

| Field | Current | Risk Level | Anonymize To |
|-------|---------|------------|--------------|
| `profile.name` | "John Doe" | **High** | "Patient" |
| `profile.date_of_birth` | "1985-06-15" | **High** | Age (e.g., "39 years old") |
| `profile.emergency_contact_*` | Contact info | Medium | Remove entirely |
| `doctor.name` | "Dr. Sarah Johnson" | Medium | "your [specialty]" |
| `doctor.phone/email` | Contact info | Medium | Remove entirely |
| `doctor.clinic` | "City Medical Center" | Low | Keep |
| `medication.prescribing_doctor` | "Dr. Smith" | Medium | "Prescribing physician" |
| `appointment.notes` | Free text | **Varies** | Scan for PII |

### Anonymization Options

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| **A. Simple Replace** | Deterministic replacement | Simple, testable | Might miss PII in notes |
| **B. Tokenization** | Replace with tokens, restore later | Can restore names | Complex, might confuse LLM |
| **C. Regex Scrubbing** | Scan for patterns | Catches phones/emails | False positives possible |
| **D. Hybrid** | Combine structured + regex | Best coverage | More work |

**User Decision:** Go with Option D (Hybrid)
- Structured fields: Simple replace
- Free-text fields: Regex scan + NER

### LLM Provider Comparison

| Option | Quality | Privacy | Cost |
|--------|---------|---------|------|
| **Claude API** | Excellent | Medium | ~$0.01/call |
| **OpenAI GPT-4** | Excellent | Medium | ~$0.01/call |
| **Google Gemini** | Good | Medium | Free tier |
| **Ollama (local)** | Good | Maximum | Free |

**User Decision:** Support both Claude + Anonymization AND Ollama (local)

### ConversationLog Discussion

**Question:** What to log in the ConversationLog table?

| Option | What's Logged | Pros | Cons |
|--------|---------------|------|------|
| **Log anonymized** | "Patient, 39..." | Privacy-safe | Less useful for training |
| **Log original** | "John Doe, 39..." | Better training data | PII in database |
| **Log both** | Both versions | Flexible | More storage, PII risk |
| **Don't log** | Nothing | Simplest, safest | Lose training capability |

**User Decision:** Log anonymized only

### Final Anonymization Decisions

| Item | Decision |
|------|----------|
| Patient name | → "Patient" |
| DOB | → Exact age (e.g., "39 years old") |
| Doctor name | → "your [specialty]" or "Doctor" |
| Doctor clinic | Keep as-is |
| Prescribing doctor | → "Prescribing physician" |
| Contact info | Remove entirely |
| Free-text fields | Regex + NER scanning |
| ConversationLog | Log anonymized only |

---

## 9. Visit Notes Structure (DEC-008)

### Clarification Needed

**User:** "Your appointment.notes were meant to be patient notes for appointment prep. I thought they were for quick user-entered notes for during/after the appointment. Can we add that feature right now?"

### Two Types of Notes

| Type | When | Example |
|------|------|---------|
| **Prep notes** | Before visit | "Bring blood sugar logs", "Ask about headaches" |
| **Visit notes** | During/after visit | "Doctor said increase Metformin", "Follow up in 3 months" |

### UI Flow Diagram

```
Appointment Card (before visit):
┌─────────────────────────────────────────┐
│ Dr. Johnson - Endocrinology             │
│ March 15, 2025 at 10:00 AM              │
│                                         │
│ Purpose: Quarterly diabetes checkup     │
│                                         │
│ Prep Notes:                             │
│ ┌─────────────────────────────────────┐ │
│ │ Bring blood sugar logs              │ │
│ │ Ask about fatigue                   │ │
│ └─────────────────────────────────────┘ │
│                                         │
│ [Prepare Visit]  [Add Visit Notes]      │
└─────────────────────────────────────────┘

After clicking "Add Visit Notes":
┌─────────────────────────────────────────┐
│ Visit Notes:                            │
│ ┌─────────────────────────────────────┐ │
│ │ - Increase Metformin to 1000mg      │ │
│ │ - Schedule blood panel              │ │
│ │ - Follow up in 3 months             │ │
│ └─────────────────────────────────────┘ │
│                                         │
│ [Save]                                  │
└─────────────────────────────────────────┘
```

### Questions Answered

1. **Should visit notes be editable after the appointment?** → Yes
2. **Track when notes were added/updated?** → Yes (`visit_notes_updated_at`)
3. **Migrate existing notes data?** → No, start fresh (no data in system yet)

### Using Visit Notes for Future Prep

**User:** "I want last visit notes to be used to prepare prep_notes for the upcoming appointment, along with other details."

**Improved Flow:**
- Current conditions and medications
- This appointment's purpose
- **Last visit notes with same doctor**
- **Visit notes from other appointments since last same-doctor visit**

---

## 10. Intelligent Context Selection

### The Problem

**User:** "Is there a way to identify which visits might be relevant based on doctor specialty + always including notes from PCP visits? Sometimes different specialties tie in together for overall care and they matter. But sometimes some are very irrelevant, so no point in wasting tokens."

### Options Presented

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| **1. Specialty Mapping** | Hardcode related specialties | Fast, free, deterministic | Might miss connections |
| **2. Multi-Agent** | Agent 1 filters, Agent 2 generates | Smart, context-aware | Extra LLM call cost |
| **3. RAG** | Vector search on visit notes | Semantic relevance | Requires ChromaDB setup |
| **4. Hybrid** | Rules + summarization | Practical, implementable now | Rules need maintenance |
| **5. Local LLM Pre-Filter** | Use Ollama for relevance scoring | Free, private filtering | Requires Ollama |

**User Decision:** Combine Options 4 (Hybrid) and 5 (Local LLM Pre-Filter)

### 4-Stage Context Selection Flow

```
All visits since last same-doctor appointment
                    │
                    ▼
┌─────────────────────────────────────────────────────────┐
│  STAGE 1: Rules-Based Filter (instant, free)            │
│                                                         │
│  ✓ Include: Same doctor's last visit                   │
│  ✓ Include: All PCP/Internal Medicine visits           │
│  ✓ Include: Related specialties (mapping)              │
│  ✗ Exclude: Doctors with "exclude_from_prep" flag      │
└─────────────────────────────────────────────────────────┘
                    │
                    ▼
          Remaining visits > 5?
                    │
           Yes ─────┴───── No
            │               │
            ▼               │
┌───────────────────────────┐               │
│  STAGE 2: Local LLM       │               │
│  Relevance Scoring        │               │
│  (Ollama - private, free) │               │
│                           │               │
│  "Rate 1-10: How relevant │               │
│  is this visit?"          │               │
│                           │               │
│  Keep score >= 7          │               │
└───────────────────────────┘               │
            │                               │
            └───────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────┐
│  STAGE 3: Token Budget Check                            │
│                                                         │
│  If total tokens > MAX_CONTEXT:                         │
│    - Keep recent visits in full                         │
│    - Summarize older visits to 1-2 sentences            │
└─────────────────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────┐
│  STAGE 4: Anonymize + Send to Main LLM                  │
│  (Claude or Ollama based on user preference)            │
└─────────────────────────────────────────────────────────┘
```

### Specialty Mapping

| Specialty | Related To |
|-----------|------------|
| **Primary Care** | All specialties |
| **Internal Medicine** | All specialties |
| **Endocrinology** | Cardiology, Nephrology, Ophthalmology, Podiatry, Neurology |
| **Cardiology** | Endocrinology, Nephrology, Pulmonology, Vascular Surgery |
| **Oncology** | All specialties |
| **Nephrology** | Cardiology, Endocrinology, Urology |
| **Neurology** | Psychiatry, Pain Management |
| **Orthopedics** | Physical Therapy, Rheumatology, Pain Management |
| **Gastroenterology** | Hepatology, Oncology, Nutrition |
| **Pulmonology** | Cardiology, Allergy, Sleep Medicine |

### Sensitive Specialties Handling

**User Decision:** Add "Exclude from Prep Context" flag on Doctor model

This allows users to mark sensitive doctors (e.g., psychiatry), and their visit notes won't be shared with other doctors' prep.

### Configuration Decisions

| Setting | Value |
|---------|-------|
| Stage 2 threshold | > 5 visits triggers LLM filtering |
| Relevance score cutoff | >= 7 |
| Summarization | Use same local LLM |
| Fallback if Ollama unavailable | Skip Stage 2, use rules + truncation |

---

## 11. Implementation Summary

### Commit Made

**Message:** "Add Phase 1: Health Profile + Visit Prep with React UI"

**User explicitly rejected:**
- Long commit messages with descriptions
- Co-Authored-By line

### Final Implementation

After all discussions, the following was implemented:

**Database Model Updates:**
- Doctor: Added `exclude_from_prep_context` flag
- Appointment: Renamed `notes` to `prep_notes`, added `visit_notes` and `visit_notes_updated_at`

**New Modules:**
- `src/utils/anonymization.py` - PII detection and anonymization
- `src/utils/context_selection.py` - 4-stage context selection
- `src/agents/ollama_client.py` - Local LLM support

**Updated Modules:**
- `src/agents/visit_prep.py` - Complete rewrite with anonymization
- `src/agents/base.py` - Logs only anonymized content
- `src/config.py` - Added Ollama and anonymization settings

**Frontend Updates:**
- Visit notes section for completed appointments
- "Mark as Completed" button
- "Exclude from prep context" checkbox on doctor form

**Tests:** 55 tests passing
- 19 tests for anonymization
- 21 tests for context selection
- Existing CRUD and visit prep tests

---

## Decision Summary Table

| ID | Topic | Status | Outcome |
|----|-------|--------|---------|
| DEC-001 | Multi-User Family Sharing | Deferred | Pending partner discussion |
| DEC-002 | Frontend Framework | Decided | React + Tailwind |
| DEC-003 | Database Choice | Decided | SQLite now, PostgreSQL for multi-user |
| DEC-004 | UUID Primary Keys | Decided | Yes, for privacy |
| DEC-005 | PDF Processing | Deferred | Phase 3, combined with action items |
| DEC-006 | PII Anonymization | Implemented | Regex + NER, log anonymized only |
| DEC-007 | Action Items Extraction | Planned | Phase 3 combined with PDF |
| DEC-008 | Visit Notes + Context Selection | Implemented | 4-stage hybrid approach |
| DEC-009 | Agentic Visit Prep Architecture | Approved | Claude API native tool use |
| DEC-010 | AVS PDF Parser Integration | Implemented | Local Ollama section-routing parser |
| DEC-011 | Specialty-Aware Visit Prep | Implemented | ICD-10 specialty tags, specialty-focused prompt |
| DEC-012 | Patient Disengagement / Action Items | **Complete** | Post-AVS panel, overview section, snooze/completion, UX polish |

---

## 12. AVS PDF Parser Integration (DEC-010)

### Context

The sandbox experiment (SB-001, `avs-pdf-parser`) successfully demonstrated parsing after-visit summary PDFs into structured medical data using a section-routing architecture. This session integrated that sandbox code into HealthSteward as a full feature.

### What Was Built

**Phase 1 — Parser Module (`src/parsers/`):**
- Ported sandbox code into a proper Python package
- `SectionRouter` processes each AVS section with the best strategy: deterministic for structured sections (patient info, med changes, follow-ups, appointments), LLM for unstructured (vitals, lab orders, notes, referrals)
- All LLM calls go through local Ollama only — safety check blocks non-localhost URLs
- Uses `pdfplumber` for text extraction

**Phase 2 — New Database Models:**
- `Document` — uploaded PDF metadata + parse status + cached parse result (JSON)
- `Vitals` — weight, BMI, blood pressure, heart rate, temperature (linked to Document)
- `LabOrder` — test name, ordered date, status
- `Referral` — specialty, provider, reason, status
- `FollowUp` — description, timeframe, target date, status
- `Condition` gained `icd_10` column for ICD-10-CM codes

**Phase 3 — Backend API (`src/api/documents.py`):**
- `GET /documents/scan` — scan `data/avs/` directory, return PDF files with processing status
- `POST /documents/parse-file` — create Document record for a scanned file
- `GET /documents/{id}/parsed` — trigger parse (or return cached), runs via `run_in_executor`
- `POST /documents/{id}/apply` — apply user-selected items to profile (deduplicates conditions, starts/stops medications, creates vitals/lab orders/referrals/follow-ups)

**Phase 4 — Frontend:**
- Documents tab (6th tab) in ProfileDetail
- Scan-folder UI — shows PDFs from `data/avs/`, new files highlighted at top
- `DocumentCard` component — file row with status badge (New/pending/completed/failed) and Parse/Review buttons
- `ParsedItemsReview` component — checkboxes per extracted item, section select all/deselect, action badges (START/STOP/CHANGED), ICD-10 badges, confirm button
- Polling spinner while parse runs (3s interval)

**Refactor — Scan-folder pattern (same session):**
- Removed file upload in favor of scanning `data/avs/` directory
- User drops AVS PDFs into `data/avs/`, app lists them with processing status
- No file duplication — backend reads PDFs in place
- Removed `FileUpload` component and `python-multipart` dependency

### User Flow

```
Drop PDF in data/avs/ → Open Documents tab
     ↓
App scans folder → Shows new files with "New" badge
     ↓
Click "Parse" → Creates Document record + Ollama extracts structured data
     ↓
Review screen → Checkboxes for each extracted item by category
     ↓
Click "Confirm" → Selected items applied to profile
     ↓
Profile updated with new conditions, meds, vitals, lab orders, referrals, follow-ups
```

---

## 12. Specialty-Aware Visit Prep (DEC-011)

**Date:** 2026-02-15

### Problem

Visit prep was generating irrelevant questions. For example, asking a cardiologist about dermatology medications (topical creams). Meanwhile, useful cross-specialty context was being missed — the interconnection between related conditions across specialties, plus lab results and vitals trends.

### Root Causes

1. System prompt was generic — "Generate 5-10 questions" with no specialty guidance
2. All medications dumped into context without indicating which specialty prescribed them
3. No lab orders, vitals, follow-ups, or referrals included in context
4. No ICD-10 to specialty mapping to help LLM understand condition relevance
5. Doctor specialty field was null (populated from AVS without specialty), but clinic name contained it

### Changes Made

- **Specialty-focused system prompt** — explicitly tells LLM to focus on this specialty, avoid unrelated meds
- **ICD-10 → specialty tags** on conditions (e.g., E11→Endocrinology, I10→Cardiology, L40→Dermatology)
- **Medication prescriber tags** — `[prescribed for Dermatology]` when we can match prescribing doctor
- **Clinical data sections** — lab orders, vitals trend, pending follow-ups, active referrals
- **Clinic-name specialty inference** — e.g., "Valley Cardiology Associates" → Cardiology when doctor.specialty is null
- **Expanded specialty mapping** — Gynecology ↔ Endocrinology bidirectional relevance
- **Merged feature/avs-pdf-parser-integration into main**

### Result

Visit prep now generates questions relevant to the target specialty — lab results, condition management, vitals trends — with no mention of unrelated medications from other specialists.

---

## 13. Patient Disengagement & Action Items (DEC-012)

**Date:** 2026-07-05

### Problem Identified

HealthSteward assumes an engaged patient. The system was great at storing what the doctor ordered (follow-ups, lab orders, referrals) but never reminded the patient to act on them. The data existed but was invisible unless the patient actively navigated to it.

### Discussion

**User:** Proposed a specific nudge model: after an AVS is uploaded, detect ordered tests and future appointments to be scheduled, and nudge the patient contextually — book a follow-up immediately if timeframe is short, remind about labs 1-2 weeks before an upcoming appointment, repeat nudges with snooze/action-completed buttons.

**What the system was missing:**
- No proactive surfacing of pending follow-ups, lab orders, referrals
- No API endpoints to query these records (they were stored but never exposed)
- No moment in the UX where the patient was told "here's what you need to do next"

### Complexity Assessment

| Feature | Complexity | Reason |
|---------|------------|--------|
| Post-AVS action panel | Simple | Fires at moment of engagement, logic on existing data |
| Overview "Needs Attention" section | Simple | Query existing records, no new schema |
| Backend API for follow-ups/lab orders/referrals | Simple | Response schemas existed, just no router |
| Snooze / action-completed buttons | Medium | New nudge state model + migrations |
| Scheduled/repeated nudges | Medium | Requires APScheduler or cron |
| 6-month lookahead from free-text timeframe | Medium | Timeframe is free text, needs parsing |

### Decision

Implement the simple ones first (DEC-012):
1. New API endpoints: `GET/PATCH /follow-ups`, `/lab-orders`, `/referrals`
2. Post-AVS action panel shown after apply completes
3. Overview tab "Needs Attention" section

Snooze/action-completed loop and scheduled notifications deferred.

**Second iteration — remaining simple tasks:**

- **Auto-refresh scan folder** — `refetchInterval: 30_000` on the scannedFiles query; new files dropped in `data/avs/` appear automatically without manual refresh. Small "auto-refreshes every 30s" label added to Documents tab header.
- **Appointment-driven nudge** — banner on the Appointments tab when there are upcoming appointments within 30 days AND unprocessed files sitting in `data/avs/`. Prompts the patient to parse them before their visit. Pure frontend logic using already-available data (appointmentList + scannedFiles).
- **Visit prep nudge** — "Needs Attention" section on Overview now includes upcoming appointments (within 30 days) that have no visit prep generated. Backend endpoint `GET /upcoming-without-prep` does the join efficiently. "Prepare" button links directly to the prep page; the nudge disappears as soon as prep is generated.

**Third iteration — final simple tasks:**

- **Longitudinal vitals alerts** — backend endpoint `GET /vitals-alerts` computes meaningful trends across all parsed vitals: weight change ≥5 lbs, BMI change ≥1.5, systolic BP change ≥10 mmHg, heart rate change ≥10 bpm. Surfaced in "Needs Attention" with oldest→newest values and visit count.
- **Follow-up and referral aging** — follow-ups now show urgency escalation (approaching/overdue) based on timeframe elapsed since creation. Referrals show a staleness warning after 60 days pending. Lab orders show age warning after 21 days.
- **Completed appointments without AVS** — backend endpoint `GET /completed-without-avs` finds completed appointments with no parsed document within 14 days of the visit date. Surfaced with a prompt to drop the PDF in `data/avs/`.
- **Past-due appointments not marked complete** — pure frontend logic: scheduled appointments whose date has passed. Prompts patient to add visit notes and mark complete, which feeds future visit prep quality.

### Architecture Notes

- The localhost safety check on Ollama (`_check_localhost`) means the nudge logic must stay on the local machine — no external notification service can be called with raw medical data
- `FollowUp.timeframe` is free text — nudge logic uses heuristic parsing (look for month/week numbers)
- Post-AVS nudges fire at the highest-engagement moment: right after the patient has just reviewed and confirmed their parsed document

---

## 14. Snooze and Completion State (DEC-012 Medium Phase)

**Date:** 2026-07-05

**Context:** After implementing the simple action items phase, the "Needs Attention" section had no memory — completed items would re-appear on next refresh, and there was no way to acknowledge a nudge without acting on it. This made the section feel noisy and untrustworthy over time.

**What was implemented:**

**Backend:**
- Added `snoozed_until` (DateTime, nullable) and `completed_at` (DateTime, nullable) columns to `FollowUp`, `LabOrder`, and `Referral` via Alembic migration
- New `NudgeState` table — stores `(profile_id, nudge_type, item_id, snoozed_until)` for computed nudges (upcoming-without-prep, past-due appointments, completed-without-avs, vitals alerts) that have no persistent row to attach state to. Upserted via `POST /nudge-states`
- List endpoints (follow-ups, lab-orders, referrals) now filter out completed and actively-snoozed items by default when no explicit status filter is passed — the backend handles it, frontend no longer needs to pass `?status=pending`
- PATCH endpoints now accept `snoozed_until` (ISO datetime string) in addition to `status`; auto-stamp `completed_at` when status transitions to a completed value
- Computed endpoints (upcoming-without-prep, vitals-alerts, completed-without-avs) query `NudgeState` and exclude matching snoozed items

**Frontend:**
- All action items in `ActionItemsSection` and `PostAvsActionPanel` now have a "Snooze 1w" secondary button alongside the existing primary action button
- Snooze sets `snoozed_until` to 7 days from now; the item disappears immediately (query invalidation) and re-surfaces after the snooze period expires
- Past-due appointments moved to a server-side endpoint (`GET /past-due-appointments`) that checks `NudgeState`, so snooze survives page refresh — consistent with all other computed nudges
- A shared `ActionButtons` component was extracted to avoid repeating the two-button pattern across all item types

**Key design decisions:**
- Snooze is always time-limited (1 week) — no permanent dismiss. Items re-surface after the snooze expires, keeping the feedback loop intact
- `completed_at` is a permanent timestamp so we could show completion history in a future phase

---

| Phase | Feature | Status |
|-------|---------|--------|
| Phase 1 | Health Profile + Visit Prep | Complete |
| Phase 2 | Multi-user / Family sharing | Pending DEC-001 |
| Phase 3 | PDF processing + Action items | **Complete** (DEC-010, DEC-012) |
| Phase 4 | RAG for health documents | Planned |
| Phase 5 | Medication reminders | Planned |
| Phase 6 | Local model distillation | Planned |

---

## 15. Snooze UX Polish (DEC-012 UX Polish Phase)

**Date:** 2026-07-05

**Context:** After merging the snooze/completion state branch, three minor UX gaps were identified: no way to see what had been resolved (items just disappeared), no indication when an item resurfaced after a snooze, and a fixed 1-week snooze that was too short for longer-horizon items like referrals.

**What was built:**

- **Resolved history** — "Show/Hide resolved" toggle in the Needs Attention card header. Backend gets `?include_resolved=true` on the three list endpoints, returning completed items capped at 20 ordered by `completed_at` desc. Frontend renders them muted with strikethrough and completion date; queries only fire when the toggle is on.
- **Previously snoozed indicator** — A small clock icon + "snoozed" text appears inline on any active FollowUp/LabOrder/Referral that has a non-null `snoozed_until`. Since the backend already filters actively-snoozed items, any active item with the field set must have had an expired snooze — no date comparison needed in the frontend.
- **Flexible snooze durations** — Single "Snooze 1w" button replaced with a [1w][2w][1m] pill group in both `ActionItemsSection` and `PostAvsActionPanel`. `snoozeDate()` now takes a `days` argument. Covers referrals or follow-ups that realistically won't happen within a week.

**Files changed:** `src/api/action_items.py`, `frontend/src/api/client.ts`, `frontend/src/components/ActionItemsSection.tsx`, `frontend/src/components/PostAvsActionPanel.tsx`

---

## 16. Pluggable LLM Backend + Agentic Tool-Use (DEC-013)

**Date:** 2026-07-06

**Context:** A GitHub issue asked for a pluggable LLM backend so visit prep could run fully local (Ollama) alongside Claude. Investigating turned up a bigger gap: DEC-009's agentic visit-prep architecture (tool-calling for drug interactions, past-visit lookup, clarifying questions) had been approved back in February but never actually implemented — `prepare_visit()` was still a single-shot prompt-in/JSON-out call, with no tool-calling anywhere in the codebase. A basic `settings.llm_provider` toggle already existed, but it only switched which LLM generated that single-shot response; there was no agentic loop for it to plug into.

**Decision:** Build both together — implement DEC-009's agentic tool-use loop, designed from day one behind a pluggable backend interface (`LLMBackend`) that works for both Claude and Ollama, rather than building the loop Claude-only and retrofitting pluggability later.

**Scope, deliberately bounded for v1:**
- Two read-only tools: `get_medication_details` (structured, on-demand medication lookup — not a real drug-interaction database, which would need a licensed external API) and `lookup_past_visits` (on-demand deeper visit history query)
- Descoped, tracked as follow-up issues: a real drug-interaction checker, and a user-facing pause-to-ask-clarifying-questions flow (both are substantial features on their own — the latter needs new DB state, a new API endpoint, and new frontend UI)
- Fallback, not a hard failure: if the loop can't converge within `agent_max_turns` (default 6) or a backend's tool-call output can't be parsed (`ToolCallParsingError` — expected on small quantized local models, per DEC-009's original caveat), `prepare_visit()` falls back to the existing single-shot call. No regression risk either way.
- Anonymization is applied to tool results the same way for both backends, consistent with how the main context was already anonymized regardless of provider before this change
- No DB schema changes, no API response shape changes, no frontend changes — `prepare_visit()`'s return shape is unchanged

**What was built:**

- **`src/agents/llm_backend.py`** (new) — `LLMBackend` ABC with `ClaudeBackend` (wraps `AsyncAnthropic`, native `tools=` param) and `OllamaBackend` (calls `/api/chat` with OpenAI-style tool specs) implementations. `ToolCall`/`LLMTurnResult` dataclasses normalize both providers' responses into a common shape. `get_llm_backend()` factory keyed off `settings.llm_provider`.
- **`src/agents/tools.py`** (new) — `VisitPrepTools` executor for the two tools, plus `claude_tools()`/`ollama_tools()` adapters that convert one canonical tool spec into each backend's expected wire format. Every tool result is anonymized via the existing `Anonymizer` before being returned to the loop.
- **`src/agents/visit_prep.py`** — new `_run_agentic_loop` method: bounded loop that calls the backend, executes any requested tools, appends results, and repeats until the model returns final text or `agent_max_turns` is exhausted (raising `RuntimeError` to trigger fallback). Wired into `prepare_visit()` ahead of the existing single-shot call, which now only runs when the agentic path is disabled, unavailable, or fails.
- **`src/agents/base.py`** — additive `tool_calls` param on `_log_conversation` for a richer audit trail; no existing call sites changed behavior.
- **`src/config.py`** — new settings `agent_tool_use_enabled` (default `True`, kill switch) and `agent_max_turns` (default `6`).
- **Tests** — new `tests/test_llm_backend.py` (backend abstraction, both providers, malformed tool-call handling) and `tests/test_agent_tools.py` (tool execution + anonymization); extended `tests/test_visit_prep.py` with a successful tool-use round-trip test and a non-convergence fallback test. Full suite: 72/72 passing.

**Verification:** An independent review pass re-ran the full test suite from scratch (confirmed 72/72) and read through the anonymization boundary, exception handling, and turn-counting logic line by line. No correctness bugs found. One non-blocking risk noted: the pre-existing broad `except Exception` around `prepare_visit()`'s Step 7/8 now wraps more surface area (the new tool-execution code), so a genuine bug inside a tool (e.g. a DB error) would currently be silently reported to the user as "AI service unavailable" rather than surfacing distinctly. Left as-is for now; worth tightening in a follow-up if failure visibility becomes important.

**Files changed:** New `src/agents/llm_backend.py`, `src/agents/tools.py`, `tests/test_llm_backend.py`, `tests/test_agent_tools.py`. Modified `src/agents/visit_prep.py`, `src/agents/base.py`, `src/config.py`, `tests/test_visit_prep.py`.

---

## 17. Public Landing Page + Brand Mark (DEC-014)

**Date:** 2026-07-08

**Context:** HealthSteward existed only as a GitHub repo, with no public-facing presence for people who aren't already comfortable browsing source code. The goal was a real landing page, plus a decision on how (and whether) to package the app so non-technical users could try it without a terminal.

**Decision:** Build a standalone marketing landing page (not a build-tooled part of the frontend) with its own visual identity distinct from the app's plain Tailwind UI, but tied to it via a shared brand mark and the app's emerald accent. Packaging strategy for non-terminal users is a separate, larger decision — see DEC-014 for the options considered (install script vs. native desktop app vs. thin Docker launcher) and why the install script was chosen as the starting point, deferring the others. That work is tracked in [issue #18](https://github.com/nidhi-menon/HealthSteward/issues/18) and hasn't started; the landing page's "Get started" section currently documents the real manual setup steps, not a placeholder installer command.

**What was built:**

- **`docs/index.html`** (new) — the landing page, served via GitHub Pages from `/docs` on `main`. Visual identity: a "patient chart" concept — monospace headline styled like a typed after-visit summary, a redaction-bar reveal animation on the hero (ties directly to the PII-anonymization feature), content laid out as chart fields (Chief Complaint, Plan, Chart Access Log, Disposition), and a two-column "trust boundary" panel explaining the local-vs-anonymized-cloud split. Deliberately single-theme (light/paper) — the redaction bars need dark ink on light paper to read, so it doesn't follow the viewer's dark-mode preference. Includes the same anonymization disclaimer already in the README (`src/utils/anonymization.py` — best-effort, not a guarantee) so the two documents don't drift into different claims.
- **Brand mark** — a small SVG icon (a sharp-cornered card outline with one line rendered as a solid bar, echoing the redaction motif) replacing the placeholder "HS" initials badge that was previously hardcoded in the app. Applied consistently in three places: the landing page header (`docs/index.html`), the app's nav (`frontend/src/components/Layout.tsx`), and as the actual favicon for both the app (`frontend/public/favicon.svg`, replacing the default Vite icon) and the landing page (`docs/assets/favicon.svg`).
- **README** — added a "Website" link alongside the existing Discussions/Issues links.

**Explicitly not done in this pass:** the one-step installer script itself, and the `docker-compose.yml` fix it depends on (currently provisions Postgres/Redis/ChromaDB while the app defaults to SQLite, and has no Ollama service) — both are scoped to issue #18.

**Files changed:** New `docs/index.html`, `docs/assets/favicon.svg`, `frontend/public/favicon.svg`. Modified `frontend/src/components/Layout.tsx`, `frontend/index.html`, `README.md`, `docs/notes/DECISIONS.md` (DEC-014). Removed `frontend/public/vite.svg`.

---

## 18. Visit Prep Tool Scope Audit (DEC-015)

**Date:** 2026-07-08

**Context:** Revisiting the visit-prep agentic loop (DEC-009/DEC-013) from first principles: what data is actually useful to prep a visit, regardless of whether a human or an agent does the prepping? The candidate list — current medications, test results, visit notes from other providers since the last visit with the target provider, and any surgeries/hospital admissions/procedures since then — was checked against `src/data/models.py` rather than assumed.

**Findings:**
- **Current medications** — already fully supported; `get_medication_details` returns all current meds when `medication_name` is omitted (that's a tool call default, not missing data — every returned medication still includes its name).
- **Visit notes from other providers since last visit with target provider** — data exists (`Appointment.visit_notes` + `Doctor`), but `lookup_past_visits` only filters by `specialty`/`keyword`, with no date window. Tool-layer gap, not a data gap.
- **Test results** — real data gap. `LabOrder` only records that a test was *ordered* (name, ordered date, status); there is no result value, reference range, or result date anywhere in the schema, and the AVS parser doesn't extract results either.
- **Surgeries / hospital admissions / procedures** — real data gap. No model at all, and no AVS parser section-routing branch for this category.

**Decision:** Split into three independent follow-ups (schema-change costs differ too much to bundle) — see DEC-015 for full reasoning:
1. Widen `lookup_past_visits`'s default window to "since last completed visit with the target provider" — tool-layer only ([issue #21](https://github.com/nidhi-menon/HealthSteward/issues/21))
2. Add lab results to schema + AVS parser, windowed to whichever is shorter of since-last-visit-with-provider or 6 months, to avoid surfacing stale results ([issue #22](https://github.com/nidhi-menon/HealthSteward/issues/22))
3. Add a procedures/hospitalizations model, parser branch, and tool — largest of the three ([issue #23](https://github.com/nidhi-menon/HealthSteward/issues/23))

**Broader audit:** Separately checked whether any other previously-descoped or deferred work across `docs/notes/DECISIONS.md` was missing a tracking issue. Found two:
- **Real drug-interaction checker** — DEC-013 descoped this and said it would be "tracked as a follow-up issue," but no issue was ever filed. Opened as [issue #24](https://github.com/nidhi-menon/HealthSteward/issues/24) — framed as a research spike given the "needs a licensed external API" unknown, with open questions on data source, whether checks should run only inside visit-prep vs. also fire on medication changes, and whether the privacy posture (DEC-006) is compatible with sending medication names to a third-party API.
- **Scheduled push notifications** (DEC-012, option C) — the sibling option D (snooze/completion state) shipped in the medium phase back on 2026-07-05, but option C was deferred and never picked up. Opened as [issue #25](https://github.com/nidhi-menon/HealthSteward/issues/25) — flagged as needing its own design decision (channel, scheduler, trigger logic) before scoping, since it's new infrastructure rather than a pure addition on existing data like options A/B were.

Everything else referenced as deferred (DEC-001 multi-user family sharing, DEC-004/005 PDF storage/encryption approach) is waiting on a decision from the user, not on an engineering task, so it wasn't issue-ified.

**Docs updated:** `docs/notes/DECISIONS.md` (new DEC-015; DEC-012 and DEC-013 status lines updated to link #24/#25/#15 instead of describing untracked follow-up work in prose), `docs/notes/IMPLEMENTATION.md` (same two descoped-item rows linked to #24/#15), `README.md` (decision log range now "DEC-001 through DEC-015").

**Files changed:** `docs/notes/DECISIONS.md`, `docs/notes/IMPLEMENTATION.md`, `README.md`. No code changes — this was a scoping/planning pass, not an implementation.

---

## 19. Public Technical Design Doc + Site Style Guide

**Date:** 2026-07-09

**Context:** DESIGN.md (entry above's follow-on) works as a Markdown snapshot, but isn't a shareable artifact for a technical interview — nobody wants to scroll 600 lines of Markdown live on a call. Built `docs/tdd.html` as a tabbed, publicly-hosted rendering of the same material (problem framing, system design, deep dives, decisions/tradeoffs with filters, a synthetic walkthrough example, honest risks/gaps, glossary, FAQ), styled to match `docs/index.html`'s existing brand identity rather than a generic doc template.

**What was built:**

- **`docs/tdd.html`** (new) — sidebar-navigated, 8 sections, single-theme paper palette shared with `index.html`. Centerpiece is a hand-built system-architecture diagram (not mermaid): a dashed "your machine" boundary box containing 6 vertically-stacked phase boxes (Ingest → Select → Anonymize → Orchestrate → Backend → Serve), each with its own icon-labeled sub-nodes, plus a standalone Claude API box outside the boundary connected by a bidirectional crossing arrow — directly visualizing the local-vs-anonymized-external trust boundary rather than describing it only in prose. Iterated through several structural bugs before landing here: horizontal lanes with inter-card arrows produced "dangling arrow" bugs on wrap (fixed by switching to the vertical full-width-phase-box spine); a `width:100%` + `max-width` breakout attempt silently failed to widen the diagram past its 820px reading column (fixed by setting `width` directly to the `clamp()` expression); `.chart-line`/list text was nested inside containers narrower than its own cap, shrinking it visibly shorter than the row's divider line (removed the redundant nested caps).
- **Accessibility pass**: fixed two real WCAG AA contrast failures (`--ink-faint` 4.15:1 → 5.34:1, `--amber`-as-text 3.24:1 → 5.07:1 — both had shipped without being computed, not just eyeballed), added a proper ARIA tab pattern (roving tabindex, arrow-key nav, `aria-selected`/`aria-controls`) to the sidebar, `aria-hidden="true"` on all 18 decorative diagram icons (previously screen-readers would've announced an unlabeled graphic before every node label), skip-to-content links on both pages, and a repo-wide sweep for a `ch`-unit bug: `ch` is relative to an element's own font-size, so several smaller-font paragraphs (footer, dek, glossary, FAQ, chart-lines) were wrapping narrower than the page's 80ch body text despite nominally sharing the same cap — fixed with per-font-size compensated values.
- **Token consistency fix**: `index.html` and `tdd.html` both defined `--amber`, but with different meanings (a green selection-highlight in one, a real warning-amber in the other) — split into `--amber` (warning/boundary, consistent value in both files now) and `--select-hl` (selection highlight) to stop the collision.
- **`docs/SITE_STYLE_GUIDE.md`** (new) — captures every pattern above as a living reference (unlike DESIGN.md's point-in-time-snapshot rule) so the next edit to either public page doesn't have to rediscover the `ch`-compensation formula, the breakout-width pitfall, or the diagram conventions from scratch. Cross-linked from `CLAUDE.md` and the README.
- **Diagram sizing**: scaled the whole diagram to 80% via CSS `zoom` (not `transform: scale()`, which leaves reserved blank layout space since it doesn't reflow) after confirming a `transform`-based preview looked right; raised the smallest diagram sub-label text from 9.5px to a 10.5px legibility floor first, since a blanket 80% shrink would otherwise have pushed it below that.
- **Cross-linked Risks & Open Gaps to live issues**: four of the panel's six items map to actual GitHub issues (#27, #29, #30, #31 — confirmed via `gh issue view` before linking, not assumed), plus a general pointer to the Issues backlog and Discussions.

**Files changed:** New `docs/tdd.html`, `docs/SITE_STYLE_GUIDE.md`. Modified `docs/index.html` (shared token fixes, skip-link, cross-nav to tdd.html), `CLAUDE.md` (gitignored, local-only — pointer to the new style guide), `README.md` (Documentation section).

---

## 20. Landing Page Terminology: Dropped Clinical-Jargon Labels

**Date:** 2026-07-09

**Context:** Revisiting `index.html`'s "patient chart" visual concept (entry 17), the section labels were literally in-character clinical terms — "Chief Complaint," "Chart Access Log," "Disposition." Two problems surfaced on review: the terms ask a first-time visitor to decode jargon before reaching actual content, and the site's author isn't a clinician, so writing the page's voice in clinical vocabulary reads as a costume that doesn't fit — not what HealthSteward is about.

**Decision:** Keep the visual chart identity (brand mark, redaction-bar reveal animation, palette, monospace/serif pairing) since it's genuinely tied to the anonymization feature, not just decoration — but replace the in-character section labels with plain, direct ones:

| Before | After |
|--------|-------|
| "patient chart · continuity of care · v0, early development" (hero eyebrow) | "open source · privacy-first · v0, early development" |
| "Chief Complaint" | "The Problem" |
| "Plan" | "Features" |
| "Chart Access Log" | "Privacy" |
| "Disposition" | "Setup" (not "Get Started" — would have duplicated the section's own h2) |

Left unchanged: "Stays on device," "Anonymized first," the three "terminal — ..." labels, and the Profile/Prep/Ingest/Follow-up feature tags — these were already plain, not clinical roleplay. Also kept the footer's "not a substitute for clinical judgment" line — a standard protective disclaimer, not costume language, distinct from the labeling issue.

**Reasoning:** Distinctive visual identity and plain language aren't in tension here — the metaphor lives in the *styling* (mono headline like a typed summary, redaction bars, chart-line layout), not in the *words* the visitor has to read. Removing the in-character vocabulary doesn't cost the page its identity, and it removes a real confusion/tone risk.

**Files changed:** `docs/index.html`.

---

## 21. Landing Page: Personal Note From the Builder

**Date:** 2026-07-09

**Context:** The landing page pitches HealthSteward on privacy and coordination mechanics, but had no human voice behind it — no explanation of why it exists or an invitation for feedback. Added a "Personal Note" section, in the same first-person voice deliberately absent from the rest of the page (which stays product-copy throughout).

**What was built:** A new `#from-me` section, labeled "Personal Note" (after briefly trying "Margin Note," which was confusing, and "From Me"), covering: living for years with undiagnosed endometriosis/PCOS/adenomyosis and the medical gaslighting that came with it; a high-risk pregnancy and a layoff during the last trimester as the moment that made it personal rather than intellectual; an explicit bridge line tying that experience to why HealthSteward runs locally by default ("when a system has already failed to take you seriously, the last thing you want is to also hand your data to another one"); why it's public under GPLv3; and a direct invitation for critique.

**Placement:** Ordered last among the field sections — after Setup, right before the footer — rather than between Privacy and Setup where it was first drafted. Reasoning: going straight from a vulnerable personal story into `pip install` commands read as tonal whiplash; keeping the practical flow (problem → features → privacy → setup) uninterrupted and closing on the personal note instead reads more like an authentic sign-off. Nav link order was updated to match.

**Reasoning:** The section is deliberately personal-heavy rather than product-heavy — "what HealthSteward does" is already covered thoroughly elsewhere on the page, so re-explaining it here would be redundant. The bridge sentence was added specifically so the personal and product paragraphs read as causally connected rather than a life story followed by an unrelated project plug.

**Files changed:** `docs/index.html`.

---

## 22. Personal Note: Rewritten

**Date:** 2026-07-09

**Context:** Revisited entry 21's Personal Note copy. Two concerns: naming specific diagnoses (endometriosis, PCOS, adenomyosis) publicly and permanently, tied to a real name, in a page also linked from a technical/interview-facing artifact; and whether "medical gaslighting" plus a diagnosis-delay framing was the most direct way to explain why HealthSteward exists specifically, versus a story more tightly tied to the coordination failure the app actually addresses.

**Decision:** Rewrote the section around a different, more concrete incident: months of postpartum chronic-condition management (medications, blood tests, follow-ups) quietly lapsing with no provider ever flagging it, because care was split across specialists with no shared system and the patient was the only one holding the full picture. Drops the named diagnoses and the "medical gaslighting"/professional-background framing entirely. Also cut a relative time reference ("last year") that would go stale on rereading — the section already anchors to an absolute date ("December 2025") a sentence later, so the relative one was redundant and the one that ages badly. Restored a "why open source" beat (shared it with others, realized the need went beyond personal use) that a tighter intermediate draft had cut along with the redundant product-feature recap.

**Reasoning:** The new framing is more directly load-bearing for "why does this specific tool, with this specific architecture, exist" — a coordination failure that nobody caught maps straight onto a tool that centralizes and tracks, more so than a diagnostic-delay story did. It also resolves the disclosure-level question in the author's favor without needing a judgment call from anyone else: specific diagnoses are gone, the concrete narrative beat (a gap that opened and took a long time to close) stayed.

**Files changed:** `docs/index.html`.

---

## 23. Local-First Default + Custom OpenAI-Compatible Provider + Runtime Settings

**Date:** 2026-07-09

**Context:** The default LLM provider for visit prep was Claude API, decided in DEC-009 specifically because the dev machine (8GB RAM M3) can't run quantized local models reliably enough for tool-calling. That's a real constraint, but it made the *default* out of step with the project's own privacy-first framing — "stays on device" was the opt-in, not the default, on exactly the feature (visit prep) people would use most. On top of that, there was no way to change the LLM provider without hand-editing `.env` and restarting the backend, and only two providers existed at all (Claude, Ollama) — no path to "point this at whatever model I actually want to use."

**What was built:**
- Flipped `llm_provider`'s default to `"ollama"` in `src/config.py`. Claude is now an explicit opt-in.
- Added a third provider, `CustomOpenAICompatibleBackend` in `src/agents/llm_backend.py`, for any endpoint speaking OpenAI's `/chat/completions` + tool-calling format — covers OpenAI, OpenRouter, Groq, Together, a self-hosted vLLM/LM Studio server, etc. Reused the existing `ollama_tools()` adapter (Ollama's tool-spec shape is already OpenAI-style) rather than writing a third adapter.
- Consolidated three separate `settings.llm_provider == "ollama"` string checks in `visit_prep.py` (agentic-loop tool selection, single-shot fallback dispatch, model-name-for-logging) into single dispatch through `get_llm_backend()`/`get_tools_for_provider()`. Folded the old provider-specific `_call_claude`/`_call_ollama` single-shot methods into one `_call_backend()`.
- Added a DB-backed settings layer so the provider can be switched at runtime, not just via `.env`: a singleton `AppSettings` row (`src/data/models.py` + Alembic migration), `src/services/settings_service.py` (`get_effective_settings()` overlays non-null DB values onto the env-based `Settings`, `update_settings()` upserts), and `GET`/`PUT /api/settings` (`src/api/settings.py`, API keys masked to last-4-chars on read). `VisitPrepAgent.prepare_visit()` now pulls effective settings fresh at the start of each call instead of caching env-only settings at construction time.
- New frontend Settings page (`frontend/src/pages/Settings.tsx`) with a provider selector (Ollama / Claude / Custom) and provider-specific connection fields, linked from the nav (`Layout.tsx`).

**Reasoning:** DEC-009's tool-reliability finding didn't change — it's still true that small quantized local models are unreliable at function-calling, which is exactly why the DEC-013 fallback-to-single-shot path exists and now matters more broadly, since more installs will default into hitting it. What changed is the judgment about which trade-off should be the *default* for users generally, versus what was true of one specific underpowered dev machine. "Connect any LLM" was scoped to "any OpenAI-compatible endpoint" — one adapter covers the large majority of hosted and self-hosted options without per-provider bespoke code, consistent with DEC-013's bounded-scope pattern. Full reasoning in DEC-016.

**Files changed:** `src/config.py`, `src/agents/llm_backend.py`, `src/agents/tools.py`, `src/agents/visit_prep.py`, `src/data/models.py`, `src/services/settings_service.py` (new), `src/api/settings.py` (new), `src/models/schemas.py`, `src/main.py`, `alembic/versions/a1b2c3d4e5f6_add_app_settings.py` (new), `tests/test_llm_backend.py`, `tests/test_visit_prep.py`, `frontend/src/pages/Settings.tsx` (new), `frontend/src/App.tsx`, `frontend/src/components/Layout.tsx`, `frontend/src/api/client.ts`, `frontend/src/types/index.ts`, `.env.example`.

---

## 24. Context Selection: Priority-Based Stage 3 Packing, Stage 2 Candidate Cap, Pinning

**Date:** 2026-07-13

**Context:** Writing a deeper technical-design-doc explanation of DEC-008's 4-stage context selection pipeline (`src/utils/context_selection.py`) surfaced that the shipped code didn't match its own module docstring or the TDD's description. Stage 3's docstring/comment both claimed it would "summarize older visits with the local LLM if still over budget" — it never did; it just stopped adding visits (`break`) the moment one didn't fit, silently dropping everything after that point in whatever order it happened to receive them (recency, from Stage 1). Separately, Stage 2 calls Ollama once per candidate, sequentially, with no cap — an unbounded number of candidates could mean an unbounded number of sequential local-LLM round trips before question generation even starts.

**What was built:**
- Stage 3 (`stage3_token_budget`) now packs by priority (pinned visit first, then Stage 2's relevance score descending, then recency as a tiebreaker/fallback when no score exists) instead of by whatever order it received. It also keeps evaluating past an over-budget visit instead of stopping there, so a smaller later visit can still be packed in. Returns a third value, `dropped` count, instead of silently discarding the rest.
- Stage 2 (`stage2_llm_scoring`) now returns `(appointment, score)` pairs instead of a filtered list, so the score survives into Stage 3's packing order rather than being thrown away the moment it's used as a pass/fail filter.
- Added `context_stage2_max_candidates` (default 15, provisional — see issue #56) — caps how many candidates get sent to Stage 2's scoring calls, applied in `select_context` before calling `stage2_llm_scoring`.
- Added pinning: `select_context` identifies the Stage-1 same-doctor visit (there's at most one, by construction) and threads its id through as `pinned_ids` to both Stage 2 (exempt from the cap and from the relevance-cutoff filter) and Stage 3 (packed first, regardless of score). Previously this visit's "always include" guarantee from Stage 1 didn't actually survive Stage 2 or 3 — it could be capped out or scored below the cutoff like any other candidate.
- `ContextSelectionResult` gained `visits_dropped_stage2_cap` and `visits_dropped_stage3_budget` fields; `visit_prep.py` logs both instead of the drop being invisible everywhere.

**Reasoning:** Summarization was rejected as the fix for Stage 3, not just deferred — for medical context specifically, a lossy/hallucinated summary from a small quantized model is a worse failure mode than an honestly-truncated list (see issue #56 discussion). Priority-based packing plus visible drop counts solves the actual problems (arbitrary drop order, invisible data loss) without introducing a new LLM call or a new way for the pipeline to be subtly wrong. The candidate cap's default (15) is a placeholder, not a measurement — issue #56 tracks grounding it in real per-call Ollama latency and evaluating whether to batch Stage 2's scoring into one call instead of N sequential ones.

**Files changed:** `src/utils/context_selection.py`, `src/agents/visit_prep.py`, `src/config.py`, `tests/test_context_selection.py`.

Related: issue #56.

---

## 25. Context Selection: Stage 2 Was Never Actually Wired Up

**Date:** 2026-07-14

**Context:** While auditing the context-selection deep dive in `docs/tdd.html` for accuracy (following entry 24's fixes), traced through where `ContextSelector`'s `ollama_client` actually comes from in production. `VisitPrepAgent.__init__` constructs `ContextSelector(anonymizer=..., stage2_threshold=..., relevance_cutoff=..., stage2_max_candidates=...)` — never passing `ollama_client`. Since `ContextSelector.__init__` defaults it to `None`, and `stage2_llm_scoring()` unconditionally skips (`if not self.ollama_client: return [(appt, None) for appt in candidates]`) when it's `None`, **Stage 2 relevance scoring has never actually run in the shipped app**, regardless of Ollama's availability or model. It's only ever been exercised in unit tests, which inject a mock client directly. In production, context selection has always been a 3-stage pipeline (rules filter → budget pack → anonymize), not the documented 4-stage one — entry 24's pinning/cap/priority-packing fixes were all correct code, just unreachable.

**What was built:**
- `visit_prep.py` now calls `get_ollama_client()` (`src/agents/ollama_client.py`) and assigns it to `self.context_selector.ollama_client` fresh on every `prepare_visit()` call, right before Stage 2 would run. That function already existed specifically for this purpose (its own module docstring says "Relevance scoring in context selection (Stage 2)") and already does a live availability check, returning `None` if Ollama isn't reachable — which `select_context()` already treats as "skip Stage 2," so no new fallback logic was needed, just the missing wiring.
- Added a regression test (`test_prepare_visit_wires_ollama_client_into_stage2_scoring`) that creates enough past visits to trigger Stage 2, mocks the Ollama client, and asserts it's actually called during a real `prepare_visit()` run — this is the test that would have caught the original bug.
- Along the way, found the existing test suite's `get_ollama_client()` singleton doesn't survive pytest-asyncio's per-test event loops when a real local Ollama happens to be running (dev-machine-dependent "Event loop is closed" failures on teardown). Added an autouse fixture in `test_visit_prep.py` to stub it out for the existing tests (none of which create past appointments, so Stage 2 was never meant to be exercised by them anyway).
- Corrected `docs/tdd.html` in two more places that assumed PDF parsing and context-selection scoring share one model (`qwen2.5:7b`) — they don't. Parsing has its own dedicated setting (`avs_parser_model`); scoring reuses whatever `ollama_model` is configured as (`llama3.2` by default, the same model the agentic loop uses). This was already wrong before today's fix and remains a separate configurability gap (issue #59) — the wiring fix makes Stage 2 *run*, it doesn't give it its own model setting.

**Reasoning:** This was found by tracing "why does the AI (local) row say qwen2.5:7b for scoring" all the way to source, not by looking for bugs directly — a reminder that doc-accuracy audits surface real functional bugs, not just stale prose. No DEC entry: this restores DEC-008's already-decided 4-stage design, it isn't a new architectural choice.

**Files changed:** `src/agents/visit_prep.py`, `tests/test_visit_prep.py`, `docs/tdd.html`.

Related: DEC-008, entry 24, issue #59.

---

## 26. Evaluation Plan Page

**Date:** 2026-07-14

**Context:** Issue #29 (no quality evaluation of visit-prep output) has been an open, unimplemented gap since it was filed — the test suite verifies plumbing, not whether the AI output is actually good. Wanted a concrete plan captured before an interview, grounded in the real pipeline (`context_selection.py`'s 4-stage selector, `visit_prep.py`'s prompt + agentic loop, `tools.py`'s two tools) rather than a generic eval template, and to extend that plan to the other three AI-touching components (AVS parsing, PII anonymization) that issue #29 doesn't cover on its own.

**What was built:** A new "Evaluation Plan" tab in `docs/tdd.html`, explicitly labeled "Proposed, not built." Key structural decision: visit prep's AI decisions split into two eval surfaces with different failure modes — **retrieval** (`ContextSelector`, Stages 1-2: fails by omission or dilution) and **generation** (`VisitPrepAgent.prepare_visit`: fails by hallucination or scope violation) — because a generation eval can't detect something retrieval never surfaced to the LLM in the first place. Covers:
- Retrieval eval: Stage 1 as pure-assertion unit tests, Stage 2 recall@selected as the primary metric (token budget makes recall the scarce resource), a stage-attribution breakdown (which stage killed each gold visit), and Stage 2 scorer calibration.
- Generation eval: five independent correctness dimensions (groundedness, specialty scope, relevance, non-redundancy, format validity), each with its own ground truth/metric/method — scored separately since conflating them into one "quality" number hides which one is actually breaking. Specialty scope is flagged as the highest value/effort item since it's fully programmatic, reusing `med_specialty_map`/ICD-10 tags already computed in code.
- AVS parsing and PII anonymization eval, both fully deterministic (golden-set diff; synthetic-PII span-overlap), no judge-reliability problem.
- A proposed `eval/` harness directory shape, and the observation that `ConversationLog` already logs the full anonymized context per call (verified against `_log_conversation` in `src/agents/base.py`) — so a "run judges against real logged conversations" eval mode needs zero new data collection.
- Offline (fixture harness, run on-demand) vs. "online" (passive `ConversationLog` monitoring — fallback-rate visibility per issue #30, retroactive judge sampling, human-in-the-loop feedback) reinterpreted for a single-user local app rather than population-scale A/B testing.
- A single ranked 8-item build order across all four components, rendered as three priority tiers (deterministic-first) rather than a flat list, plus a `Judge?` badge column on both detail tables (reusing the existing deterministic/llm/hybrid badge convention) so judge-dependency is scannable without reading prose.

Also fixed `docs/index.html`'s quick-install section, which only listed the `qwen2.5:7b` pull command despite visit prep needing `llama3.2` by default too.

**Reasoning:** Self-critiqued before shipping and found five real issues in the first draft — a mislabeled table row (called "Stage 2 selection" what was actually end-to-end Stages 1-3 recall), inconsistent table schemas between the retrieval and generation tables, a redundant claim stated twice, a build-order list that only covered 6 of the 8 real items with the other 2 hand-waved in, and a "Metric" column cell that was phrased as a question instead of naming a metric. Fixed all five before the density pass. The density/visual pass came from direct feedback that an 8-item list of paragraph-length bullets is hard to use *during* an interview — converted to tier diagrams and badge columns that add a fast-scan layer without removing any of the underlying detail.

**Files changed:** `docs/tdd.html`, `docs/index.html`.

Related: issue #29, issue #30.

---

## 27. Unified Brand Palette (DEC-017)

**Date:** 2026-07-16

**Context:** Building a GitHub social preview card and a LinkedIn brand asset surfaced a real inconsistency: the docs site's favicon/logo used a deliberately-designed teal, but the actual running app used Tailwind's `emerald` as its primary accent, on a cool-toned `gray-50` background — two disconnected color systems that had never been reconciled.

**What was built:**
- Verified the app's actual colors before assuming anything — grepped `frontend/src` rather than trusting the initial "the app uses teal" premise, which turned out to be wrong (no teal anywhere in the app; real primary accent was `emerald-600/700`, with `blue`/`green`/`purple` used for distinct categorical states — appointment status, document tags, ICD-10 codes).
- Computed actual WCAG contrast ratios (`amber` vs. paper at both the old cream and new near-white values) rather than eyeballing a "colors might clash" intuition — the numbers didn't support an earlier draft objection, which was corrected before it became a decision input.
- Chose to promote the docs site's existing, already-designed, already-audited teal/amber system to the single canonical brand palette everywhere, rather than reverse-engineer a system out of the app's incidental Tailwind defaults.
- Background moved from the docs' cream (`#efeee6`) and the app's cool `gray-50` to one shared near-white (`#fafaf9`); `--paper-raised` moved from `#f7f6ef` to `#ffffff` to preserve "raised = lighter than base."
- Added a Tailwind v4 `@theme` block (`frontend/src/index.css`) defining `brand-teal`/`brand-teal-bright`/`brand-amber`/`brand-paper`/`brand-ink` as the exact docs hex values; bulk-replaced every `emerald-*` class with the matching token.
- One deliberate semantic fix beyond the mechanical rebrand: the "Parsing document with local LLM" indicator was using `blue`, despite being exactly the concept the brand system already calls teal ("runs locally") — changed to `brand-teal`/`brand-teal-bright`.
- Deliberately left other `blue`/`purple` usages (appointment status, document category tags, ICD-10 chips) and component-level `gray-50` tints (disabled inputs, nested sub-panels) untouched — different UI concerns (categorical meaning, visual hierarchy) than brand identity; collapsing them would have reduced clarity, not improved consistency.
- Updated `docs/SITE_STYLE_GUIDE.md`'s documented palette values/rationale, `README.md`'s badge colors, the GitHub social preview card, and the favicon (`docs/assets/favicon.svg`) to match the site header's actual logo markup, which it had drifted from.
- Also corrected the `status` badge (README + social card) from "early development" to "active development" — "early" undersold a project whose core agentic architecture is implemented and running; "active" doesn't overclaim stability the eval harness and installer (issue #18) still lack.

**Reasoning:** Full color uniformity was the explicit goal, but "uniform brand" means shared *brand* colors, not collapsing every incidental UI color into two tokens regardless of what it currently communicates — status/category colors that were never about brand identity were left alone on purpose. See DEC-017 for the full options-considered table.

**Files changed:** `frontend/src/index.css`, `frontend/src/components/Layout.tsx`, `frontend/src/pages/ProfileDetail.tsx`, plus every component using `emerald-*` classes, `docs/index.html`, `docs/tdd.html`, `docs/SITE_STYLE_GUIDE.md`, `docs/assets/favicon.svg`, `README.md`.

Related: DEC-017.

---

## 28. Agentic Loop: Fixed Two Silent-Failure Paths (#52, #53)

**Date:** 2026-07-18

**Context:** Prioritizing the backlog ahead of building the #29 eval harness surfaced two bugs in the agentic tool-use loop, both in the same class: code that already had the right structure in place for a failure to be visible, but wasn't actually using it — so failures degraded silently instead. #53: `VisitPrepTools.execute()` (`src/agents/tools.py`) returned the string `"Unknown tool: {name}"` for an unrecognized tool name instead of raising, so a hallucinated tool call was fed back into the conversation as if it were a legitimate result — the model had no way to know it went wrong, and neither did anything watching the loop. #52: `_log_conversation` (`src/agents/base.py`) already accepted a `tool_calls` parameter and stored it in `ConversationLog.extra_data`, but neither call site in `visit_prep.py` ever passed it, so no `ConversationLog` row could ever be used to reconstruct which tools ran during a given visit-prep call.

**What was built:**
- Added `UnknownToolError` (`src/agents/tools.py`); the unknown-tool branch now raises it instead of returning a fake result string.
- `visit_prep.py`'s agentic-loop caller now catches `UnknownToolError` alongside the existing `ToolCallParsingError`/`RuntimeError`, so an unrecognized tool name triggers the same single-shot fallback as any other loop failure (DEC-009/DEC-013), rather than silently continuing.
- `_run_agentic_loop` now accumulates `{name, input, result}` for every tool call across all turns into a list initialized once outside the turn loop (not reset per turn), and passes it to `_log_conversation(tool_calls=...)` when the loop converges — `ConversationLog.extra_data["tool_calls"]` is now actually populated.
- Regression tests: unknown-tool-name now asserts the raise (`tests/test_agent_tools.py`); single-turn tool-call logging, a 2-turn multi-tool-call accumulation test (guards specifically against the list being reinitialized inside the loop and dropping earlier turns), and the existing non-convergence fallback test extended to cover the unknown-tool fallback path (`tests/test_visit_prep.py`).

**Reasoning:** Neither fix is an architectural choice — both restore behavior the existing code structure already implied (a `tool_calls` param nobody passed, an exception-handling path that already existed for two sibling error types). No DEC entry. Chose to raise rather than log-and-continue for #53 specifically because the loop already has a working fallback path (DEC-013) — routing through it is strictly better than inventing a second silent-degradation mode alongside the first.

**Files changed:** `src/agents/tools.py`, `src/agents/visit_prep.py`, `tests/test_agent_tools.py`, `tests/test_visit_prep.py`.

Related: issue #52, issue #53, DEC-009, DEC-013.

---

## 29. Evaluation Harness v1 (DEC-018) + Three Production Bugs It Found + Prompt Versioning

**Date:** 2026-07-19

**Context:** Picked up issue #29 next, following `docs/tdd.html`'s existing Evaluation Plan tab (entry 26) and its tiered, deterministic-first build order. Before writing any harness code, swept the pipeline for structural gaps in the same family as a redundancy issue found while scoping this (the 4-stage `ContextSelector` and the agentic loop's on-demand tool calls are two independent retrieval phases that don't coordinate) — that sweep surfaced four more real gaps, filed as issues #71 (Ollama calls never set `num_ctx`), #72 (`SPECIALTY_MAPPING`/`ICD10_SPECIALTY_MAP` can disagree), #73 (`PII_PATTERNS` is a narrow hand-rolled list), #74 (clinic-keyword specialty inference has the same gap as #72, sequenced behind it). None blocked v1; all are tracked follow-ups.

**What was built:**
- `eval/` package: `fixtures.py` (5 synthetic cases, each deliberately constructed to exercise one specific check — a cross-specialty medication, lab/vitals data, a zero-data cold start, a dosing-interaction case designed to make a tool call useful, and a past-visits case designed to test retrieval redundancy), `db.py` (persists a case into a real DB via the actual ORM models, not a re-implementation), `scorers.py` (format validity, groundedness entity-match, specialty-scope checker, tool-call necessity, Phase 1/Phase 2 retrieval redundancy — all deterministic, no judge), `retrieval_stage1.py` (pure-assertion Stage 1 rule checks, including one that documents #72's gap by asserting today's buggy behavior on purpose, flipped once #72 is fixed), `run.py` (CLI runner — real pipeline, real configured backend, temperature=0.0, writes a timestamped JSON report and diffs against the prior run).
- Two small, targeted production changes the harness needed: a `temperature` parameter threaded through `LLMBackend.call()` → `prepare_visit()` (production default 0.7 untouched), and run diagnostics (`last_context_selection`, `last_tool_calls`) exposed on `VisitPrepAgent` after a run, rather than changing its return contract.
- Ran the harness against a real local Ollama server, not just mocks — deliberately, since a mock-only harness would validate the scorers but never prove the pipeline actually works end to end. This immediately found three real, previously-invisible production bugs, all fixed same-branch: Ollama's `/api/chat` streams by default and the backend never sent `stream: false`, so `response.json()` broke on any real multi-chunk response (`json.JSONDecodeError: Extra data`) — plausibly degrading most/all real Ollama-backed calls straight to the generic canned fallback with no visible error; `temperature` was sent top-level, which Ollama's native API silently ignores (needs nesting under `options`); and the HTTP timeout only bounded gaps *between* chunks, not total request duration, so one case's real generation ran over 30 minutes on an active-but-stalled connection with nothing to stop it — fixed with an `asyncio.wait_for` wall-clock ceiling plus a per-case guard in the harness itself.
- A fourth bug, this one in the harness rather than production: an undisposed `AsyncEngine` in `eval/run.py` left the process hanging ~17 minutes in asyncio shutdown/cleanup *after* it had already written its results — the actual work finished in under 4 minutes each time; only interpreter teardown was stuck. Fixed by returning and disposing the engine explicitly.
- First real (post-fix) baseline run found a genuine, actionable result on its own: 0 of 5 cases passed the system prompt's own stated 8-15 question requirement, and one case (`cold_start`, zero vitals data) generated a question asking about blood pressure readings that were never provided — a caught hallucination, exactly the harness doing its job.
- Reinforced both `visit_prep.py` system prompts in response (moved the count requirement earlier, restated it as a pre-response self-check, added an explicit "don't reference data that wasn't provided" rule) and re-ran the harness: 3 of 5 cases now pass format validity (up from 0), grounded_rate improved in every case that changed, none regressed. Two cases still fail the count — `cold_start` in particular has very little real data to draw 8+ grounded questions from, which may be a harder ceiling for that case specifically rather than a remaining prompt-following gap.
- Started project-wide prompt versioning (DEC-018), prompted by this exercise having nowhere to record why the prompt changed or what evidence justified it. Every prompt in the codebase now carries a version tag; `docs/notes/PROMPT_CHANGELOG.md` is the new source of truth for prompt-by-prompt history, separate from `DECISIONS.md` (architecture) and this log (narrative). `visit_prep.py`'s prompts log their version into `ConversationLog` on every real run; the Stage 2 scoring prompt and the AVS parser's five prompts are versioned but not yet threaded into a per-run log — an acknowledged gap, not a silent one.
- Regression tests added throughout: `tests/test_eval_harness.py` for the scorers/plumbing (mocked backend, no live model dependency), plus new/extended cases in `tests/test_llm_backend.py` for the streaming/temperature-placement fix and the wall-clock timeout.

**Reasoning:** Deterministic-only v1 was the deliberate scope, matching `docs/tdd.html`'s own build order — judge-model reliability is a separate, harder problem, and shipping a real (if narrower) regression signal now beat blocking on solving that first. The decision to actually run against live Ollama rather than stop at mocked unit tests was the single highest-value choice in this whole session: it found three real production bugs a mock-only harness structurally cannot find, since mocks by definition can't diverge from the real wire format the way a real server can. Prompt versioning wasn't originally scoped for this session — it became obviously necessary the moment the harness produced its first real "should we change the prompt" decision and there was nowhere durable to record it.

**Files changed:** `eval/__init__.py`, `eval/fixtures.py`, `eval/db.py`, `eval/scorers.py`, `eval/retrieval_stage1.py`, `eval/run.py`, `src/agents/llm_backend.py`, `src/agents/visit_prep.py`, `src/agents/base.py`, `src/utils/context_selection.py`, `src/parsers/agent/prompts.py`, `tests/test_eval_harness.py`, `tests/test_llm_backend.py`, `docs/notes/PROMPT_CHANGELOG.md`, `CLAUDE.md`, `.gitignore`.

Related: issue #29, issue #71, issue #72, issue #73, issue #74, DEC-008, DEC-009, DEC-011, DEC-013, DEC-018.

---

## 30. Fixed Ollama `num_ctx` Never Being Set (#71, DEC-019)

**Date:** 2026-07-20

**Context:** Picked up issue #71 next off the backlog — one of the follow-up bugs surfaced while scoping the #29 eval harness (entry 29). `_OpenAIStyleHTTPBackend.call` never included `num_ctx` in the Ollama request payload, so Ollama silently used its own runtime default (commonly 2048 for a freshly-pulled model) regardless of what this app's `context_max_tokens` budget (2000) assumed — a gap that predates the agentic loop's tool-call overhead and could already be silently truncating context on local models.

**What was built:** Added `Settings.ollama_num_ctx: int = 8192` (`src/config.py`), sized from a documented formula (`context_max_tokens` + estimated system-prompt overhead + per-turn tool-call overhead × `agent_max_turns`, rounded to the next power-of-two Ollama context size) rather than an arbitrary round number, and wired it into `OllamaBackend._sampling_payload`'s `options` dict (`src/agents/llm_backend.py`) — scoped to `OllamaBackend` only, since `num_ctx` isn't a standard OpenAI-compatible field and `CustomOpenAICompatibleBackend` shares the same base class. Kept env-only for now rather than adding it to the runtime-editable Settings allowlist, matching the existing gap on `ollama_model` (issue #59) instead of quietly compounding it.

Went back and closed the issue's second half rather than leaving it as a follow-up: added `_context_budget_warning`, a hook on `_OpenAIStyleHTTPBackend` (no-op by default, overridden by `OllamaBackend`) that estimates a request's token count via a chars/4 heuristic over the serialized messages and tool specs, and logs a loguru warning — naming the estimate and which settings to adjust — if it crosses 75% of `ollama_num_ctx`. Deliberately a visibility mechanism rather than a hard gate, since the heuristic isn't a real per-model tokenizer count and shouldn't block an otherwise-fine request on a false positive.

Added three regression tests in `tests/test_llm_backend.py`: `test_ollama_backend_sets_num_ctx_from_settings` (configured value reaches the payload), `test_ollama_backend_warns_when_request_likely_exceeds_num_ctx`, and `test_ollama_backend_no_warning_for_small_request`.

**Reasoning:** See DEC-019 for the full options analysis — a formula-grounded default plus a runtime overflow warning closes both halves of the issue's expected behavior (explicit, reasoned `num_ctx`; loud failure on likely overflow) without needing a separate profiling project to trust the number first.

**Files changed:** `src/config.py`, `src/agents/llm_backend.py`, `tests/test_llm_backend.py`, `docs/notes/DECISIONS.md`.

Related: issue #71, DEC-019, DEC-008, DEC-009, DEC-013, DEC-018.

---

## 31. Doctor.notes Never Reached Visit-Prep Context (#51)

**Date:** 2026-07-20

**Context:** Picked up issue #51 next off the backlog — same class of gap as `Appointment.prep_notes` (#43): `Doctor.notes` (`src/data/models.py:157`) is a persisted, user-editable freeform field (the "Notes" textarea on the Doctor modal, distinct from the already-wired Condition modal's Notes field) with zero references in `visit_prep.py`, `context_selection.py`, or `anonymization.py`. `Condition.notes` and `Appointment.visit_notes` were both already confirmed wired in; `Doctor.notes` was the one remaining orphaned notes field.

**What was built:**
- `AnonymizedDoctor` (`src/utils/anonymization.py`) gained a `notes: Optional[str]` field, populated in `Anonymizer.anonymize_doctor()` via `self.anonymize_text(doctor.notes)` — same anonymization call as every other free-text field, not a new code path.
- `VisitPrepAgent._build_context_message` (`src/agents/visit_prep.py`) now appends a `- Provider Notes: ...` line to the "Upcoming Appointment" section when present, reading the already-anonymized `appointment.doctor.notes` (no double-anonymization, since context assembly operates on the `AnonymizedAppointment`/`AnonymizedDoctor` dataclasses, not raw ORM objects).
- Regression test `test_prepare_visit_includes_doctor_notes_in_context` (`tests/test_visit_prep.py`) — forces `llm_provider="claude"` via `monkeypatch.setattr(get_settings(), "llm_provider", "claude")` (matching `test_prepare_visit_agentic_tool_use`'s pattern) so the mocked Claude client is actually the backend exercised, then asserts the doctor's notes text appears in the constructed context message. Found while writing this that several *existing* `test_visit_prep.py` tests patch `AsyncAnthropic` to mock Claude but never force `llm_provider` away from the dev machine's `.env` default (`ollama`) — those tests were silently exercising a real/timing-out Ollama call and its single-shot fallback instead of the intended mock, which happened to still produce a 200 response so nothing failed, just not against the code path the test's own docstring claims. Out of scope for #51 itself; filed as issue #79.

**Reasoning:** Not an architectural choice — restores the same anonymize-then-include treatment every other patient/provider free-text field already gets, following the exact pattern `Condition.notes` already established rather than inventing a new one. No DEC entry, matching the #52/#53 precedent (entry 28) for gap-filling fixes with no new architectural surface.

**Files changed:** `src/utils/anonymization.py`, `src/agents/visit_prep.py`, `tests/test_visit_prep.py`.

Related: issue #51, issue #43, issue #79.

---

## 32. "Retry" on a Failed Document Parse Never Actually Retried (#45)

**Date:** 2026-07-20

**Context:** Picked up issue #45 next. `handleParse` (`frontend/src/pages/ProfileDetail.tsx`) only called `documents.parseFile(...)` — the endpoint that resets a document's `parse_status` from `failed` back to `pending` (`src/api/documents.py`'s `/parse-file`) — when `documentId` was falsy. A previously-failed document already has a `document_id` (set from the scan response), so that branch was always skipped, and `handleParse` went straight to `documents.getParsed`, which immediately re-raises the same cached `parse_error` as a 422 for any document whose `parse_status` is already `"failed"` without ever re-invoking the parser. Clicking "Retry" redisplayed the same stale error every time.

**What was built:**
- `DocumentCard`'s `onParse` prop now passes the file's `status` through, not just `filename`/`documentId` (`frontend/src/components/DocumentCard.tsx`).
- `handleParse` (`frontend/src/pages/ProfileDetail.tsx`) now calls `parseFile` whenever `!docId || status === 'failed'`, not only `!docId` — so a failed document gets its `parse_status` reset to `pending` server-side before `getParsed` is called, letting the backend's existing `pending → parsing → completed/failed` flow actually re-run rather than short-circuiting on the cached failure.
- No backend change needed — `/parse-file`'s failed→pending reset and `/parsed`'s trigger-on-pending behavior were already correct; this was purely a frontend control-flow gap.
- Verified against a live `uvicorn` instance rather than just the diff: created a document, forced a real parse failure (invalid PDF), confirmed `getParsed` alone re-raises the identical cached error with no `updated_at` change (the pre-fix bug, reproduced exactly), then confirmed calling `parse-file` first (the fix's new code path) resets `parse_status` to `pending` and a follow-up `getParsed` call genuinely re-invokes the parser — `updated_at` advances and a fresh parse attempt runs, rather than an instant cached re-raise. `npx tsc --noEmit` passes; no frontend test suite exists in this repo to add a regression test to.

**Reasoning:** Not an architectural choice — restores the control flow the button's own label already implies, matching the #52/#53/#51 precedent for gap-filling fixes. Passing `status` through `onParse` (rather than re-deriving it from `documentId` alone, which can't distinguish "never parsed" from "failed") was the minimal signal `handleParse` needed to make the right call.

**Files changed:** `frontend/src/components/DocumentCard.tsx`, `frontend/src/pages/ProfileDetail.tsx`.

Related: issue #45.

---

*This document will be updated at periodic checkpoints as development continues.*
