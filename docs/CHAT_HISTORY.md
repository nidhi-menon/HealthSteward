# HealthSteward Development Chat History

This document captures the complete development conversation for the HealthSteward project, including questions, answers, options discussed, and decisions made.

**Last Updated:** 2026-02-15

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
| DEC-012 | Patient Disengagement / Action Items | Implemented (simple phase) | Post-AVS panel + overview section |

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

### Architecture Notes

- The localhost safety check on Ollama (`_check_localhost`) means the nudge logic must stay on the local machine — no external notification service can be called with raw medical data
- `FollowUp.timeframe` is free text — nudge logic uses heuristic parsing (look for month/week numbers)
- Post-AVS nudges fire at the highest-engagement moment: right after the patient has just reviewed and confirmed their parsed document

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

*This document will be updated at periodic checkpoints as development continues.*
