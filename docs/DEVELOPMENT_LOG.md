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

**Action:** Created `docs/IMPLEMENTATION.md` with:
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

**Action:** Created `docs/USAGE.md` with:
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

*This document will be updated at periodic checkpoints as development continues.*
