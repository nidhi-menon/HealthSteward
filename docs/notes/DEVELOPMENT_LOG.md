---

## 56. Pre-Apply Diff Preview for Parsed AVS Items (#46)

**Date:** 2026-08-07

**Context:** `apply_items` reconciled parsed AVS data against existing records by fuzzy-matching a name and then overwriting fields in place — `existing_cond.severity = dx.severity`, `existing_med.dosage = med.strength`. The only guard was `_is_newer(visit_dt, record.updated_at)`, which stops an *older* visit clobbering a newer record but does nothing about a genuinely newer visit carrying a mis-parsed value. With no history table anywhere in `src/data/models.py`, a bad parse applied cleanly and the previous value was simply gone. Since parsing runs through a local LLM over OCR'd text (DEC-010), "the parse was wrong" is a routine case, not an exotic one.

**Scope: option 1 (preview) only; option 2 (history/audit trail) deliberately deferred.** The issue offered both. A `changed_from`/`changed_at` pair or a dedicated history table is the same substrate #12 (append-only claim rows), #54 (regenerate history), and #97 (cross-source reconciliation) will each want, and picking its shape unilaterally here means designing it three times or migrating it once. Deferred to be designed once, across those issues. The preview alone converts a blind "Apply" into a reviewed one, which is the bulk of the protection.

**What changed:** the reconciliation decisions were pulled out of the mutation. `_build_apply_plan` is a read-only function returning a list of `_PlanEntry` — `{entity_type, action: create|update|skip, label, entity_id, reason, changes[]}` — where `changes` carries per-field `old_value → new_value` and `reason` records *why* something is skipped (`"the existing record is newer than this visit"`, `"already recorded"`). `apply_items` no longer decides anything; it calls `_build_apply_plan` and then `_execute_apply_plan`, which only writes. A new `POST /{document_id}/apply/preview` returns the same plan without committing.

**Preview/apply drift is the failure mode this design is built against.** Two endpoints that must agree about what will change is exactly the kind of pair that silently diverges. They share `_build_apply_plan`, and the response totals come from `_plan_totals` — one function, used by both — so `counts`/`skipped` cannot disagree by construction. `test_preview_and_apply_agree_on_the_same_input` pins that end to end.

**Stale-preview guard (repo owner's call on the issue):** the preview returns a `plan_fingerprint`, a digest over the plan *including the stored values it read*. Confirm sends it back as `expected_plan_fingerprint`; apply re-derives the plan and returns `409` with the fresh plan attached if the fingerprint moved. Because the digest covers old values, an edit to a targeted record in another tab invalidates the preview even when the actions themselves look identical. The field is optional at the API layer so existing callers keep working; the UI always sends it.

**One intentional behaviour change:** within-document duplicates are now deduped deterministically. Previously two items in the same AVS that matched each other each created their own row — unless a `_find_or_create_doctor` call happened to flush mid-loop, in which case the second was skipped. Plan building tracks what it has already planned to create, so the outcome no longer depends on flush timing. Duplicates now land as `skip` with reason "already included earlier in this document".

**Frontend:** the confirm modal in `ParsedItemsReview.tsx` previously listed the items being sent — which is not the same thing as what would change. It now fetches the plan and renders it grouped into "Will be changed" / "Will be added" / "Will be left alone", with `old → new` per field, following the `changedFields` pattern already in `ProfileDetail.tsx` rather than inventing another. Fields whose incoming value matches what is stored are counted but not listed, so the diff shows only real edits. Skipped-because-newer items are now visible, which they never were before. A refused apply swaps in the re-derived plan behind a "this profile changed while you were reviewing" banner instead of making the user start over.

**Tests:** `tests/test_documents_apply.py` (new, 15 tests). Ten are characterisation tests written against the *pre-refactor* code and confirmed passing before any of it moved — create/overwrite/skip-because-newer for conditions, the four medication paths including the deliberately-uncounted matched-start refresh, dedup skips, vitals, undated appointments, doctor matching. Five cover the preview: field-level diff without writing, skip reasons, preview/apply agreement, the stale-plan 409 and recovery, and backwards compatibility without a fingerprint. Full suite: 314 passed, 25 skipped (up from 299). Frontend `tsc -b && vite build` green.

**Drive-by:** `frontend/src/components/PostAvsActionPanel.tsx` had two unused type imports that failed `tsc -b` on `main`, so the frontend build was already red before this change. Fixed here because the build had to be green to verify the frontend work; it is a two-line change unrelated to #46.

**No DEC entry:** this makes an existing behaviour visible rather than choosing a new architecture. The history table, when it happens, is the DEC-worthy part.

**Files changed:** `src/api/documents.py`, `src/models/schemas.py`, `tests/test_documents_apply.py`, `frontend/src/api/client.ts`, `frontend/src/types/index.ts`, `frontend/src/components/ParsedItemsReview.tsx`, `frontend/src/components/PostAvsActionPanel.tsx`, `frontend/src/pages/ProfileDetail.tsx`, `docs/notes/DEVELOPMENT_LOG.md`.

Related: issue #46, issue #135 (FHIR import reuses this parse→preview→apply flow), issue #97 (reconciliation, deferred), issue #12, issue #54, DEC-010, DEC-031.

---

## 57. Pre-Visit "What to Bring" Checklist (#110)

**Date:** 2026-08-07

**Context:** #110 came out of a product-strategy discussion as a small, concrete friction point: people turn up without their insurance card, the referral paperwork, the imaging disc, or the pharmacy address, and the visit is worse for it. The issue's own scope note called for deterministic rules rather than an LLM — "deterministic is fine and cheaper here" — which holds up: the things people forget are the same things every time, so a rules table gets this right more predictably than a prompt, costs nothing to run, and doesn't touch the LLM boundary (DEC-006), the anonymization path, or any prompt. No `PROMPT_CHANGELOG.md` bump, no eval re-run.

**Fixed rules for v1, not user-editable** — the issue's own open question, confirmed by the repo owner on the issue. User-added items need a table, a migration, and CRUD UI, which turns a Small into a Medium; deferred rather than half-built.

**What changed:** `src/services/visit_checklist.py` (new) holds the rules as data — a specialty table, a purpose-keyword table, a first-visit set, and three baseline items — plus `build_checklist`, a pure function over facts the caller has already loaded. No DB access, no clock, no I/O, so the rules are directly unit-testable and the endpoint stays a thin query-and-render layer. `GET /api/profiles/{profile_id}/appointments/{appointment_id}/checklist` does the queries and returns the result. Computed per request: nothing is stored, there is no new table and no migration, and a referral closed this morning drops off the list by itself.

**Rule inputs, all from data that already exists:** `Doctor.specialty` (substring-matched, since it's free text — "Interventional Cardiology" still has to match the cardiology rule); whether any *completed* appointment with this doctor already exists; keyword matches on `Appointment.purpose`; whether the profile has active medications, allergies, or generated prep questions; and the count of unresolved `Referral`/`LabOrder` rows. That last pair are the most concrete items on the list precisely because they aren't guesses — the profile already knows the paperwork is outstanding.

**"First visit" means no *completed* earlier visit with that doctor, not no earlier row.** You can book three appointments before attending any of them; the first one you actually walk into is still a first visit as far as the front desk is concerned. `COMPLETED_STATUSES` in `src/api/action_items.py` was made public (from `_COMPLETED_STATUSES`) so "still outstanding" means the same thing in the checklist as it does in the action-items list, rather than being defined twice.

**Every item carries a `why`, and the rules that produced it.** The `why` is not decoration — a checklist that explains itself gets followed, and it lets someone judge whether a rule actually applies to them. `sources` records which rules fired (`specialty:orthoped`, `purpose:mri`, `open_referral`), so a surprising entry can be traced instead of taken on faith. Items dedupe by id with sources merged, so a rule firing twice reads as one item with two reasons.

**Known weak spot, tracked not buried:** there is no structured visit-type field, so visit-shape rules keyword-match free text and will miss phrasings they don't know. `test_an_unrecognised_purpose_adds_nothing` asserts the empty result for unrecognised wording, so the gap is visible in the suite rather than implied. Filed as **#144** (add a structured `visit_type` to `Appointment`) at the repo owner's request on the issue, rather than left as prose here.

**Deliberately generic where the data doesn't exist:** there are no insurance fields in the schema, so the item is "bring your insurance card", not "bring your Aetna card". Adding insurance data overlaps #102, a cost/claims feature deliberately not touched.

**Frontend:** `VisitChecklistCard.tsx` (new), rendered on `VisitPrep.tsx` for not-yet-completed visits only — a "what to bring" list has no use after the visit. Grouped by category with a remaining count. Tick-off state lives in `localStorage` keyed by appointment id, not the database: it's a scratchpad for one visit, not health data worth a table and a migration, and localStorage failures (private browsing, quota) are swallowed rather than surfaced as an error, since failing to remember a ticked box shouldn't take the card down. Placement note: #43 reworks `VisitPrep` into a before/after hub, so this card will want re-placing when that lands.

**Tests:** `tests/test_visit_checklist.py` (new, 15 tests), split by what's worth pinning — nine call `build_checklist` directly (empty profile produces an empty list, baseline items, first-visit set, substring specialty matching, purpose keywords, the unrecognised-purpose gap, counted paperwork, dedupe-with-merged-sources, determinism), six exercise the endpoint (specialty and purpose read correctly, scheduled-vs-completed first-visit logic, resolved items excluded, active-vs-stopped medications, no-doctor appointments, 404s). Full suite: 314 passed, 25 skipped (up from 299).

**No DEC entry:** a rules table is not an architectural or technology choice. Flagged as such on the issue and not objected to.

**Files changed:** `src/services/visit_checklist.py`, `src/api/appointments.py`, `src/api/action_items.py`, `src/models/schemas.py`, `tests/test_visit_checklist.py`, `frontend/src/components/VisitChecklistCard.tsx`, `frontend/src/pages/VisitPrep.tsx`, `frontend/src/api/client.ts`, `frontend/src/types/index.ts`, `frontend/src/components/PostAvsActionPanel.tsx`, `docs/notes/DEVELOPMENT_LOG.md`.

Related: issue #110, issue #144 (visit_type follow-up), issue #43 (Visit Prep rework — placement), issue #102 (insurance/cost data, not touched), DEC-006, DEC-027.

---
<<<<<<< HEAD

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

## 33. Surfaced LLM Backend Failure to the User (#47, DEC-020)

**Date:** 2026-07-20

**Context:** Picked up issue #47 next. When the configured LLM backend fails entirely (unreachable/misconfigured Ollama URL, or any failure surviving both the agentic loop and its single-shot fallback), `VisitPrepAgent._get_fallback_response()` returns hardcoded generic placeholder questions, but `prepare_visit` never raises past that point — the frontend got a normal 200 response and the existing "Failed to generate questions" error banner never fired, since nothing errored from its perspective. Silent success with useless content, with no trace beyond a backend log line.

**What was built:**
- `VisitPrep.used_fallback: bool` (`src/data/models.py`), migration `73a1532778f1` (`add_used_fallback_to_visit_preps`) — checked by hand against a copy of the dev DB (upgrade, downgrade, re-upgrade all applied cleanly). Had to hand-fix the autogenerated migration twice: it included a spurious, unrelated `appointments.id` NOT NULL alter (SQLite PK-column reflection noise, removed from both directions), and the column needed `server_default='0'` to backfill existing rows before dropping the server default so the ORM's Python-side default governs new rows.
- `VisitPrepAgent.prepare_visit`'s return dict now carries `used_fallback`: `True` only from `_get_fallback_response()`'s outer-exception path, `False` everywhere else — including the DEC-009/013 agentic-loop-doesn't-converge single-shot fallback, which is real LLM output, not a failure. Persisted on both create and update in `src/api/visits.py`; exposed via `VisitPrepResponse` (`src/models/schemas.py`).
- `VisitPrep.tsx` shows an amber warning banner ("Couldn't reach your configured AI backend... Check your Settings and regenerate") when `used_fallback` is true, styled to match `ParsedItemsReview.tsx`'s existing edit-count banner rather than inventing a new visual pattern.
- Regression tests: `test_prepare_visit_surfaces_used_fallback_when_backend_fails_entirely` (new) forces both the agentic loop and single-shot calls to fail and asserts `used_fallback: True` reaches the API response; added an assertion to the existing `test_prepare_visit_falls_back_when_agentic_loop_does_not_converge` confirming `used_fallback` stays `False` there, since that's a real single-shot generation succeeding, not issue #47's failure case.
- Verified `npx tsc --noEmit` and `npx vite build` both pass with the new banner/type.

**Reasoning:** See DEC-020 for the full options analysis. Persisting the flag (vs. an ephemeral POST-only field) was the deliberate call — a user reopening the Visit Prep page after a failed generation should still see the warning, not just at the moment of the original request.

**Files changed:** `src/data/models.py`, `alembic/versions/73a1532778f1_add_used_fallback_to_visit_preps.py`, `src/agents/visit_prep.py`, `src/api/visits.py`, `src/models/schemas.py`, `frontend/src/types/index.ts`, `frontend/src/pages/VisitPrep.tsx`, `tests/test_visit_prep.py`, `docs/notes/DECISIONS.md`.

Related: issue #47, DEC-020, DEC-009, DEC-013.

---

## 34. Test-Only Fix: Three `test_visit_prep.py` Tests Weren't Actually Exercising Their Mocked Claude Client (#79)

**Date:** 2026-07-20

**Context:** Self-filed follow-up from #51's work — `test_prepare_visit`, `test_get_visit_prep`, and `test_prepare_visit_with_additional_concerns` (`tests/test_visit_prep.py`) patch `AsyncAnthropic` to mock a Claude response, matching the module's own docstring, but never forced `Settings.llm_provider` away from whatever the dev machine's `.env` has it set to (`ollama` by default per DEC-016). `get_llm_backend()` dispatches on `settings.llm_provider`, not on which client happens to be patched, so on a machine with `.env`'s checked-in `LLM_PROVIDER=ollama` default, these three tests actually constructed `OllamaBackend` and hit a real/unreachable local Ollama server, timing out and falling through to the single-shot fallback — never touching the mocked Claude client. They still passed, since none asserted content tied to the mock, only response shape.

**What was built:**
- Added `monkeypatch.setattr(get_settings(), "llm_provider", "claude")` to all three tests, matching the pattern already used correctly by `test_prepare_visit_agentic_tool_use` and others.
- Added a content assertion to each (`data["generated_questions"] == {...}` matching the mock's exact response, plus `mock_client.messages.create.called` on one) so a future regression of this same kind fails loudly instead of silently passing via a fallback path.
- Confirmed the fix mattered rather than just being cosmetic: `tests/test_visit_prep.py` dropped from several minutes (real Ollama wall-clock timeouts, per `_TOTAL_CALL_TIMEOUT_SECONDS`) to under 1 second; the full backend suite (126 tests) dropped from ~150-600s across every run this session to 1.36s.

**Reasoning:** Not an architectural choice — test-only fix restoring the isolation the mocking setup already implied. The dramatic runtime drop is itself the confirmation: these three tests were the majority of this session's repeated multi-minute `pytest` waits, silently caused by a real network dependency the test suite was never supposed to have.

**Files changed:** `tests/test_visit_prep.py`.

Related: issue #79, issue #51.

---

## 35. Snoozed Action Items Made Recoverable and Visible (#44)

**Date:** 2026-07-21

**Context:** Picked up issue #44. Every action-items endpoint (`src/api/action_items.py`) excluded snoozed items entirely rather than flagging them — `_snoozed_item_ids`/`_is_active` filtered them out of every list, so a snooze pill click removed an item from view immediately with no confirmation, no way to see what was currently snoozed or until when, and no undo. "Snooze" behaved like a silent, permanent delete rather than something temporary and reversible.

**What was built:**
- **Backend** (`src/api/action_items.py`): refactored vitals-alert computation into `_compute_all_vitals_alerts` (trend message for every metric, snoozed or not), so the same real trend text can be shown for a currently-snoozed vitals alert instead of just its bare metric name. Added `GET /snoozed-items` — a single unified view across both snooze mechanisms in this codebase: `NudgeState`-backed computed nudges (past-due, upcoming-without-prep, completed-without-AVS, vitals-alert) and the three model rows with their own `snoozed_until` column (FollowUp, LabOrder, Referral) — each resolved to a human-readable label (appointment → doctor name + date via a join; vitals → the real trend message; the three model rows → their existing description/test_name/specialty fields). Added `DELETE /nudge-states/{nudge_type}/{item_id}` to un-snooze a computed nudge early, since `NudgeState.snoozed_until` is `NOT NULL` (unlike the three model columns, which already supported un-snoozing via the existing `snoozed_until: null` PATCH path) — deleting the row is the only way to represent "not snoozed" for that table.
- **Frontend** (`ActionItemsSection.tsx`): a "Show snoozed" toggle (matching the existing "Show resolved" pattern) revealing `SnoozedItemsList`, with an "Un-snooze now" button per item. An undo banner appears for 8 seconds after any snooze action (all 7 snooze call sites now pass a per-call `onSuccess` to `.mutate()`), reusing the same unified `unsnoozeMutation` that dispatches to either the new DELETE endpoint or the existing null-out PATCH depending on category.
- New `tests/test_action_items.py` — this file had zero test coverage before this PR (a pre-existing gap, not introduced here). Covers: snoozed follow-up excluded from the active list and visible in `/snoozed-items`, then reappearing after un-snooze; lab-order/referral labels; a `past_due` nudge's label correctly resolving through the appointment→doctor join, and un-snoozing it via the new DELETE endpoint; 404 on deleting a non-existent snooze.
- No schema/migration change — purely additive filtering/display, as scoped in the issue.
- Manually verified the exact API sequence the frontend calls (snooze → confirm excluded from active list → confirm visible in `/snoozed-items` with the correct resolved label → un-snooze via DELETE → confirm it's back in the active list and gone from `/snoozed-items`) against a live `uvicorn` instance with real profile/doctor/appointment data. Browser-tooling wasn't available this session, so the actual click-through UI wasn't visually verified — `npx tsc --noEmit` and `npx vite build` both pass, and this API-level verification covers the same request/response contract the UI calls.
- Incidental fix while testing manually: the dev DB (`data/healthsteward.db`) hadn't had DEC-020's `used_fallback` migration applied yet (unrelated pre-existing gap, surfaced by hitting a stale endpoint) — ran `alembic upgrade head` against it.

**Reasoning:** Not an architectural choice — matches the issue's own framing as small/additive, inverting an existing filter into a second view rather than changing the underlying snooze mechanism. Keeping computed-nudge un-snooze as a row deletion (rather than adding a nullable-relaxation migration to `NudgeState.snoozed_until`) avoided a schema change for a purely additive feature.

**Files changed:** `src/api/action_items.py`, `frontend/src/components/ActionItemsSection.tsx`, `frontend/src/api/client.ts`, `frontend/src/types/index.ts`, `tests/test_action_items.py`.

Related: issue #44.

---

## 36. Ollama Auto-Discovery on Settings Page (#48, DEC-021)

**Date:** 2026-07-21

**Context:** Picked up issue #48 next. The Settings page's Ollama Base URL field was a plain text input with no help finding the right value, even though it's almost always `localhost:11434` in practice for this app's single-machine target use case. The issue posed two open questions up front: whether discovery should run automatically or only on request, and how to keep the candidate list easy to extend — both resolved and recorded in DEC-021.

**What was built:**
- `src/utils/ollama_discovery.py` — `CANDIDATE_OLLAMA_URLS` (a flat, ordered list: localhost, 127.0.0.1, host.docker.internal, Docker's default bridge gateway), `probe_ollama_url()` (health-check via `/api/tags`, matching `OllamaClient.is_available()`'s existing pattern, 1.5s timeout), `discover_ollama_url()` (first responding candidate, or `None`).
- `GET /api/settings/discover-ollama` (`src/api/settings.py`) — new `OllamaDiscoveryResponse` schema (`found`, `base_url`, `candidates_tried`).
- `Settings.tsx`: a "Detect" button next to the Base URL field (explicit-only, per DEC-021 — never auto-runs on page load) that auto-fills the field on success, or shows `OllamaDiscoveryGuide` — an in-UI panel with copy-pasteable next steps for the three non-default cases from the issue (different machine, different port, Docker) — when nothing responds. The auto-filled value isn't auto-saved; the user still confirms via the existing Save button.
- Regression tests: `tests/test_ollama_discovery.py` (7 tests) covering `probe_ollama_url`'s true/false/error paths, `discover_ollama_url` returning the first responding candidate or `None`, and the route's found/not-found responses (mocked, no real network calls in the test suite).
- Verified against a live `uvicorn` instance: `GET /api/settings/discover-ollama` correctly found this dev machine's real running Ollama instance at `localhost:11434`. `npx tsc --noEmit` and `npx vite build` both pass. Browser tooling wasn't available this session, so the actual click-through UI (Detect button, guide panel) wasn't visually verified — this covers the same request/response contract the UI calls.

**Reasoning:** See DEC-021 for the full analysis. Explicit-only discovery was the deliberate call — auto-probing on every Settings page visit would be a small but real departure from the project's local-first, privacy-first positioning, for a feature whose only job is convenience.

**Files changed:** `src/utils/ollama_discovery.py`, `src/api/settings.py`, `src/models/schemas.py`, `frontend/src/pages/Settings.tsx`, `frontend/src/api/client.ts`, `frontend/src/types/index.ts`, `tests/test_ollama_discovery.py`, `docs/notes/DECISIONS.md`.

Related: issue #48, DEC-021.

---

## 37. Enforced Retrieval Non-Redundancy Between Context Selection and `lookup_past_visits` (DEC-023, DEC-024)

**Date:** 2026-07-22

**Context:** While walking through the System Design diagram, a question surfaced about why context selection (DEC-008) runs as a separate deterministic pipeline instead of being folded into the agentic loop as just another tool call — that rationale had never actually been written down anywhere, so it got documented retroactively as DEC-023. That writeup claimed context selection and `lookup_past_visits` were "intentionally complementary, non-overlapping layers," backed by `eval/scorers.py::score_retrieval_redundancy` checking for overlap between them. Checking that claim against the actual code found it was only half true: the eval scorer's own docstring called it "Observational" — it measured redundant re-fetching after the fact, but nothing in `src/agents/tools.py` or `src/agents/visit_prep.py` actually prevented it. `lookup_past_visits` queried all completed appointments for a profile with no awareness of what DEC-008's pipeline had already selected into the base prompt.

**What was built:**
- `ContextSelectionResult.selected_visit_ids: list[str]` (`src/utils/context_selection.py`) — the pre-anonymization `Appointment.id`s for `selected_visits`, populated at the same point Stage 4 anonymizes them (the id was already in scope there; it just wasn't being kept).
- Threaded through `VisitPrepAgent._run_agentic_loop`'s new `exclude_appointment_ids` param (`src/agents/visit_prep.py`) into `VisitPrepTools.__init__` (`src/agents/tools.py`), which now filters `_lookup_past_visits`'s query with `Appointment.id.notin_(...)` — redundant re-fetching is now impossible at the SQL level, not just discouraged.
- Updated `eval/scorers.py::score_retrieval_redundancy`'s docstring: overlap is now a regression signal (the exclusion filter broke) rather than a quality-tuning signal (the model chose to re-fetch).
- Added `tests/test_agent_tools.py::test_lookup_past_visits_excludes_context_selection_visits`.
- Also updated the System Design diagram (`docs/tdd.html`): expanded the "Select" phase's collapsed "Context selection / 4-stage pipeline" node into its actual four sub-steps (SQLite → Rules filter → Ollama scoring → Token budget, stacked vertically), then wrapped Select and Anonymize together in a labeled `.arch-boundary` reading "4-stage context selection pipeline" — since Anonymize is stage 4 of the same pipeline, not a separate step, which the original two-box layout obscured.

**Reasoning:** Didn't cross the anonymization trust boundary (DEC-006) — the exclusion list is derived from real appointment ids before anonymization, but is only ever used as a SQL filter inside the tool executor, never rendered into anything the LLM sees. See DEC-023 for why context selection is a separate deterministic step at all, and DEC-024 for the enforcement decision itself.

**Files changed:** `src/utils/context_selection.py`, `src/agents/visit_prep.py`, `src/agents/tools.py`, `eval/scorers.py`, `tests/test_agent_tools.py`, `docs/tdd.html`, `docs/notes/DECISIONS.md`.

Related: DEC-023, DEC-024.

---

## 38. Expose `Appointment.prep_notes` to Visit Prep (Base Context and `lookup_past_visits`)

**Date:** 2026-07-22

**Context:** While auditing what `lookup_past_visits` actually returns, found that `Appointment.prep_notes` ("notes before the visit — concerns, questions to ask") was invisible to visit prep entirely — both in the base context built by `context_selection.py` and in the `lookup_past_visits` tool's output — even though `visit_notes` ("during/after — what was discussed, outcomes") was already included in both places. `AnonymizedAppointment` (`src/utils/anonymization.py`) simply had no field for it. Practically, this meant the agent could never reason about continuity like "did the concern the patient meant to raise last time actually get addressed" — it only ever saw what was discussed, never what was intended to be discussed.

**What was built:**
- Added `prep_notes: Optional[str]` to `AnonymizedAppointment`, anonymized the same way as `visit_notes` in `Anonymizer.anonymize_appointment`.
- Rendered as `Planned to discuss: ...` in both `_build_anonymized_context`'s past-visits section (`src/agents/visit_prep.py`) and `lookup_past_visits`'s tool output (`src/agents/tools.py`), alongside the existing `Purpose:`/`Notes:` lines.
- Added `tests/test_anonymization.py::TestAnonymizeAppointment::test_anonymize_appointment_includes_prep_notes`, confirming it's anonymized (not just passed through raw) and doesn't silently collide with `visit_notes`.
- Deliberately scoped to *exposure* only — did not touch the system prompt to instruct the model to actually reason about carryover ("was this addressed last time"), since that's a wording change subject to the project's prompt-versioning discipline and needs separate review before landing.

**Reasoning:** Pure data-exposure fix, not a new capability or a new tool — the data already existed on `Appointment`, the anonymization dataclass just never carried it through. Kept as a standalone step specifically so the still-unwritten prompt change to make the agent reason about it can be reviewed and versioned on its own, rather than bundling a data-shape change with a prompt-wording change in one commit.

**Files changed:** `src/utils/anonymization.py`, `src/agents/visit_prep.py`, `src/agents/tools.py`, `tests/test_anonymization.py`.

Related: DEC-015 (visit-prep tool scope).

---

## 39. Prompt v4: Instruct the Model to Surface `prep_notes`/`visit_notes` Carryover

**Date:** 2026-07-22

**Context:** Follow-up to #38 above — with `prep_notes` now exposed to the model, added the actual instruction to compare it against `visit_notes` and surface a question when something planned was never shown as addressed. Drafted wording for review before touching the versioned prompt, then applied it once approved.

**What was built:**
- `SYSTEM_PROMPT_TEMPLATE_VERSION`/`SYSTEM_PROMPT_GENERIC_VERSION` bumped v3-2026-07-19 → v4-2026-07-22 (`src/agents/visit_prep.py`).
- One new rule in both prompts' `IMPORTANT RULES`, scoped to only fire when both fields are present and the second is silent on the topic (not when notes are missing/sparse generally) — kept inside the existing "only assert what's grounded" discipline rather than inventing carryover.
- "Follow-up Planning"'s category description extended to explicitly include carryover concerns, so they land in an existing category rather than needing a new one.
- Full `PROMPT_CHANGELOG.md` entry per the project's versioning convention.

**What didn't happen:** attempted a real before/after eval comparison per that same convention (`python -m eval.run`), but the baseline run itself failed — every one of 5 generation cases timed out on the 150s `_TOTAL_CALL_TIMEOUT_SECONDS` (`llm_backend.py:24`) on both the agentic loop and the single-shot fallback, landing on the outer generic-fallback response for all 5 (`grounded_rate=0.0`/`format_valid=False` across the board — "nothing generated," not a real quality signal). `llama3.2:latest` was confirmed pulled; Ollama's `llama-server` process was genuinely computing (~10 min CPU observed) rather than hung — looks like resource contention from four pulled models (`medgemma`, `llama3.2`, `qwen2.5`, `llama3.1`) competing for this 8GB M3's memory/CPU, not a code or prompt defect. Rather than fabricate a "no regression" conclusion from a run where nothing actually generated, landed the prompt change with eval evidence explicitly marked pending in the changelog, and filed [issue #89](https://github.com/nidhi-menon/HealthSteward/issues/89) to re-run once Ollama can reliably complete calls within timeout.

**Reasoning:** User's explicit call, given a live choice between deferring eval, retrying with a longer timeout, or reverting the prompt change outright — chose to land the (self-contained, narrowly-scoped, low-hallucination-risk-by-construction) prompt change now and close the eval gap separately, rather than block on infra that's flaky on this specific dev machine right now.

**Files changed:** `src/agents/visit_prep.py`, `docs/notes/PROMPT_CHANGELOG.md`.

Related: #38, DEC-015, issue #89.

---

## 40. Harden `PII_PATTERNS` Against Common Real-World PII Shapes

**Date:** 2026-08-03

**Context:** `PII_PATTERNS` (`src/utils/anonymization.py`) was 5 hand-authored regexes guarding DEC-006's anonymization boundary — everything free-text that reaches an external LLM provider passes through them. Issue #73 flagged the list as narrower than the "best-effort" language in README/CONTRIBUTING implies. Started by writing a throwaway audit harness over ~44 candidate strings (plausible PII shapes on one side, realistic clinical text on the other) to find out what actually leaked rather than guessing: **23 shapes passed through completely unredacted**, and 2 more were partially redacted, which is its own leak — an international number kept "+44 20 7" and a ZIP+4 kept "94", because `phone`'s 7-digit branch consumed the tail before the more specific pattern ran.

**What was built:**
- Added 6 patterns: `phone_intl` (E.164-style `+` numbers), `zip_code` (ZIP+4 and state-qualified ZIPs), `date_iso`, `date_written` (both month orderings, abbreviated months), `po_box`, `mrn`, `insurance_id`.
- Widened 2 existing patterns: `address` grew from 9 street suffixes to ~30 (spelled-out plus USPS abbreviations) and now absorbs a trailing apartment/unit/suite designator so the unit number isn't left dangling after the street is redacted; `date` now covers day-first ordering and 2-digit years, not just MM/DD/YYYY.
- Introduced `PII_REPLACEMENTS`, a per-pattern replacement-template map (defaulting to whole-match redaction). Label-anchored patterns use it to keep their label, so text reads `MRN: [REDACTED]` rather than losing the clinical context along with the identifier.
- Reordered `PII_PATTERNS` so `zip_code`/`phone_intl` precede `phone`, and documented that the ordering is load-bearing — a future reorder would silently reintroduce partial-redaction leaks.
- 41 new test cases in `tests/test_anonymization.py` (`TestHardenedPIIPatterns`). Verified they're real coverage by stashing the source change and confirming all 41 fail against the pre-change module.
- Suite: 140 → 181 tests, all passing.

**Reasoning:** Scoped to hardening the existing list rather than adopting Presidio/`scrubadub` — the repo owner's explicit written call on the issue; library adoption is tracked separately as #92. The binding constraint throughout was over-redaction, not coverage: this runs on clinical free text where dose ranges, BP ratios, and fractions are all date- or identifier-shaped, so every widened pattern is paired with negative cases asserting clinical content survives, and several tempting patterns (bare 5-digit ZIP, bare month+year, street suffixes like Park/Point/Row) were deliberately left out because the false-positive cost exceeds the privacy gain. MRN and insurance IDs are label-anchored for the same reason — an unanchored long-digit-run pattern would eat platelet counts and lab values. The accepted consequence is that an unlabeled MRN in bare free text still isn't caught; anonymization here stays best-effort by construction.

**Files changed:** `src/utils/anonymization.py`, `tests/test_anonymization.py`, `docs/notes/DECISIONS.md`.

Related: issue #73, issue #92, DEC-006, DEC-025.
## 41. Make `avs_parser_model` Runtime-Configurable, Matching `ollama_model`

**Date:** 2026-08-03

**Context:** DEC-016 made `ollama_model` runtime-editable — an `AppSettings` column, overlaid on the env default, exposed via `GET`/`PUT /api/settings` and the Settings page, switchable without a restart. `avs_parser_model` (`src/config.py`, default `qwen2.5:7b`) never got the same treatment: it was a static config default, absent from `.env.example` entirely, with no DB overlay and no UI. Changing the AVS parser's model meant editing source and restarting; changing the agentic loop's model was a text field in Settings. Issue #59.

**What was built:**
- `avs_parser_model` column on `AppSettings` (`src/data/models.py`) + migration `b7c4e2a91d38`, nullable with no server default — NULL means "fall back to the env default", matching every other overlay column, so existing rows need no backfill.
- Added to `_OVERLAY_FIELDS` (`settings_service.py`), `AppSettingsUpdate`/`AppSettingsResponse` (`schemas.py`), and both `/api/settings` handlers.
- Frontend: `AppSettings`/`AppSettingsUpdate` types, and a new always-visible **Document Parsing** card on the Settings page.
- `AVS_PARSER_MODEL` added to `.env.example` (was missing entirely).
- 5 new tests in `tests/test_settings_api.py`. Suite 140 → 145.

**Two things worth calling out, because neither is in the issue's step list:**

1. **The overlay wasn't reachable from the parse path.** `parse_avs_pdf` resolves its model via `get_settings().avs_parser_model` — the *env* settings, not the DB-overlaid ones — and runs in a thread executor where an async DB session isn't available. Following the issue's 5 steps literally would have produced a Settings field that persists correctly, round-trips correctly through the API, and is never actually read by the parser. `src/api/documents.py` now resolves the effective settings before dispatching to the executor and passes the model explicitly.
2. **The Settings field is deliberately not in the Ollama card.** The issue proposed "same section as the existing Ollama config", but that card renders only when `provider === 'ollama'`. AVS parsing always runs on local Ollama regardless of which provider generates visit prep, so nesting the field there would hide it from Claude and custom-provider users while the setting stayed in effect for them. It lives in its own always-visible card instead, with a test (`test_avs_parser_model_override_survives_provider_switch`) pinning the behavior that motivated the split.

**Reasoning:** Free-text field rather than a curated dropdown, per the repo owner's call on the issue — a vetted-model list doesn't exist yet and isn't worth inventing here; a dropdown can layer onto the same field later. Scoped to configurability plumbing only: the `qwen2.5:7b` default itself is unchanged and `src/parsers/agent/prompts.py` was not re-validated against alternative models, so no DEC entry is warranted (a DEC would be needed only if the default choice changed). The rationale-for-the-default question folds into #91 per the owner rather than becoming a new issue.

**Files changed:** `src/data/models.py`, `src/services/settings_service.py`, `src/models/schemas.py`, `src/api/settings.py`, `src/api/documents.py`, `alembic/versions/b7c4e2a91d38_add_avs_parser_model_to_app_settings.py`, `frontend/src/types/index.ts`, `frontend/src/pages/Settings.tsx`, `.env.example`, `tests/test_settings_api.py`.

Related: issue #59, issue #91, DEC-016.
## 42. Default `lookup_past_visits` to "Since the Last Visit With This Provider"

**Date:** 2026-08-03

**Context:** `lookup_past_visits` (`src/agents/tools.py`) filtered by `specialty`/`keyword` but had no date bound at all — called with no arguments, it returned every completed visit the patient had ever had, capped only by the `[:10]` slice at render time. For visit prep the useful question is narrower: *what's happened since I last saw this provider*, across all providers. Issue #21, a DEC-015 follow-up.

**What was built:**
- `VisitPrepTools` gained `target_doctor_id` and `current_appointment_id`. When `lookup_past_visits` is called with neither `specialty` nor `keyword`, it resolves the patient's most recent completed visit with the target provider and filters `scheduled_date >= that date` (inclusive, per the issue).
- No prior completed visit with that provider — or no doctor on the appointment at all — falls back to the previous unbounded behavior, per the issue's own note, rather than inventing a 12-month default.
- `visit_prep.py` threads both values through `_run_agentic_loop` into the tool executor.
- Tool description updated so the model knows what the no-argument call now returns, and that an explicit filter is what widens the search back to full history. Introduced `TOOL_SPECS_VERSION` and a `PROMPT_CHANGELOG.md` section for it.
- 10 new tests in `tests/test_agent_tools.py`. Suite 140 → 150.

**Three decisions inside the implementation worth recording:**

1. **The anchor query deliberately ignores `exclude_appointment_ids`.** That list (DEC-024) exists to stop the tool re-surfacing visits already in the prompt — but an excluded visit is still a real visit, and still the correct anchor for "what's happened since." Anchoring off the filtered set would silently widen the window precisely when the anchor had already been selected into context, which is the common case: the last visit with this provider is exactly what context selection tends to pick. Pinned by `test_window_composes_with_exclude_appointment_ids`.
2. **The appointment being prepped is excluded from the anchor query.** Prep can be re-run on an already-completed appointment, in which case it would otherwise anchor to its own date and window out the entire history it's asking about. This mirrors the `Appointment.id != current_appointment_id` guard `_get_past_appointments` already carries for the same reason.
3. **The window applies only when neither filter is supplied.** The issue's first sentence conditions the window on "no explicit specialty/keyword args," while a later sentence asks for the filters to stay "composable on top of that window" — mildly contradictory. Read the first literally: an explicit filter signals a targeted question, and bounding a `specialty="Cardiology"` lookup to "since I last saw my endocrinologist" would hide the older cardiology history the model was reaching for. Flagged on the PR.

**Reasoning:** Tool-layer only, no schema change, matching the issue's own scoping. The new constructor arguments are optional and default to the previous behavior, so nothing that builds `VisitPrepTools` without them changes — covered by `test_backwards_compatible_when_no_window_args_supplied`. Only `status == "completed"` visits anchor the window; a cancelled appointment isn't a visit, which has its own test since it would otherwise be an easy silent bug.

**Files changed:** `src/agents/tools.py`, `src/agents/visit_prep.py`, `tests/test_agent_tools.py`, `docs/notes/PROMPT_CHANGELOG.md`.

Related: issue #21, DEC-015, DEC-023, DEC-024, issue #89 (eval blocked).
## 43. Allow Editing and Saving Visit Prep Questions

**Date:** 2026-08-03

**Context:** Visit prep was generate-only. `POST /api/visits/{id}/prepare` re-ran the whole agent and replaced `generated_questions`/`context_summary` wholesale; there was no way to touch the output otherwise. Since this is content the patient carries into a real appointment, an AI question that's slightly off — wrong wording, an angle that doesn't apply, a missing concern of their own — meant either living with it or rolling the dice on a full regeneration. Issue #14.

**What was built:**
- `PATCH /api/visits/{appointment_id}/prep` (`src/api/visits.py`) with a new `VisitPrepUpdate` schema. Both fields optional and applied via `exclude_unset`, so a client can save just the questions or just the summary.
- Frontend edit mode on `VisitPrep.tsx`: an Edit button beside the questions heading swaps each category card's rendered list for a textarea (one question per line) and the summary for a textarea, with Save/Cancel replacing Regenerate while editing.
- 10 new tests in `tests/test_visit_prep.py`. Suite 140 → 150.

**Design notes:**

1. **Newline-delimited textarea per category, not per-question widgets.** The issue asks for three things — reword a question, add one of your own, drop one that doesn't apply. All three are just line edits, and this needs no change to `generated_questions`' `{category: [question, ...]}` shape, confirming the assumption flagged when the issue was picked up. Blank lines are filtered on save (that's how a question gets deleted), and a category emptied entirely is dropped rather than persisting a heading with nothing under it.
2. **`generated_questions` is typed `dict[str, list[str]]` on the update schema**, unlike the bare `dict` on `VisitPrepResponse`. The response has to accept whatever generation produced; this endpoint is user-writable and the frontend renders every value as a list of strings, so accepting arbitrary JSON would let a malformed save break the page that has to display it. A bad shape is a 422 and the stored prep is untouched.
3. **`exclude_unset`, not `exclude_none`.** An omitted field means "leave it alone"; an explicit null means "clear it". Collapsing them would make it impossible to clear a context summary.
4. **Edit-only — PATCH will not create a prep.** Editing an appointment with no prep is a 404; silently creating one would hide a client bug.
5. **`used_fallback` is cleared on edit (amended during PR review).** It drives the "these are generic default questions, not personalized — regenerate" banner (issue #47). Initially left as-is on the theory that it records how the prep was *generated*, and editing afterwards doesn't change that history — but the repo owner judged that once the patient has hand-edited the content, that warning is no longer true and reads as wrong over text they just wrote. `PATCH` now sets `used_fallback = False` on any edit, regardless of the original value; `test_patch_prep_clears_used_fallback` covers it.
6. **No draft/unsaved-confirm step**, per the repo owner's own resolved comment on the issue: once editing exists, a bad generation is as fixable by editing as by blocking the save.
7. **Regenerate still replaces wholesale**, so edits are lost by design — pinned by `test_regenerate_after_edit_replaces_edits` so a future change to that is deliberate rather than accidental.

**Also:** removed an unused `refetchAppointment` binding in `VisitPrep.tsx` that `tsc -b` was failing on. Pre-existing, but in a file this change rewrites heavily. Two further pre-existing `tsc` errors in `PostAvsActionPanel.tsx` were left alone as an unrelated file.

**Files changed:** `src/api/visits.py`, `src/models/schemas.py`, `frontend/src/pages/VisitPrep.tsx`, `frontend/src/api/client.ts`, `frontend/src/types/index.ts`, `tests/test_visit_prep.py`.

Related: issue #14, issue #47.

---

## 44. Surfaced the Agentic-Loop Fallback Rate (#30, DEC-026)

**Date:** 2026-08-04

**Context:** DEC-013's agentic loop falls back to single-shot generation rather than failing — the right call for the patient, but it meant a backend that stopped doing reliable tool use would degrade the app silently. `prepare_visit()` logged a `logger.warning` and moved on; nothing was readable back through the app. `DESIGN.md` §8 listed this as one of three remaining real gaps. Issue #30.

**What was built:**
- Per-run diagnostics on every `prepare_visit()` run, stored as `ConversationLog.extra_data["run_diagnostics"]` = `{"agentic_path": bool, "fallback_reason": str | None}` (`src/agents/base.py`'s `_log_conversation` gained a `run_diagnostics` param; `src/agents/visit_prep.py` threads the reason through).
- `AgenticLoopNotConvergedError(RuntimeError)` and `_classify_agentic_failure()`, so turn exhaustion is distinguishable from a backend error — previously both were a bare `RuntimeError` caught by the same handler.
- `_log_hard_failure()`, covering the case where both paths fail and there is no response to log at all.
- `GET /api/diagnostics/visit-prep-fallback?limit=N` (`src/api/diagnostics.py`, new router) returning runs considered, agentic vs. fallback counts, the rate, hard failures, and a per-reason breakdown over a rolling window.
- 11 new tests in `tests/test_diagnostics.py` — one per fallback reason plus endpoint aggregation. Suite 233 → 244.

**Design notes:**

1. **No migration.** `extra_data` is an existing JSON column already carrying `system` / `model` / `prompt_version` / `tool_calls`; the repo owner picked it over a dedicated counter table on the issue. See DEC-026 for the full tradeoff.
2. **`used_fallback` was deliberately left alone.** The name collides, but DEC-020's flag means "the model produced nothing, these are placeholders" and drives a user-facing warning. An agentic → single-shot fallback still returns a real personalized answer; reusing the flag would warn the patient that good questions are generic ones.
3. **Reasons are an enum, not free text**, and a hard failure records both `backend_unavailable` and the `prior_agentic_failure` that preceded it — a backend breaking tool use on its way down would otherwise look like a plain outage.
4. **Rolling window, not an all-time rate.** The operative question is "is tool use working *now*"; an all-time average is slow to move once a backend starts failing.
5. **Not admin-gated, because there is no auth to gate on.** The issue asked for an "admin-only" endpoint; this app has no authentication anywhere (`/api/settings` exposes and accepts API keys unauthenticated today), so this is a plain endpoint on a localhost-only app. Flagged for review rather than inventing an auth scheme here.
6. **`json_extract` in the query** filters to rows that actually carry diagnostics, so `limit` means "the last N visit-prep runs" rather than "whatever survives filtering the last N assistant rows." SQLite-specific; noted in the code as the line to change if the DB ever moves.

**Also:** updated `DESIGN.md` §8's "no visibility into agentic-loop fallback rate" bullet, which this makes untrue — struck through with a pointer to DEC-026 rather than deleted, since the weaker residual gap (nothing *alerts*, someone has to look) is still real.

**Files changed:** `src/agents/visit_prep.py`, `src/agents/base.py`, `src/api/diagnostics.py`, `src/main.py`, `src/models/schemas.py`, `tests/test_diagnostics.py`, `docs/notes/DECISIONS.md`, `docs/notes/DESIGN.md`.

Related: issue #30, DEC-009, DEC-013, DEC-020, DEC-026, `DESIGN.md` §8.

---

## 45. Soft-Delete Profiles with a 30-Day Recovery Window (#50, DEC-027)

**Date:** 2026-08-04

**Context:** Deleting a profile was immediate and permanent, cascading through every related table. The type-to-confirm modal is a high bar, but nothing existed on the other side of it — a mis-aimed confirmation destroyed months or years of caregiver-entered history with no undo. Issue #50.

**What was built:**
- Nullable `HealthProfile.deleted_at` (`src/data/models.py`) + Alembic migration `c8f2b41d7e93`.
- `DELETE /api/profiles/{id}` sets `deleted_at` instead of deleting; `GET /api/profiles/deleted` lists soft-deleted profiles with `expires_at`/`days_remaining`; `POST /api/profiles/{id}/restore` clears the field.
- `get_live_profile_or_404()` and `purge_expired_profiles()` (`src/api/health_profile.py`); the four child routers' `verify_profile_exists` now filter `deleted_at IS NULL` too.
- Frontend: a collapsible "Recently deleted (n)" section on `ProfileList.tsx` with per-profile time remaining and a Restore button; `DeleteConfirmModal` gained an optional `recoveryDays` prop so its warning stops claiming the deletion can't be undone.
- 16 new tests in `tests/test_soft_delete_profiles.py`. Suite 233 → 249.

**Design notes:**

1. **Lazy cleanup, not a scheduler** — the repo owner's call on the issue, to avoid building scheduling infrastructure speculatively for #25. Runs from both list endpoints, so the "Recently deleted" view alone is enough to trigger expiry.
2. **Nothing under the profile is touched at delete time.** No cascade until the window expires, which is what makes restore a single field write and lets the retention window change later without touching any child table.
3. **Restore doesn't purge first**, deliberately — otherwise a restore click could destroy the profile it was trying to bring back. A past-window profile stays restorable until something else purges it; `test_past_window_profile_is_still_restorable_until_purged` pins that.
4. **`/profiles/deleted` is declared before `/profiles/{profile_id}`.** FastAPI matches in declaration order, so the reverse reads "deleted" as a profile id. Pinned by its own test, since a future reorder would break it silently.
5. **`days_remaining` is computed server-side and floored at 0**, and `expires_at` is derived from `deleted_at` + the retention constant rather than stored — so changing the constant moves every existing countdown instead of leaving rows frozen at whatever it was when they were deleted.
6. **The type-to-confirm bar stayed.** Recoverable isn't the same as cheap; the point of that modal is to stop the wrong profile being deleted at all, and #50 didn't ask to lower it.
7. **Two routers deliberately out of scope.** `action_items.py` and `documents.py` never verified the profile existed (unknown ids return `200 []`), so a soft-deleted profile's action items stay readable to a stale URL. Bringing them in line is a behavior change beyond soft-delete — filed as #119.

**Files changed:** `src/data/models.py`, `src/api/health_profile.py`, `src/api/{conditions,medications,doctors,appointments}.py`, `src/models/schemas.py`, `alembic/versions/c8f2b41d7e93_add_deleted_at_to_health_profiles.py`, `frontend/src/pages/{ProfileList,ProfileDetail}.tsx`, `frontend/src/components/Modal.tsx`, `frontend/src/api/client.ts`, `frontend/src/types/index.ts`, `frontend/src/constants.ts`, `tests/test_soft_delete_profiles.py`.

Related: issue #50, issue #25 (scheduler), issue #49 (AVS file deletion — its natural hook point is now the purge path), issue #93, issue #119, DEC-027.

---

## 46. Per-Profile JSON Export (#93, DEC-028)

**Date:** 2026-08-04

**Context:** No export path existed — HealthSteward was the sole copy of a user's health history on a single unbacked-up machine. Issue #93. The issue's three open questions (per-profile vs. everything, plaintext vs. encrypted, local vs. cloud) were all resolved by the repo owner before implementation.

**What was built:**
- `GET /api/profiles/{profile_id}/export` (`src/api/profile_export.py`, new router) returning a full-fidelity JSON document: format version, export timestamp, app version, the profile's own fields, and a top-level list per profile-scoped table, plus `visit_preps`. Served as a file download.
- Frontend: an "Export" button on the profile header; `downloadProfileExport()` in `api/client.ts` takes the filename from the server's `Content-Disposition` header so the two can't drift.
- 10 new tests in `tests/test_profile_export.py`. Suite 233 → 243.

**Design notes:**

1. **Serialization is mapper-driven, not a field list** — a column added to a model is exported automatically, because the alternative fails silently and is only discovered at restore time.
2. **Keys are included.** Which appointment was with which doctor is part of the data; an export that drops the foreign keys is a summary, not a backup.
3. **`export_format_version` ships in v1** — the one field that can't be added retroactively, since files already on disk won't have it.
4. **Documents are metadata + parsed contents, not the source PDFs**, with a `documents_note` field inside the file stating so.
5. **Nothing is anonymized.** DEC-006 governs data crossing to an external LLM; this file never leaves the machine, and redacting it would corrupt the backup.

**Import was deliberately not built.** The approved plan called for `POST /api/profiles/{profile_id}/import`, but implementing it surfaced a question the plan doesn't answer: importing into an *existing* profile can either append (duplicating everything on a re-import), replace its contents (destructive), or the endpoint could instead create a new profile from the document (non-destructive, and the only shape that works on a fresh machine with no profile to import into). Those are three materially different features, and the failure modes are duplication or data loss on a user's only copy of their history — so it was raised as an open question on #93 rather than guessed at. #93 stays open.

**Files changed:** `src/api/profile_export.py`, `src/main.py`, `frontend/src/api/client.ts`, `frontend/src/pages/ProfileDetail.tsx`, `tests/test_profile_export.py`.

Related: issue #93, issue #92 (encryption at rest), issue #99 (human-readable share-with-provider export), DEC-006, DEC-028.

---

## 47. Action-Item and Document Routes Now Verify the Profile Exists (#119)

**Date:** 2026-08-05

**Context:** #50/DEC-027 made a soft-deleted profile invisible everywhere it's looked up — the profile routes and the four child routers (conditions, medications, doctors, appointments) all 404 for a deleted profile via a per-router `verify_profile_exists`. `src/api/action_items.py` (follow-ups, lab orders, referrals, nudges, computed alerts) and `src/api/documents.py` never verified the profile at all, so a soft-deleted profile's action items and documents stayed readable — and, on the mutating routes, writable — through a URL kept open across the deletion.

**What changed:**
- `action_items.py` and `documents.py` now call `get_live_profile_or_404` (already defined in `src/api/health_profile.py`) at the top of every route handler, before touching any per-router table.
- The four existing `verify_profile_exists` copies in `conditions.py`, `medications.py`, `doctors.py`, `appointments.py` are collapsed into a one-line wrapper around the same shared helper — same behavior and call-site signature, one definition instead of four.

**Behavior change:** reusing `get_live_profile_or_404` means an unknown `profile_id` on an action-items or documents route now returns `404` instead of the previous `200 []` (reads) or proceeding silently (writes). This was flagged as an open question on the issue; the user's call was to make it consistent with the other four routers rather than 404-only-on-soft-delete, on the reasoning that leaving unknown ids returning `[]` would be an inconsistency that reads as a bug to the next person touching this code. No client in this codebase relies on the old empty-list shape.

**Tests:** extended `tests/test_soft_delete_profiles.py` with `test_action_item_routes_404_for_a_soft_deleted_profile`, `test_action_item_routes_404_for_an_unknown_profile`, `test_document_routes_404_for_a_soft_deleted_profile`, and `test_document_routes_404_for_an_unknown_profile`, covering both read and mutating paths on each router. Full suite: 276 passed (up from 270).

No DEC entry — this implements DEC-027's stated boundary consistently rather than making a new architectural choice; the 200-vs-404 question was resolved via a quick prompt with the user rather than warranting its own record.

**Files changed:** `src/api/action_items.py`, `src/api/documents.py`, `src/api/conditions.py`, `src/api/medications.py`, `src/api/doctors.py`, `src/api/appointments.py`, `tests/test_soft_delete_profiles.py`.

Related: issue #119, issue #50, DEC-027.

---

## 48. Log What Got Redacted, Per Visit-Prep Request (#16, DEC-029)

**Date:** 2026-08-05

**Context:** `Anonymizer.anonymize_text()` scanned free text for PII and substituted `[REDACTED]`, but threw away what it matched. There was no way to check, after the fact, whether the regex/NER net actually caught everything for a given visit-prep call — a Reddit comment on the pluggable-backend post flagged exactly this: "redaction recall is the whole ballgame ... worth logging what got redacted so you can audit misses." A follow-up discussion on the issue clarified the aggregation should be per visit-prep-request (not per-document — AVS PDFs never get anonymized in the first place, since nothing derived from them leaves the machine at that stage) and that each match should carry a stable per-entity id rather than just a count, so a future write-back-capable agentic tool could be audited against exactly which entities a run could see.

**What was built:**
- `RedactionEvent` (`src/utils/anonymization.py`): `entity_id` (deterministic `sha256(profile_id|field_name|entity_type|occurrence_index)`, truncated — never a random UUID, never derived from the matched text), `entity_type`, `start`/`end` span, `field_name`, optional `document_id`. `to_dict()` emits `"document_link": "none"` when there's no document lineage rather than omitting the key.
- `anonymize_text()` now returns `(anonymized_text, list[RedactionEvent])`, with matches recorded before each regex substitution and before NER's replacement pass, in the same declaration order the redaction itself already followed.
- `anonymize_profile()`, `anonymize_doctor()`, `anonymize_appointment()` all thread `profile_id`/`field_name`/`document_id` through and return `(result, events)`.
- Call sites updated: `VisitPrepTools` (`src/agents/tools.py`) now accumulates `self.redaction_events` across every tool-result anonymization; Stage 4 of context selection (`src/utils/context_selection.py`) collects events into a new `ContextSelectionResult.redaction_events` field; `VisitPrepAgent.prepare_visit` (`src/agents/visit_prep.py`) aggregates all of the above into `self.last_redaction_events` for the whole request — profile/appointment anonymization, Stage 4 selection, and agentic-loop tool results, including the non-convergence path before falling back to single-shot.
- `BaseAgent._log_conversation` (`src/agents/base.py`) gained a `redaction_events` parameter, written to the assistant `ConversationLog` row as `extra_data["redaction_events"]` — no schema migration, since `extra_data` was already a flexible JSON column.
- Fixed a pre-existing duplication while touching this code: `_build_anonymized_context` was re-calling `anonymize_text` on `condition.notes` even though `anonymize_profile` had already anonymized it (the result just wasn't reused downstream). Left alone, that would have double-logged every condition-notes redaction event; now it reuses `anonymize_profile`'s output via `zip(conditions_raw, profile.conditions)`.
- New tests: `tests/test_anonymization.py` (event shape never leaks the raw match; entity ids stable across repeated calls and distinct across field names; `document_id` tagging vs. honest `"document_link": "none"`), `tests/test_agent_tools.py` (tool-result redaction events aggregate onto `VisitPrepTools`), `tests/test_visit_prep.py` (end-to-end: events land in `ConversationLog.extra_data`, ids are stable across two separate `prepare_visit()` calls). Suite 276 → 279.

**Not in scope, deliberately:** `Condition`/`Medication`/`Appointment` have no `document_id` column and none was added — the issue's own scoping note is that most PII-bearing free text (visit notes, additional concerns) is user-typed and was never document-sourced, so a migration wouldn't fully solve per-document traceability anyway. `Vitals`/`LabOrder`/`Referral`/`FollowUp` do have `document_id`, and `RedactionEvent` supports tagging it, but none of those models' text fields currently flow through `anonymize_text` in the pipeline (`_build_anonymized_context` inserts their values unanonymized today — a pre-existing gap, unrelated to #16). The `document_id`-tagging capability is exercised directly against the `Anonymizer` in tests rather than through the pipeline for that reason.

**Files changed:** `src/utils/anonymization.py`, `src/agents/tools.py`, `src/agents/visit_prep.py`, `src/agents/base.py`, `src/utils/context_selection.py`, `tests/test_anonymization.py`, `tests/test_agent_tools.py`, `tests/test_visit_prep.py`, `tests/test_context_selection.py` (mock return-shape fix).

Related: issue #16, DEC-006, DEC-029.

---

## 49. Partition `data/avs/` Per Profile, Opt-In File Deletion at Purge Time (#49, DEC-030)

**Date:** 2026-08-05

**Context:** `data/avs/` was one flat folder scanned for every profile: `scan_documents` listed every PDF unconditionally, filtering only the response's *status* by matching against a profile's `Document` rows — not the underlying scan itself. In practice a PDF already applied to one profile still showed as "New" under a different profile's Documents tab, with nothing stopping it from being parsed and applied a second time to the wrong person. And `delete_profile` cascade-deleted `Document` rows without ever touching the file on disk, so a deleted profile's PDF reappeared as "new" in the shared folder afterward. Real risk for the caregiver persona this app targets — a parent tracking multiple kids, someone managing multiple aging parents — where several people's AVS PDFs land in the same folder.

**What was built:**
- `scan_documents` and `parse-file` (`src/api/documents.py`) now scope to `data/avs/<profile_id>/` instead of the flat root — cross-profile visibility is now structurally impossible, not just filtered out of one response.
- `HealthProfile.purge_avs_files_on_expiry` (new boolean column, default `false`, migration `50e07994bbfe` chained off `c8f2b41d7e93`): an opt-in captured at soft-delete time via a checkbox in `DeleteConfirmModal` (`frontend/src/components/Modal.tsx`, wired up in `frontend/src/pages/ProfileDetail.tsx`), unchecked by default since AVS PDFs are the user's own source documents, not something the app generated.
- `delete_profile` (`src/api/health_profile.py`) now takes a `purge_avs_files_on_expiry` query param and stores it on the profile — it does **not** touch any files itself. The actual `shutil.rmtree` of the profile's subfolder happens inside `purge_expired_profiles`, only for profiles that are both past the 30-day recovery window (DEC-027) *and* have the flag set. A profile restored before expiry keeps its files regardless of the flag — `restore_profile` just clears `deleted_at`, and a live profile is never in `purge_expired_profiles`'s query.
- `scripts/migrate_avs_per_profile.py`: one-time, idempotent migration for existing installs. Matches each top-level file to a `Document` row by the same `(original_filename, file_size_bytes)` key `scan_documents`/`parse_file` already use and moves it to `data/avs/<profile_id>/`; files with no matching `Document` row move to `data/avs/_unassigned/` instead of guessing an owner. Run with `python -m scripts.migrate_avs_per_profile`. Safe to re-run: only top-level files count as unmigrated, and a destination-name collision is skipped with a logged warning rather than overwritten.

**Tests:** new `tests/test_avs_partitioning.py` — scan isolation (Profile B never sees Profile A's files, and scanning creates the requesting profile's own subfolder); migration correctly partitions claimed vs. unclaimed files and is idempotent across two runs; opt-in deletion fires only when the flag is set *and* the profile actually purges, never at soft-delete time; and a profile restored before expiry keeps its files intact even though it was soft-deleted with the flag set. Full suite: 282 passed (up from 276).

**Files changed:** `src/api/documents.py`, `src/api/health_profile.py`, `src/data/models.py`, `alembic/versions/50e07994bbfe_add_purge_avs_files_on_expiry_to_health_.py`, `scripts/migrate_avs_per_profile.py`, `frontend/src/components/Modal.tsx`, `frontend/src/pages/ProfileDetail.tsx`, `frontend/src/api/client.ts`, `tests/test_avs_partitioning.py`.

Related: issue #49, issue #50, DEC-027, DEC-030.

---

## 50. OpenMed PII Benchmark — Evaluated and Not Adopted (#122)

**Date:** 2026-08-05

**Context:** DEC-025 hardened the hand-rolled regex list rather than adopting a PII-detection library, and parked library adoption on #92. #122 asked for a prototype benchmark of OpenMed (Apache-2.0, local-first, 18 HIPAA Safe Harbor categories) against the current approach — explicitly an evaluation, not a production swap: no changes to `src/utils/anonymization.py`, and no `openmed` in `requirements.txt`/`environment.yml`.

**What was built:**
- `eval/prototypes/openmed_pii_cases.py` — 67 positive and 24 negative cases transcribed from `tests/test_anonymization.py`, each citing the test it came from, tagged by PII category. (Moved from `eval/openmed_pii_cases.py` into its own `eval/prototypes/` subdirectory during PR #124 review, since it doesn't share `eval/`'s existing `run.py`/`scorers.py`/`fixtures.py` conventions.)
- `eval/prototypes/openmed_pii_prototype.py` — scores systems (`regex`, `regex+ner`, `openmed`) on that corpus by one rule, reports per-category rather than as one accuracy number, and measures load time, per-text latency, and peak RSS. Supports `--confidence` and `--model` for sweeping OpenMed's threshold and testing different model sizes. `--json` writes a machine-readable report stamped with the platform it ran on.
- `tests/test_openmed_pii_corpus.py` — pins the corpus's known case counts (67/24) so an edit to `test_anonymization.py`'s PII cases that isn't mirrored in the transcribed corpus fails loudly instead of drifting silently.
- `eval/prototypes/OPENMED_FINDINGS.md` — full write-up: methodology, all six configurations tested, caveats, reproduction steps.
- Nothing in `src/` imports these files and `tests/` (other than the corpus-count guard) does not collect them; full suite at 272.

**The initial PR (#124) shipped with the OpenMed half unmeasured** — this sandbox's egress policy blocks `huggingface.co`, so the reviewer re-ran the missing half locally on the actual target hardware (8GB M3, the machine DEC-009 identifies as the binding constraint). That run hit its own snag: `openmed[hf]` pulls in `transformers==5.14.1`, which breaks OpenMed's pipeline construction (`AutoConfig.from_pretrained() got multiple values for keyword argument 'local_files_only'`, an OpenMed/transformers version incompatibility, not a harness bug) — downgrading to `transformers<4.45` fixed it.

**Full results, six configurations:**

| system | PII caught | clinical text intact | mean/text | peak RSS |
|--------|-----------|---------------------|-----------|----------|
| `regex` (fresh clone: spaCy in neither manifest) | 63/67 (94%) | 24/24 (100%) | 0.007 ms | 15 MB |
| `regex+ner` (DEC-006 as described) | 66/67 (99%) | 23/24 (96%) | 1.9 ms | ~304 MB |
| `openmed` small-44M, conf 0.3 | 63/67 (94%) | 17/24 (71%) | 780 ms | ~513 MB |
| `openmed` small-44M, conf 0.5 (default) | 62/67 (93%) | 17/24 (71%) | 785 ms | ~513 MB |
| `openmed` small-44M, conf 0.7 | 55/67 (82%) | 18/24 (75%) | 872 ms | ~513 MB |
| `openmed` large-434M, conf 0.5 | 56/67 (84%) | 21/24 (88%) | 2993 ms | ~1481 MB |

**Verdict: no OpenMed configuration beats the current approach on both recall and precision at once, and every configuration is 400×–1500× slower than what's running today.** The large model trades recall for precision relative to the small one rather than dominating it — bigger wasn't strictly better. Full breakdown, including which specific cases leaked or over-redacted per configuration, is in `OPENMED_FINDINGS.md`.

**Findings worth more than the aggregate:**

1. **The NER half over-redacts clinical content.** `"Lisinopril 10 mg daily"` → `"[REDACTED] 10 mg daily"` — spaCy tags the drug name as a PERSON. DEC-025's reasoning leans hard on negative cases asserting clinical content survives, but every one of those tests constructs `Anonymizer(use_ner=False)`, so the NER path had no negative coverage at all and this was invisible. Filed as #125 rather than fixed here, since #122 is explicitly scoped to not touch production anonymization.
2. **`Dr. Smith` still leaks in `"Call Dr. Smith at 555-123-4567"`** even with NER on — spaCy doesn't tag it as PERSON in that construction, though it does in `"Referred by Dr. Sarah Johnson last spring"`. Single-token surnames after a title are the weak case.
3. **OpenMed's label taxonomy doesn't match this project's policy**, confirmed rather than just predicted: clinic names, appointment times, weights, and dosage numbers all got over-redacted under labels (`city`, `time`, `age`, `postcode`, `pin`) this project's `NegativeCase` corpus treats as clinical content to keep. Any future integration would need real label filtering, not wholesale acceptance of OpenMed's output.
4. **DEC-006 vs. actual behavior gap surfaced separately** — spaCy isn't in either dependency manifest, so `regex` (94% recall) is what a fresh clone actually runs, not `regex+ner` (99%) which DEC-006 describes. Filed as [#126](https://github.com/nidhi-menon/HealthSteward/issues/126).

**Design notes:**

1. **Scoring is asymmetric on purpose.** A leak (PII survives) and an over-redaction (clinical text altered) are both failures but not the same failure — a detector that redacts everything has a perfect leak rate and is useless. Positives pass when no `must_remove` substring survives; negatives pass only on byte-identical output.
2. **`extract_pii`, not `deidentify`.** `deidentify` does its own masking with per-label placeholders (`[NAME]`, `[EMAIL]`); rewriting OpenMed's spans with the same `[REDACTED]` the current anonymizer uses is what makes the exact-equality check on negatives meaningful.
3. **The probe call is eager.** The first `extract_pii` is what downloads weights, so it runs at build time — that's the only way an unreachable model host surfaces as an unavailable system rather than as 91 silent misses.
4. **`regex+ner` is scored separately from `regex`, and skipped loudly if spaCy is absent.** spaCy is in neither manifest, so the regex-only row is what a fresh clone actually runs; reporting those numbers under the DEC-006 label would overstate the real baseline.
5. **Peak RSS is process-cumulative** (`ru_maxrss` is a high-water mark), so the report prints the post-import floor and says to compare deltas or isolate with `--systems`.

**Caveats on the numbers themselves** (see `OPENMED_FINDINGS.md` for the full list): per-category sample sizes are small enough that one case swings a rate 25-33%; the corpus was transcribed from tests written to validate the *regex* approach, so it's denser with exact-format edge cases regex is defined to catch and lighter on the free-text PII NER-style models target; only English models and three confidence points were tested. None of these caveats affect the latency/memory conclusions, which are decisive regardless.

**No DEC entry** — per #122's own scope note, this is an evaluation, not a production change: `src/utils/anonymization.py` is untouched and `openmed` is absent from both dependency manifests. Issue #122 closed as evaluated-and-not-adopted.

**Files changed:** `eval/prototypes/openmed_pii_cases.py`, `eval/prototypes/openmed_pii_prototype.py`, `eval/prototypes/OPENMED_FINDINGS.md`, `tests/test_openmed_pii_corpus.py`.

Related: issue #122 (closed), issue #125 (NER over-redaction), issue #126 (DEC-006 vs. actual behavior gap), PR #124, issue #73, issue #92, DEC-006, DEC-025, DEC-009.

---

## 51. Profile Export Now 404s for a Soft-Deleted Profile (#123, DEC-027 amendment)

**Date:** 2026-08-06

**Context:** Raised as concern #6 on PR #121 and again after that PR's rebase; #121 merged without it being answered, so the behavior on `main` was whatever the code happened to do rather than a decision — which is why it was filed as its own issue instead of fixed in passing. `export_profile` (`src/api/profile_export.py`) predates DEC-027 and kept its own plain `select(HealthProfile).where(HealthProfile.id == profile_id)` with no `deleted_at` filter. Since #120/DEC-027 landed, every other profile route resolves through `get_live_profile_or_404` or the child routers' wrapper around it, both of which 404 for a soft-deleted profile. Export was the one route that didn't: a soft-deleted profile inside its 30-day recovery window was still fully exportable by anyone holding the URL, and `tests/test_profile_export.py` didn't touch soft-delete at all, so nothing pinned it either way.

**What changed:** one lookup. `export_profile` now calls `get_live_profile_or_404` like everything else, with a comment recording that the exemption was considered and rejected rather than overlooked.

**The decision, and why it went this way.** The repo owner's call on #123 was **block**, against the recommendation the previous run posted there (which argued to allow it deliberately, on the grounds that export is a read-only escape hatch and the lopsided failure mode is losing your only copy at day 31). The deciding argument for blocking: "deleted means unreachable, everywhere" is the existing pattern, and an exception for the one route that already didn't follow it is what created this gap. The "grab a copy before the purge" use case is real but wants a discoverable affordance on the "Recently deleted" view rather than a URL-only backdoor that in practice rescues nobody — filed as **#130** rather than left as a sentence here.

**No DEC entry**, per the issue's own scope note: this settles a boundary DEC-027 and DEC-028 left ambiguous between them rather than making a new choice, so it's an amendment appended to DEC-027's status.

**No frontend change.** The Export button lives on `ProfileDetail` (`frontend/src/pages/ProfileDetail.tsx`), which is unreachable for a deleted profile, and `downloadProfileExport` already surfaces the server's `detail` on a non-2xx. There is no UI path that can now hit the new 404.

**Tests:** `tests/test_profile_export.py` gains `test_export_of_a_soft_deleted_profile_is_404` (exports 200 while live, 404 after delete — asserting both halves so the test can't pass because export was broken generally) and `test_export_works_again_after_restore` (the block is keyed on `deleted_at`, not on anything sticky, and the data comes back intact). Full suite: 291 passed (up from 289).

**Files changed:** `src/api/profile_export.py`, `tests/test_profile_export.py`, `docs/notes/DECISIONS.md`.

Related: issue #123, issue #130, PR #121, DEC-027, DEC-028.

---

## 52. Negative Test Coverage for the spaCy NER Path (#125, item 1)

**Date:** 2026-08-06

**Context:** Surfaced by the #122 benchmark harness (PR #124): running the anonymizer in its DEC-006 configuration — regex + spaCy `en_core_web_sm` PERSON detection — turns `"Lisinopril 10 mg daily"` into `"[REDACTED] 10 mg daily"`. spaCy tags the drug name as a `PERSON` and `anonymize_text` redacts every `PERSON` unconditionally, destroying the most clinically load-bearing token in the sentence before the LLM generating visit prep ever sees it.

The reason this stayed invisible is the part worth recording. DEC-025's reasoning rests explicitly on negative test cases asserting clinical content survives redaction — "every widened pattern is paired with negative test cases asserting clinical content survives." That was true of the regex patterns and thoroughly tested. But **every class in `tests/test_anonymization.py` constructed `Anonymizer(use_ner=False)`**, so the `if self.use_ner and self.nlp:` branch had no coverage at all, positive or negative. The suite was green with spaCy installed and with it absent, because nothing exercised the difference.

**What was built** — item (1) of #125 only, per the scoping decision on the issue: land the coverage now, defer the `PERSON` false-positive mitigation (allowlist / corroboration / larger model / accept-and-document) until spaCy is actually being adopted, since it changes behavior on the DEC-006 trust boundary and wants a real DEC entry.

- `TestNERPath` in `tests/test_anonymization.py` — 25 tests, all against `Anonymizer(use_ner=True)`:
  - **Positive:** multi-token names in free text (`Jane Doe`, `Sarah Johnson`, `Robert Martinez`) are redacted — no `PII_PATTERNS` entry matches a bare name, so this is what the branch is for.
  - **Negative:** the same clinical-content corpus `TestHardenedPIIPatterns::test_clinical_content_not_redacted` covers, re-run with NER on. Exactly one case moves, which is why the list is duplicated rather than assumed to carry over.
  - **Known-bad, pinned as `xfail`:** drug-name over-redaction (`Lisinopril 10 mg daily`, `Started Rosuvastatin last month.`) and the single-token-surname leak (`Call Dr. Smith at 555-123-4567` keeps `Smith` while the phone number is caught by regex).
  - **DEC-029 events on this branch:** a `PERSON` event carries type and span but never the matched name; ids are stable across runs; and NER spans are offsets into the *post-regex* text, not the original — pinned because a `PERSON` span and a `phone` span in the same `extra_data["redaction_events"]` list index two different strings, which is a real trap for anyone reading that log.
- **`test_ner_branch_is_actually_active`** guards the guard: if the fixture ever silently degraded to regex-only, every negative case would pass for the wrong reason and the class would be decorative — which is the exact failure mode being closed. The skip predicate probes `Anonymizer(use_ner=True).nlp is not None` rather than trusting `SPACY_AVAILABLE`, because `Anonymizer.nlp` silently flips `use_ner` back to `False` when the model isn't downloaded.
- The whole class **skips cleanly** when spaCy or `en_core_web_sm` is absent — which is the case on a fresh clone and in CI, since spaCy is in neither manifest (#126). A missing optional dependency shouldn't be a red build.

**Sizing the defect, which #125 asked for.** One case is an existence proof, not a rate. Sweeping 205 common generic and brand drug names through `en_core_web_sm` across five sentence templates: **69% were tagged `PERSON` in at least one context, 8% in every context.** Context dominates — `"Started {} last month."` triggers 64% while the bare name alone triggers 13% — and 17 names (including `Rosuvastatin`, `Azithromycin`, `Levetiracetam`, `Morphine`, `Synthroid`, `Prozac`, `Coumadin`) are flagged in every template. `"Started Rosuvastatin last month."` is the worst observed shape: the span swallows the preceding verb, yielding `"[REDACTED] last month."` Full numbers posted on #125; the sweep script was deliberately throwaway and is not committed, since it exists to produce one number for a decision, not to be maintained.

**Deliberately not changed:** `src/utils/anonymization.py`. These tests pin what the NER path does today, not what it should do. When item (2) of #125 lands, the `xfail`s here are the list of things to revisit.

**Tests:** full suite **311 passed, 3 xfailed** with spaCy and `en_core_web_sm` installed (up from 289); **289 passed, 25 skipped** without them — the fresh-clone and CI configuration, and identical to the pre-change count, so nothing existing moved. All three configurations verified, including the intermediate case of spaCy installed but the model missing.

**Files changed:** `tests/test_anonymization.py`.

Related: issue #125, issue #122, issue #126, PR #124, DEC-006, DEC-025, DEC-029.

---

## 53. DEC-006 Amended: Regex-Only Is the Documented Default, spaCy NER Stays Aspirational (#126)

**Date:** 2026-08-06

**Context:** DEC-006 has described the free-text anonymization approach as "regex patterns + spaCy NER for names" since it was written, but `spacy` was never added to `requirements.txt`/`environment.yml`. `SPACY_AVAILABLE` is `False` on every fresh clone, so `regex+ner` — the configuration DEC-006 documents — has never actually run in a shipped install; the effective default has always been regex-only. PR #124's benchmark measured the gap directly (regex: 63/67 PII caught, 24/24 clinical text intact, 15 MB; regex+ner: 66/67 caught, 23/24 intact, 159 MB), and #125's follow-up sizing made the cost of closing that gap concrete: sweeping 205 common drug names through `en_core_web_sm`, **69% were tagged `PERSON` in at least one sentence context, 8% in every context** — e.g. `"Started Rosuvastatin last month."` becomes `"[REDACTED] last month."`, destroying the single most clinically load-bearing token in the sentence.

**The decision:** adopting spaCy to match DEC-006's original wording would buy +3/67 additional name catches, and would convert a defect that is currently *latent* (nobody's data passes through the NER branch today) into one *live* on every install, at a ~69% false-positive rate on drug names in note-shaped sentences. That trade isn't close. DEC-006 is amended to state regex-only as the effective, documented default; spaCy NER remains optional/aspirational, to be revisited only once #125's item (2) — a false-positive mitigation for the `PERSON`-over-redaction — is resolved. No dependency was added; no code changed.

**Why doc-only, not a new DEC entry:** per #126's own scope note, this settles which of DEC-006's two described behaviors is real rather than making a new architectural choice, so it's an amendment to DEC-006's Status line rather than a new entry — same shape as DEC-027's #123 amendment.

**Files changed:** `docs/notes/DECISIONS.md` (DEC-006 amendment).

Related: issue #126, issue #125, PR #124, PR #132, DEC-006, DEC-009.

---

## 54. Export Action on the "Recently Deleted" View (#130)

**Date:** 2026-08-06

**Context:** #123's decision (entry 51) blocked export of a soft-deleted profile through the existing route and deferred the "grab a copy before the 30-day purge" use case to its own issue rather than reopening a URL-only backdoor. #130 implements that deferred affordance.

**What changed:** a second, separate backend route, `GET /api/profiles/deleted/{profile_id}/export`, added to `src/api/profile_export.py` alongside a new `get_deleted_profile_or_404` helper — the mirror image of `get_live_profile_or_404` in `src/api/health_profile.py`, filtering on `deleted_at IS NOT NULL` instead of `IS NULL`. The existing `/{profile_id}/export` route is untouched: it still resolves through `get_live_profile_or_404` and still 404s for a deleted profile. The two routes now share a `_build_export_document` helper (factored out of the body of `export_profile`) so "what gets exported" stays identical between the live and rescue paths while "which profile is reachable" stays a completely separate lookup per path, per #123's decision to keep those two things distinct rather than relax a filter.

**Provenance flag:** the export document now carries `exported_from_deleted: bool` alongside `export_format_version`, `true` from the new route and explicitly `false` from the existing one (rather than omitting the key on a live export) — every other field in the document is always-present with a value, not optionally absent, so an explicit `false` matches the rest of the payload's shape and means an importer/reader never has to treat a missing key as "false."

**Frontend:** `frontend/src/pages/ProfileList.tsx`'s "Recently deleted" row gains an Export button next to Restore, wired to a new `downloadDeletedProfileExport` in `frontend/src/api/client.ts` — same download-file-via-blob UX as the existing `downloadProfileExport`, pointed at the new route.

**Out of scope, deliberately:** whether re-deleting a restored profile should preserve the original `deleted_at` (not reset the 30-day clock) is #130's own scope note as a separate, later issue. Not touched here.

**Tests:** `tests/test_profile_export.py` gains `test_export_of_a_live_profile_carries_exported_from_deleted_false`, `test_deleted_export_404s_for_a_live_profile`, `test_deleted_export_404s_for_an_unknown_profile`, `test_deleted_export_succeeds_for_a_soft_deleted_profile`, `test_live_export_route_still_404s_for_a_soft_deleted_profile` (regression guard on #123's fix), and `test_restore_flips_which_export_route_works` (mirror-image check across both routes before/after restore). Full suite: 299 passed, 25 skipped (up from 291 passed at entry 51's time).

**No DEC entry**, per the issue's own scope note: this implements the affordance DEC-027's status note (via #123) already pointed at, rather than making a new architectural choice.

**Files changed:** `src/api/profile_export.py`, `tests/test_profile_export.py`, `frontend/src/api/client.ts`, `frontend/src/pages/ProfileList.tsx`, `docs/notes/DEVELOPMENT_LOG.md`.

Related: issue #130, issue #123, PR #131, DEC-027.

---

## 55. FHIR Bundle Import — Scoped, Not Yet Implemented (DEC-031, #101)

**Date:** 2026-08-06

**Context:** #101 asked for a way to import records from Apple Health / FHIR bundles, since manual entry is currently the only on-ramp for a new user's data besides AVS PDF parsing. FHIR is a large standard (100+ resource types) with several genuinely different acquisition paths (file upload, an Apple HealthKit companion app, live provider OAuth) — this entry is the scoping/decision work, not implementation. No code changed.

**What was decided (DEC-031):** ship a backend-only, file-upload-triggered FHIR import path first, covering exactly `Condition` and `MedicationStatement` — the two resource types with the cleanest 1:1 mapping onto existing tables. Reuses the AVS parse→preview→apply flow rather than a new review UX. Key field-mapping calls: `Condition.icd_10` gets a companion `coding_system` column rather than assuming ICD-10 (FHIR commonly supplies SNOMED CT); `Medication.purpose`/`side_effects` stay `NULL` on FHIR-sourced rows, documented as a gap rather than silently dropped; a new provenance field distinguishes FHIR-imported rows from AVS/manual ones.

**Reconciliation explicitly deferred, not solved.** Issue #97 (cross-source conflict reconciliation) is itself unscoped, and the underlying silent-overwrite problem already exists between manual entry and AVS parsing today (#46). FHIR import doesn't introduce a new category of problem, it makes an existing open one more frequent. Rather than block on #97, this slice ships one narrow, deterministic mitigation: a fuzzy name-match against the profile's existing rows, surfaced as a "possible duplicate" flag in the preview UI — no auto-merge.

**Why not build everything at once:** each additional FHIR resource type is a real mapping decision, not boilerplate — `Vitals` needs aggregation logic to fold multiple per-visit `Observation` resources into one row; `LabOrder` needs a decision about FHIR's order-vs-result split that doesn't map cleanly onto its snooze/complete lifecycle; `Doctor` needs joining three separate resources (`Practitioner`, `PractitionerRole`, `Organization`). Guessing at all of them upfront risked getting several wrong at once instead of learning from the first two.

**Why file-upload first, not Apple Health or live OAuth:** Apple's HealthKit has a genuinely built-in bridge to FHIR for clinical records (`HKClinicalRecord.fhirResource` — no third-party conversion library needed, unlike `HealthKitOnFHIR`-style SPM packages), but it still requires a companion iOS app (HealthKit entitlements are unavoidable) with its own cost (Apple Developer Program, $99/yr) and release process — a separately-schedulable engineering surface, not a backend-scoping decision. Live SMART-on-FHIR OAuth is materially larger still: per-EHR-vendor registration, token/sync maintenance, a new persistent external-connection trust boundary DEC-006 hasn't had to reason about before (existing external calls are outbound-only to the LLM backend). Both were deferred to their own issues rather than gating a shippable first slice.

**Honest UX caveat, discussed but not resolved here:** the file-upload path alone doesn't fix the real onboarding friction #101 was aimed at — most patients don't know what a FHIR bundle is, and most portals don't offer an obvious one-click export for a non-technical user. This slice is infrastructure/validation (proves the mapping and duplicate-detection approach cheaply) more than a marketed onboarding win; its practical value is unlocked once #137 (the Apple Health companion app) removes the "where do I even get the file" problem.

**Files changed:** `docs/notes/DECISIONS.md` (DEC-031), `docs/notes/DEVELOPMENT_LOG.md`.

Related: issue #101, DEC-031, issue #135 (implementation, file-upload Condition+Medication), issue #136 (additional resource types), issue #137 (Apple Health companion app), issue #138 (live SMART-on-FHIR OAuth, deferred), issue #97 (reconciliation, deferred), issue #46 (related precedent), DEC-006, DEC-023.

---

## 58. Frontend Test Harness and First Suite (#27)

**Date:** 2026-08-07

**Context:** the backend has 299 passing tests; `frontend/package.json` had no `test` script and there were no `*.test.tsx` files anywhere under `frontend/src/`. Not from a specific bug — it surfaced during a repo-hygiene pass — but the untested logic includes the parts most likely to break silently: `ActionItemsSection`'s date-relative nudge computation, snooze-duration handling, and `ParsedItemsReview`'s selective-apply flow, which decides what actually gets written to a profile.

**Stack: Vitest + React Testing Library + jsdom**, as the issue itself suggested. Vitest reuses the existing `vite.config.ts`, so there's no second build pipeline and no Babel/Jest transform config to keep in sync with the real one. `npm test` / `npm run test:watch` in `frontend/`, plus `make test-frontend` and `make test-all` next to the existing pytest target.

**CI gating — the issue's third open question — answers itself: there is no CI.** `.github/` contains only `ISSUE_TEMPLATE/` and `pull_request_template.md`; there is no `workflows/` directory. So frontend tests run locally and gate nothing. Adding a CI workflow was deliberately *not* bundled in here — it affects the backend suite too and deserves its own decision rather than arriving as a side effect of a test-harness PR.

**No snapshot tests, no coverage thresholds.** RTL's own guidance is behaviour-over-snapshot, and snapshots over Tailwind-heavy markup produce large diffs that get rubber-stamped rather than read. A coverage threshold across a suite covering three of nine components either sits uselessly low or blocks work; better once coverage means something.

**Shared harness:** `src/test/setup.ts` (jest-dom matchers; restores real timers after every test so a frozen clock can't leak into the next one), `src/test/render.tsx` (wraps in the React Query and Router providers the components assume — rendering them bare throws before any assertion runs; retries off and per-render cache so nothing leaks), and `src/test/fixtures.ts` (builders rather than fixed objects, so each test states only the fields it is actually about).

**Initial suite — 33 tests across the three components the issue named**, all behaviour-focused, with the API stubbed at the `src/api/client.ts` boundary:

- `ActionItemsSection` (14) — the badge count, day countdowns including the singular/plural boundary, and the follow-up urgency ladder computed as elapsed fraction of the stated timeframe (quiet / approaching at ≥0.75 / overdue at ≥1.0 / silent when the timeframe isn't parseable as a duration). Snoozing: that a pill sends the right *absolute* date for its duration, that the undo banner appears, that undo clears `snoozed_until` rather than resetting it, that the banner expires, and that a second snooze replaces the banner instead of stacking. Clock pinned with `vi.setSystemTime` throughout.
- `PostAvsActionPanel` (11) — hidden when everything is resolved, resolved items filtered out, the ≤180-day urgency flag and its negative cases, and the lab-before-appointment warning including that past appointments are ignored when picking "next".
- `ParsedItemsReview` (8) — that `medication_changes` split by action into starts/stops/updates, that every accepted category reaches the request, that removing an item excludes it and empties the apply button, that a corrected misparse is what gets sent, that vitals are only included when recorded, that notes are shown but never applied, and that nothing applies until the confirmation is accepted.

**One harness lesson worth recording**, because it cost real time and will bite the next person: `vi.clearAllMocks()` clears recorded calls but **not** implementations, so a `mockResolvedValue` set in one test survives into the next. That silently rendered an extra section in later tests and broke lookups that were unique in isolation. The suites re-arm every stub explicitly in `beforeEach` rather than relying on a global reset.

**Drive-by:** `frontend/src/components/PostAvsActionPanel.tsx` had two unused type imports that failed `tsc -b`, so the frontend build was already red on `main`. Fixed here because a test suite that can't compile is worthless.

**No DEC entry:** picking the test runner the issue itself named isn't an architectural choice. Flagged as such on the issue.

**Files changed:** `frontend/package.json`, `frontend/vite.config.ts`, `frontend/src/test/setup.ts`, `frontend/src/test/render.tsx`, `frontend/src/test/fixtures.ts`, `frontend/src/components/ActionItemsSection.test.tsx`, `frontend/src/components/ParsedItemsReview.test.tsx`, `frontend/src/components/PostAvsActionPanel.test.tsx`, `frontend/src/components/PostAvsActionPanel.tsx`, `CONTRIBUTING.md`, `Makefile`, `docs/notes/DEVELOPMENT_LOG.md`.

Related: issue #27, issue #44 (the snooze/undo behaviour now under test), CONTRIBUTING.md testing section.

---

## 62. Per-Entity Tokens in Free-Text Anonymization (#17, DEC-036)

**Date:** 2026-08-09

**Context:** structured fields have had relational anonymization since DEC-006 — the same doctor always becomes "your Endocrinologist". Free text had none: every match became the same literal `[REDACTED]`, so "referred by Dr. Smith to Dr. Jones" reached the model as two identical placeholders and the fact that they're two different providers was gone. The suggestion that prompted this (via Reddit, recorded on #17) was to replace with `PERSON_1`/`PERSON_2` instead, keeping relational structure without ever exporting a raw identifier.

**The design turns on where the map lives.** `VisitPrepAgent` builds its own `Anonymizer`, so per-request state would be nearly free there — but `anonymize_text()`'s module-level `get_anonymizer()` singleton is process-wide, and plain instance state would accumulate a **cross-patient** value → token map on that path. So the map is not instance state at all:

- **`token_scope()` context manager**, with scope state in a `ContextVar`. Inside a scope, redaction emits `PERSON_1`, `PHONE_1`, `MRN_1`… keyed on the normalised matched value. Outside one, behaviour is byte-for-byte what it always was — pinned by a test, so no existing caller (including the eval PII prototypes) changes by accident.
- **A `ContextVar` rather than instance state** means each asyncio task gets its own copy: two concurrent requests through the singleton cannot see each other's tokens. There's a test that runs two `anonymize_text()` calls interleaved across tasks and asserts both start at `PHONE_1`.
- **`prepare_visit()` opens exactly one scope** covering profile/doctor/appointment anonymization, additional concerns, Stage 4 context selection and agentic-loop tool results — every `anonymize_text()` entry point in the request.

**Two different notions of "stable" now live in this module and must not be conflated.** `_make_entity_id` (DEC-029) is keyed by field + occurrence index and identifies a redaction *event* for the audit log; the token map is keyed by normalised value and identifies an *entity* across fields. The same doctor mentioned in two fields gets two `entity_id`s and one token. Both are correct; they answer different questions.

**Matching is exact-normalised only** — casefold, strip one leading title, strip surrounding punctuation. No fuzzy matching, no surname-only coreference. A wrong merge would tell the model two different providers are one person, which is worse than the status quo; under-merging just degrades to roughly pre-#17 behaviour for the mentions that didn't merge.

**Output side: a leakage guard, not re-hydration.** `scrub_leaked_tokens()` rewrites any token that survives into generated output back to `[REDACTED]`, applied to `questions` and `context_summary` on every return path from `prepare_visit` including the fallback. So the worst case a patient can see is exactly what they'd have seen before #17. Whether tokens should be *re-hydrated* to real values for the patient's own eyes is the open question #17 itself flags; it stays open, and this design forecloses nothing — re-hydration would run first and the guard would catch whatever it couldn't map.

**No prompt change, so no version bump and no `PROMPT_CHANGELOG.md` entry.** Telling the model what `PERSON_1` means would probably help, but a prompt wording change needs eval evidence per the conventions, and blocking an offline, unit-testable change on an eval cycle isn't a good trade. Filed as #151.

**Files changed:** `src/utils/anonymization.py`, `src/agents/visit_prep.py`, `tests/test_anonymization.py`, `tests/test_visit_prep.py`, `docs/notes/DECISIONS.md`, `docs/notes/DEVELOPMENT_LOG.md`.

Related: issue #17, DEC-036, DEC-006, DEC-029 (the other "stable id"), #151 (prompt follow-up), #156 (scope-forgetting guard follow-up).

---

## 65. Constrained Decoding for Non-Tool Calls, Scoped to Avoid Touching Tool-Calling (DEC-039)

**Date:** 2026-08-21

**Context:** the last item from the original reliability-review list — "make small-model tool-calling actually reliable, not just gracefully degraded" — flagged constrained decoding via Ollama's `format` field as the highest-leverage lever, back before the harness existed to test it against anything real. Picked back up now that entries #62-#64 established a working harness and a confirmed-reliable default model.

**Scoping mattered more than implementing it.** Ollama's `format` constrains `message.content` to a JSON Schema at the decoding level — but this app's agentic loop always sends `tools` alongside every turn, and there's no tested guarantee for how `format` and `tools` interact in the same request (a tool-calling turn needs to emit `tool_calls`, not schema-conforming content). Rather than guess, scoped this to exactly the two calls that already don't request tools — the single-shot fallback (`_call_backend`) and the JSON-repair retry (`_repair_response_via_model`, added in entry #62) — where the entire job of the call already is "produce this JSON shape," so there's nothing to interfere with.

**Implementation:** `LLMBackend.call` gained an optional `response_schema` param, silently ignored by any backend that doesn't implement it (Claude; a `CustomOpenAICompatibleBackend`'s no-op default, since `response_format` support varies too much across arbitrary OpenAI-compatible endpoints to assume safely). `OllamaBackend` applies it as `format` only when no `tools` are present that turn. `RESPONSE_SCHEMA` (`src/agents/visit_prep.py`) constrains only the shape both prompts already ask for in prose — an object of string arrays plus a string summary — not category names or question count, keeping those governed by prompt text and eval scorers rather than a second schema that could drift from them.

**Verified safe, not yet verified necessary.** Re-ran both `llama3.2:latest` and `granite4:3b` through `eval/run.py`: both produced output byte-identical to their pre-change baselines, including `granite4:3b`'s `cold_start` case, which actually exercises the newly-constrained fallback path (and still correctly shows no placeholder hallucination, confirming the schema sits cleanly underneath entry #63's fallback fix). No case in the current fixture set was failing to parse before this change, so there's no before/after "this prevented a malformed response" data point yet — the real test comes the next time a model/case combination would otherwise have needed the repair chain.

**Not a prompt change** — no `PROMPT_CHANGELOG.md` entry. Neither system prompt's wording changed; this is a request-level decoding constraint layered under prompts that already describe this shape, not a change to what the model is asked to do.

**Files changed:** `src/agents/llm_backend.py`, `src/agents/visit_prep.py`, `docs/notes/DECISIONS.md` (DEC-039), `docs/notes/DEVELOPMENT_LOG.md`.

Related: DEC-039, DEC-037 (the repair chain this sits underneath), DEC-038 (the model comparison this was validated against), entry #62, entry #63, entry #64.

---

## 64. `llama3.2:latest` Set as the Default Local Model, Confirmed via `--trials 3` (DEC-038 addendum)

**Date:** 2026-08-21

**Context:** entry #63 left `llama3.2:latest` vs. `granite4:3b` as a single-trial-per-case comparison — enough to lean on, not enough to commit a default to. Re-ran both at `eval/run.py --trials 3` to see whether the gap (and `granite4:3b`'s `tool_call_necessity_dosing` groundedness edge) held up or was noise.

**Both models turned out fully deterministic across all 3 trials each** at `EVAL_TEMPERATURE=0.0` — byte-identical output trial to trial, on both models. That's the actual finding worth recording: this wasn't an average narrowing toward a truer number, it was confirmation that the single-trial numbers already *were* the truth for this harness. `llama3.2:latest`: 15/15 convergence. `granite4:3b`: 12/15 — `cold_start` failed the exact same way on every one of its 3 trials, meaning its non-convergence is a stable behavioral trait (it doesn't accept "no medications found" from `get_medication_details` and keeps re-probing until `agent_max_turns` runs out), not a bad roll. `granite4:3b`'s one real advantage — `tool_call_necessity_dosing` grounded_rate 0.7 vs. `llama3.2:latest`'s 0.5 — held up too, equally reproducible.

**Decision (full detail in DEC-038's addendum):** `llama3.2:latest` is the default. A `cold_start`-shaped case — a patient with little data entered yet — isn't a rare edge case for a new HealthSteward user, so a deterministic 20% non-convergence rate on that shape outweighs one other case's groundedness edge. `granite4:3b` stays available via the existing runtime Settings toggle (DEC-016), not discarded.

**Three places actually set this, and two were already stale — fixed all three to agree:** `src/config.py`'s `ollama_model` field default (`"llama3.2"` → `"llama3.2:latest"`, made explicit rather than relying on Ollama's bare-tag-means-latest convention); `.env`'s `OLLAMA_MODEL` (was `llama3.1:latest` — leftover 2026-07-10 test data, the same stale value that produced DEC-037's initial false 20%-convergence reading before that was traced to config rather than reliability); and the live DB's `app_settings.ollama_model`, which had drifted to `llama3.2:3b`, a tag that no longer exists locally (auto-pruned when other models were pulled during this review) — cleared to `NULL` instead of being set to a duplicate value, so there's one source of truth (the env default) rather than two that can silently diverge again the way this one already had, twice.

**Files changed:** `src/config.py`, `.env` (not tracked in git — local dev config), `data/healthsteward.db` (not tracked — local dev DB), `docs/notes/DECISIONS.md` (DEC-038 addendum), `docs/notes/DEVELOPMENT_LOG.md`.

Related: DEC-038, DEC-037, DEC-016 (runtime settings toggle), entry #62, entry #63.

---

## 63. Reliability Review Part 2: A Prompt Nudge That Didn't Work, Two Confirmed Model-Level Dead Ends, and `granite4:3b` Adopted (DEC-038)

**Date:** 2026-08-20

**Context:** direct continuation of entry #62's review. The A/B/C comparison there found `qwen3:4b` and `phi4-mini` converging cleanly on every eval case while never calling any tool, including the one case designed to require one — silent, ungrounded output that looks identical to a clean success unless you check `tool_call_necessity`'s `was_called` field specifically. The planned next step (per that review's own sequencing) was cheapest-first: try a prompt nudge before assuming either model is a dead end.

**The nudge didn't work, and that turned out to be informative rather than a wasted step.** Added an explicit tool-use paragraph to both system prompts (PROMPT_CHANGELOG.md v5) — concrete trigger examples per tool, plus "don't skip an available tool just because you can produce some answer without it," aimed directly at the observed pattern. Re-ran both models against `tool_call_necessity_dosing`: zero change, `was_called: False` on both. Rather than stop at "the prompt didn't work," root-caused each separately:

- **`qwen3:4b`:** confirmed a real, currently-unresolved upstream Ollama bug. Ollama's `/api/chat` accepts a `think: false` parameter for hybrid-reasoning models, but a direct test (a trivial "say hi" prompt with `think: false` set) still produced a full `<think>...</think>` block in the response. Multiple open Ollama GitHub issues (#12917, #12907, #12234) confirm this is a known, unfixed limitation — Ollama replaces the model's own chat template with a generic one, and the reasoning-effort setting lives in the template it discards. No supported workaround short of running outside Ollama entirely (`llama-server` directly with `--jinja`), which wasn't worth adopting to test one model. Separately, and more decisively: a same-day eval re-run at the app's real default timeouts (after an earlier diagnostic bump had been reverted per this session's own request) failed `qwen3:4b` outright — 0/5, every case `backend_unavailable`. Its thinking-mode latency doesn't fit inside the timeouts the app would actually ship with, independent of the tool-use question entirely.
- **`phi4-mini`:** a more interesting failure. A minimal, isolated `curl` request against `/api/chat` (bypassing this app's own prompt/context entirely) showed the model *attempting* tool use — it names `get_medication_details` correctly and writes plausible-looking arguments — but as prose inside its text response, wrapped in a markdown code fence, never through Ollama's structured `tool_calls` field. `result.tool_calls` is empty either way, so from the agentic loop's perspective this is indistinguishable from "chose not to." The model isn't failing to decide to use the tool; it's failing to route that decision through the wire protocol its own advertised `tools` capability implies it supports. No prompt wording reaches this — it's a template/packaging gap in how this quantization was built for Ollama.

**`granite4:3b` pulled as the next candidate — the first other model to actually clear the tool-use bar.** IBM's Granite 4, specifically trained for reliable function-calling from 3B up rather than general-purpose-plus-tools. First run: 4/5 convergence, and — the thing that actually mattered — `was_called: True` on both cases requiring a tool, through the real protocol. Two new problems alongside that success, each investigated rather than just noted:

- **Over-generation:** `groundedness_labs_vitals` produced 19 questions against the prompt's 8-15 ceiling. Traced to an asymmetry in the prompt itself — the *lower* bound had real primacy/recency reinforcement from PROMPT_CHANGELOG.md's v2-2026-07-19 fix, the upper bound was a bare mention. Fixed symmetrically (PROMPT_CHANGELOG.md v6): same reinforcement pattern, both directions. Re-run: 19→12 questions, `format_valid` False→True, and all 5 cases passed format validity for the first time in this whole model-comparison exercise.
- **A genuine hallucination bug, generalizable beyond this model:** `cold_start` (a deliberately medication-free fixture) hit `non_convergence` after 6 tool calls — 4 of them `get_medication_details`, every one correctly returning "No matching medications found," the model apparently unwilling to accept that answer and move on. Per DEC-013's existing design, non-convergence discards everything the loop found and falls back to a single-shot call with only the *base* context — no medication data either way. Told to reference real medication names and given none, the model invented a literal unfilled template placeholder: `"I currently take [list any known medications here] for my seasonal allergic rhinitis."` This isn't a `granite4:3b`-specific defect — any model landing on this fallback path for a data-sparse case is exposed to the same gap, since the loop's real, already-confirmed findings are thrown away rather than passed forward.

**Fix: the fallback now reuses what the agentic loop already learned.** `_render_gathered_tool_results` (`src/agents/visit_prep.py`) renders `self.last_tool_calls` — already populated in place at the point of failure, since it's the same list object bound in `__init__`, not a fresh one lost when the loop raises — as plain text, skipping the two placeholder markers (duplicate-call, budget-exceeded) that add nothing. When non-empty, it's appended to the fallback's messages with an explicit instruction not to invent content for anything already answered, including a confirmed absence. Re-run: no more placeholder — `cold_start`'s fallback correctly omits "Medication Review" entirely instead of inventing one. The `non_convergence` itself is still open (the model still burns its full turn budget re-querying an empty result before giving up); this fix addresses the *consequence*, not that root cause, which is a smaller, separate optimization left for later.

**Net position after this round:** `llama3.2:latest` and `granite4:3b` are both confirmed viable for the agentic tool-use path, each with known and now-smaller rough edges. `qwen3:4b` and `phi4-mini` are discarded — not for lack of trying, but because each hit a genuine model/runtime-level wall a prompt can't reach. The distinction between "tried and failed" and "structurally blocked" mattered here specifically because it stopped further prompt-iteration effort from being spent against problems no prompt could fix.

**Files changed:** `src/agents/visit_prep.py`, `docs/notes/DECISIONS.md` (DEC-038), `docs/notes/PROMPT_CHANGELOG.md` (v5, v6), `docs/notes/DEVELOPMENT_LOG.md`.

Related: DEC-037, DEC-038, DEC-013 (fallback design), DEC-009 (original small-model caveat), entry #62, PROMPT_CHANGELOG.md v2-2026-07-19 (the lower-bound fix v6's upper-bound fix mirrors).

---

## 62. Small-Model Tool-Calling Reliability Review: Convergence Metric, and a Truncation Bug Found and Fixed (DEC-037)

**Date:** 2026-08-20

**Context:** a conversation-driven review of whether local (Ollama) tool-calling is actually reliable, or just gracefully degraded, per DEC-009's original caveat. First step: extend `eval/run.py` with a tool-call convergence metric (`eval/scorers.py::score_tool_call_convergence`, reading the existing `agentic_path`/`fallback_reason` fields) and a `--trials` flag, so convergence rate could be measured rather than guessed. First real run (against `llama3.1:latest`, an 8B model) came back at 20% convergence with mostly `backend_unavailable` failures — which turned out to be a stale DB row from 2026-07-10 test data overriding the intended `.env` default model, plus every call hitting a 120s connect timeout regardless. Neither was a code bug in the reliability sense; both were environment/config issues the investigation had to clear before the real question (is small-model tool-calling reliable) could be answered at all.

**A/B/C comparison across three models fitting the 8GB M3** (`llama3.2:latest` 3B, `qwen3:4b`, `phi4-mini` 3.8B), using the harness's existing five synthetic `GENERATION_CASES` (no real patient data — see `eval/db.py::build_case`). All three converged 5/5 in the harness's shallow sense (no parse error, no non-convergence), but `tool_call_necessity_dosing` — a case designed to require `get_medication_details` — exposed two different failure modes underneath that identical-looking convergence number:

- **`qwen3:4b` and `phi4-mini` never called any tool, on any case, including this one** — `score_tool_call_necessity`'s `was_called: False` on both. The model answered confidently anyway, with 3-6 of its questions per case scoring ungrounded (fabricated against data it never retrieved). This is the more dangerous failure mode for a health app: it's silent, and nothing in the harness or the app itself currently flags it as anything other than a clean success.
- **`llama3.2:latest` did call the right tool** (`was_called: True`, grounded_rate 1.0 on that case) but over-called — 9 total tool calls in one case, several near-duplicate `lookup_past_visits` lookups — and its final response came back as JSON that failed to parse, silently repackaged by the existing raw-text fallback into a fake `"General Questions"` category.

**The `llama3.2:latest` truncation bug got its own full investigation and fix, written up in detail in DEC-037** — three hypotheses (turn-count cap, tool-result content budget, `ollama_num_ctx` size) were each tested against the harness and disproved in turn before the actual cause (the model hitting its own end-of-turn stop token one token before closing its JSON, not a truncation-by-limit) was isolated. The fix: a content-size tool-result budget (not a call-count cap, which was rejected for throttling legitimate multi-lookup turns as hard as redundant ones) plus a two-layer JSON repair — a code-level bracket-closer (`src/agents/base.py::_repair_truncated_json`) for the common case, and a single model-side "finish your own output" retry (`VisitPrepAgent._repair_response_via_model`) for the harder case where content itself, not just closing punctuation, went missing. Also fixed in passing: `llm_backend.py`'s context-budget warning never fired during any of this despite real truncation — it only checked input size against a flat threshold, not remaining room for the response — now corrected to reserve output tokens explicitly.

**Result:** `llama3.2:latest` went from 4/5 to 5/5 cases passing format validation, confirmed reproducibly. `qwen3:4b`/`phi4-mini`'s silent-non-tool-use failure is a different problem, untouched by this fix, and is the next step in the same review — a tool-use prompt nudge first, `granite4:3b` as a fallback candidate if that doesn't resolve it, discard both otherwise (silent hallucination is judged worse than `llama3.2`'s noisier but self-correcting failure mode).

**Files changed:** `eval/run.py`, `eval/scorers.py`, `src/agents/visit_prep.py`, `src/agents/base.py`, `src/agents/llm_backend.py`, `docs/notes/DECISIONS.md` (DEC-037), `docs/notes/DEVELOPMENT_LOG.md`.

Related: DEC-037, DEC-009 (original small-model tool-calling caveat), DEC-013 (fallback design), DEC-016 (Ollama default).

---

## 61. A Medication Stop No Longer Reports Success Without Stopping Anything (#149, DEC-035)

**Date:** 2026-08-09

**Context:** applying a parsed AVS "medication stop" set `Medication.end_date = _parse_date_string(med.date)`. That helper returns `None` for anything outside its four date formats — `"last week"`, `"6/1/26"`, a blank OCR field — and `None` is already what an active medication's `end_date` holds. So the write changed nothing while the plan still said `action: update`, `reason: "marks this medication stopped"`, and the response still counted it under `medications_stopped`. The user was told the medication was recorded as stopped; the profile still listed it as active. Pre-existing, not introduced by #143 — #143's preview only made it visible, as an `end_date: (empty) → (empty)` row.

**The fix is one helper, `_stop_end_date(date_str, visit_dt)`**, which returns the date to write *and* the reason to show, so the plan entry can't drift from what the write actually does:

- Readable stop date → that date, reason unchanged from today.
- Unreadable/missing stop date, readable visit date → the visit date, with the reason naming the substitution: `marks this medication stopped — stop date "last week" couldn't be read, using the visit date 2099-12-31`. Because the preview (#143) renders reasons and per-field diffs, the inference is reviewable *before* it commits, and the diff shows a real value change instead of empty-to-empty.
- Unreadable/missing stop date, unreadable visit date → `action: skip` in the existing `medications_stopped` skip bucket. Nothing written, and the count stops claiming otherwise.

**Why fall back rather than always reject.** Both were on the table in the issue. The two errors aren't symmetric: an inferred `end_date` is wrong by the gap between the real stop and the visit — usually days, and the visit date is the document's own anchor, already trusted by the `_is_newer` guard. Writing nothing is wrong about whether the patient is on the medication at all, which is the fact follow-up care actually reads. DEC-035 records the general rule this instance of: an apply never reports a change it didn't make.

**Deliberately not generalised to creates.** `start_date` on a medication create parses the same way and can also land as `None`, but a null start date honestly reads as "unknown" rather than as a different, wrong state — it isn't confusable with "still active" the way a null `end_date` is. Creates keep today's behaviour, pinned by `test_medication_start_still_accepts_an_unreadable_start_date` so the scoping is deliberate rather than an omission.

**`_parse_date_string` was left alone.** Adding `%m/%d/%y` would fix the `"6/1/26"` example specifically, but not the general case, and a parser that guesses more permissively fails in exactly the same silent direction this issue is about. Widening the *visible* failure path was the point; widening the parser can be argued separately on its own merits.

**Files changed:** `src/api/documents.py`, `tests/test_documents_apply.py`, `docs/notes/DECISIONS.md`, `docs/notes/DEVELOPMENT_LOG.md`.

Related: issue #149, DEC-035, #46/#143 (the preview that surfaced it).

---

## 60. Regenerating Visit Prep No Longer Destroys the Previous Output (#54, DEC-034)

**Date:** 2026-08-08

**Context:** `prepare_visit` (`src/api/visits.py:55-59`) reassigned `generated_questions`/`context_summary` on an existing `VisitPrep` in place. One click on "Regenerate Questions" — a prominent button on the prep page — permanently destroyed whatever the previous run produced, including any hand-edits made to it under issue #14. This is not a missing feature; it's silent, unrecoverable destruction of user content, which is why it was picked ahead of everything else on the backlog. Entry 56 (#46) had already deferred "the history table" as a substrate #12, #54 and #97 would each want, specifically to avoid designing it three times.

**Scope: piece 2 only — the durability fix. Piece 1 (a review gate before first persistence) is left to #12.** The issue offers both and asks whether they should wait on #12. They split cleanly: piece 2 needs no product decision and nothing it writes is discarded when #12 lands (an append-only history is a prerequisite for #12's per-claim table, not a competitor to it). Piece 1 *is* a review-UX decision #12 explicitly claims, and building an interim Save/Discard step now means building a review surface twice and deleting one — the throwaway work #12's own write-up warns against. #54 stays open for piece 1.

**A separate `visit_prep_versions` table, not extra rows in `visit_preps`.** `VisitPrep.appointment_id` is `unique=True`, and that constraint turns out to be load-bearing in a way the model definition doesn't advertise: it's what lets three separate modules — `visits.py`, the #110 checklist in `appointments.py`, and `profile_export.py` — treat "the prep for this appointment" as a single `scalar_one_or_none()` with no ordering or filtering. Dropping it to store history in place would change what `GET /api/visits/{id}/prep` *means* and turn each of those call sites into a latent "which row did I get?" bug. A separate table trades that diffuse correctness risk for a contained, purely additive schema change. Verified rather than assumed: the checklist and export paths both read `visit_preps` unchanged and needed no modification.

**Snapshot-then-overwrite.** One helper, `_snapshot_prep_version`, called immediately before the reassignment — and deliberately *after* `agent.prepare_visit()` returns, so a generation that raises leaves the existing prep untouched and archives nothing. `version_number` is 1-based and monotonic per prep, assigned `max(existing) + 1` rather than from a count on read, so a number can't change meaning later if versions ever become individually deletable. Version 1 is the *first content displaced*, i.e. the original generation.

**Three details that each prevent the history from being quietly wrong:**

- **`used_fallback` is snapshotted per version.** Without it, a real generation and issue #47's hardcoded "backend unreachable" placeholder look identical in the history — misleading rather than merely incomplete. Surfaced in the UI too, as a note on the affected version.
- **Both timestamps are kept.** `content_updated_at` (the displaced prep's `updated_at`) answers "when was this written"; `created_at` answers "when was it replaced". Keeping one would lose the other, and silently dropping a timestamp is the same class of loss this table exists to prevent.
- **Empty content isn't archived.** A prep with neither questions nor a summary has nothing worth preserving, and a version row for it would put a "Previous versions (1)" affordance in front of the user that opens onto nothing.

**Read-only history, no restore, no pruning.** `GET /api/visits/{appointment_id}/prep/versions` returns newest-first (`[]`, not 404, when there's no history — that's a normal state for a prep, not a missing resource), and `VisitPrep.tsx` gains a collapsed "Previous versions (N)" disclosure that expands to the old questions read-only. Restore would re-raise the same overwrite question one level up (does restoring clobber the current prep, or snapshot it too?), and the harm is already gone once the old content is visible and copyable. Nothing is pruned either: every regenerate keeps a row forever, which at single-user scale is a handful of small JSON blobs per appointment, and a retention rule would silently delete exactly the content this exists to protect. Both calls are the same instinct twice — every ambiguous decision here resolves toward keeping more and doing less to it.

**PATCH does not create a version**, pinned by a test so the boundary is explicit. This issue is about regeneration destroying content silently, not about undoing the patient's own deliberate edits; edit-undo would be its own decision. Note the snapshot still captures the *edited* state when a regenerate displaces it — which is the content that actually had value, and the exact scenario the issue describes.

**One addition beyond the issue: version history is included in profile export**, `EXPORT_FORMAT_VERSION` 1 → 2. Same reasoning as the table itself, and then some — this exists because overwritten prep content was worth not destroying, so an export that dropped it would re-introduce the loss at backup time. The bump is for a purely additive key, made anyway because only the version number distinguishes "no history was kept" from "this export predates history being kept".

**No backfill.** Generations overwritten before this table existed are gone. Synthesising a "version 1" row from current content would fabricate a history that never happened, which is worse than an empty one.

**Tests:** 10 new in `tests/test_visit_prep.py` — first generation archives nothing; regenerate archives exactly the displaced content while the live prep holds the new; three generations leave two versions numbered in displacement order and returned newest-first; a hand-edit survives a regenerate *in the history* (the issue's concrete harm scenario); PATCH creates no version; `used_fallback` snapshots independently of the current row (asserted against a genuinely failing backend, so the archived version reads `false` while the live prep reads `true`); `content_updated_at` matches the prep's own pre-regenerate `updated_at`; 404 for a missing appointment vs. `[]` for empty history; and versions scoped to their own appointment, since a broken join would leak one appointment's prior questions onto another's page. Plus 1 in `tests/test_profile_export.py` for the export, and 5 frontend tests in `frontend/src/pages/VisitPrep.versions.test.tsx` covering the disclosure — hidden with no history, collapsed by default, labelled per version, no restore affordance, and the fallback marker. Backend: 340 passed, 25 skipped (up from 329). Frontend: 38 passed (up from 33); `tsc -b` and `vite build` green.

**Migration checked by hand, not just generated:** applied to a fresh DB, downgraded, and re-applied; confirmed the downgrade leaves `visit_preps` intact. Diffed the migration's emitted DDL against the ORM metadata's — identical. A composite `(visit_prep_id, version_number)` index was written and then removed for that reason: it bought nothing at this scale and existed only in the migration, which is exactly the drift that makes a future autogenerate diff noisy.

**Files changed:** `src/data/models.py`, `src/api/visits.py`, `src/models/schemas.py`, `src/api/profile_export.py`, `alembic/versions/d3f81a6c204b_add_visit_prep_versions.py`, `tests/test_visit_prep.py`, `tests/test_profile_export.py`, `frontend/src/pages/VisitPrep.tsx`, `frontend/src/pages/VisitPrep.versions.test.tsx`, `frontend/src/api/client.ts`, `frontend/src/types/index.ts`, `docs/notes/DECISIONS.md` (DEC-034), `docs/notes/DEVELOPMENT_LOG.md`.

Related: issue #54 (piece 1 still open), DEC-034, issue #12, issue #14, issue #47, issue #97, issue #110, entry 56 (#46).

---

## 59. Eval Question-Count Floor Is Now Scope-Aware (#75, DEC-033)

**Date:** 2026-08-08

**Context:** `cross_specialty_scope` had been failing format validity since the v3 prompt work — 6 questions against a floor of 8 — and #75 asked which failure mode it was before changing anything: a data-sparse fixture the DEC-018 scaling should already cover, or the model under-delivering.

**It's the first, and the entity count was hiding it.** `expected_min_questions()` scaled by `len(known_entities(case)) * 2`, and `known_entities()` has no scope filter. `cross_specialty_scope` counts 4 entities — T2DM, Metformin, Mild Plaque Psoriasis, Clobetasol Cream — so `4 * 2 = 8` handed it the *full* flat floor with no scale-down. Two of those four are the dermatology material the prompt explicitly forbids raising at an endocrinology visit, which is the only reason the fixture exists. In scope, the case is as sparse as `cold_start`; it just didn't look sparse. So the model was being scored down for correctly declining to pad — the same tension with the anti-hallucination rules DEC-018 already recorded.

**The fix splits one function into two rather than narrowing it.** `known_entities()` has two callers with opposite needs, and this is the substance of the change. `score_groundedness()` asks *did the model invent this?* — it needs every real entity, including off-scope ones. `expected_min_questions()` asks *how much was there legitimately to ask about?* — it needs only in-scope ones. Narrowing the shared function would make a question about Clobetasol score as ungrounded (a hallucination) when it's a real entry in the patient's own record that `score_scope()` already flags, correctly, as a scope violation — one failure counted twice under two names, with the scope checker's signal destroyed in the process. So `known_entities()` is untouched and a new `in_scope_entities()` feeds the floor. Both now carry docstrings explaining why the other exists, because they look interchangeable and are not.

**Scope is read the way each entity type already encodes it.** Medications carry `prescribing_doctor_key`, so their specialty resolves and is compared to the target doctor's through the same `are_specialties_related()` the runtime scope logic uses — no second notion of relatedness. A medication with no prescriber, or a prescriber with no specialty, counts as **in** scope: absence of a scope signal isn't evidence of being off scope, and defaulting the other way would quietly deflate the floor for any fixture that just didn't tag one. Conditions have no doctor link and nothing structural marking them as one specialty's, so `ConditionFixture` gained an explicit `in_scope: bool = True`, set `False` only on the psoriasis entry. Lab orders are always counted.

**Why the fixture declares condition scope instead of the scorer deriving it from `icd_10`:** the alternative was mapping ICD-10 prefixes through `ICD10_SPECIALTY_MAP`, which is the hand-authored surface #72/#74 are mid-consolidation on. Coupling the harness's floor to it would mean eval thresholds silently move when unrelated consolidation work lands — the one property a measuring stick must not have. The counter-objection is real and worth naming: this is the fixture grading itself, and a mislabelled fixture would lower its own bar. It's bounded (it only ever moves a floor, never a verdict) and the pinned floors below make any such change show up in a diff. Full tradeoff in DEC-033.

**Resulting floors, now pinned:** `cross_specialty_scope` 8→4, `groundedness_labs_vitals` 6 (unchanged — it was already below the flat 8 before this change), `cold_start` 3, `tool_call_necessity_dosing` 8, `retrieval_redundancy` 4. `EXPECTED_FLOORS` in the test module pins each one with a comment on where the number comes from, plus a test asserting every fixture case appears in that map so a newly added case can't skip the check by omission.

**Worth saying out loud:** a floor of 4 means format validity is close to vacuous for `cross_specialty_scope` — it has largely stopped testing question *volume* there. Defensible, since the signal that matters for that fixture is the scope checker rather than the count, but it's a genuine reduction and better recorded than discovered. And with two cases now scaling below the documented flat 8, the exceptions are becoming the pattern; whether 8 is still the right default is left open rather than answered here.

**Tests:** 10 new in `tests/test_eval_harness.py` — the five parametrised pinned floors, the every-case-is-pinned guard, the off-scope exclusion, a test that `known_entities()` stays scope-blind (asserting the same Clobetasol question scores grounded *and* as a scope violation, which is the invariant that would break if someone later "simplifies" the two functions back into one), the original 6-questions-now-passes case with a 3-questions-still-fails counter-check so the floor isn't vacuous in both directions, and the untagged-prescriber default. Suite: 339 passed, 25 skipped (up from 329). No frontend changes.

**No prompt change**, so no version bump and no `PROMPT_CHANGELOG.md` entry — this is a scorer-threshold change, which is why it needed a DEC instead.

**Files changed:** `eval/scorers.py`, `eval/fixtures.py`, `tests/test_eval_harness.py`, `docs/notes/DECISIONS.md` (DEC-033), `docs/notes/DEVELOPMENT_LOG.md`.

Related: issue #75, DEC-033, DEC-018, PROMPT_CHANGELOG.md v3 entry, issue #72, issue #74.

---

## 66. OpenMed Benchmark Re-Run: Bias-Corrected Corpus, Label Filtering, Wider Sweep, and a Latency Bug That Inflated the Original Cost Numbers ~70× (#122 follow-up)

**Date:** 2026-08-23

**Context:** entry #50 (PR #124, `eval/prototypes/OPENMED_FINDINGS.md`) evaluated OpenMed against the current regex(+NER) PII anonymizer and found no OpenMed configuration beat it on both recall and precision, at 400×–1500× the latency. That report named three of its own caveats as reasons the numbers might not hold up: the corpus was transcribed from `tests/test_anonymization.py` (structurally favors the regex approach it specifies), per-category sample sizes were small enough that one case swings a rate 25-33%, and OpenMed's over-redactions traced to a confirmed label-taxonomy mismatch that "any future integration would need real label filtering" for — but the original run scored OpenMed's raw output anyway, never testing the filtered variant it called for. The user asked to rerun addressing all three, for a planned research-paper write-up, so this pass also widened the model/confidence sweep those caveats had flagged as narrow.

**What changed, in order:**

1. **New corpus, not a replacement.** `eval/prototypes/openmed_pii_cases_v2.py` — 50 positive / 46 negative cases, written independently as natural clinical-note sentences with PII in context (`"Discussed lab results with Aisha Khan over the phone this afternoon."`) rather than transcribed pattern fragments. The harness runs both corpora side by side rather than swapping one for the other, so a finding has to hold on both to count. It moved a headline number a lot: bare `regex` drops from 94% recall (v1) to 74% (v2) — free-text names and standalone zip codes (not attached to a street address) are exactly the shapes the original corpus didn't stress, because it was written to specify what regex catches.
2. **Sample size** — v2 roughly doubles negative-case coverage and widens category breadth versus v1; reported per-category rather than pretending the combined N erases single-case swings (still a caveat, just a narrower one).
3. **Label filtering, the caveat the original report predicted but never tested.** `eval/prototypes/openmed_pii_prototype_v2.py` adds an `openmed-filtered` system that only redacts entities whose canonical label is in `PROJECT_REDACT_LABELS` — OpenMed's own `openmed.critical_labels()` plus `DATE`/`ZIPCODE` (this project's policy redacts both categories wholesale; OpenMed's general-purpose taxonomy doesn't). Built from the installed package at runtime so it tracks upstream label changes. Confirmed the original prediction: filtering raised precision from 71%→88% (v1) and 87%→98% (v2) at confidence 0.5, small model, for a small recall cost.
4. **Wider sweep** — 2 corpora × 2 model sizes × 3 confidence thresholds × 4 systems = 24 configurations (vs. the original's 6), run in an isolated venv (`python3.11 -m venv /tmp/venv-openmed-v2`; `openmed==2.2.0` this time, no `transformers` pin workaround needed — the original run's `local_files_only` incompatibility is gone in this release). Also installed spaCy in the same venv, which the original run couldn't do, so `regex+ner` — DEC-006's actual intended configuration — got measured for the first time instead of skipped.

**Two harness bugs found and fixed mid-run — the second one changed the headline conclusion.**

**Bug 1 (label case mismatch):** the first `openmed-filtered` run reported **0/67 recall** — every entity dropped. Cause: `extract_pii` returns lowercase raw model labels (`last_name`, `phone_number`), not the uppercase `CANONICAL_LABELS` vocabulary `critical_labels()` is expressed in, so the string-equality filter matched nothing. Fixed by routing every label through `openmed.normalize_label()` before comparing.

**Bug 2 (model-reload latency, ~70× effect on every cost number reported):** the initial full sweep measured OpenMed's small model at ~900-1030ms/text and the large model at ~3000-3440ms/text — in the same range as PR #124's original numbers. Both were wrong. `openmed.extract_pii()` rebuilds the model pipeline from scratch on every call unless a reusable `openmed.ModelLoader` is explicitly loaded once and passed in as `loader=`; neither this harness's first pass nor, apparently, the original PR #124 benchmark did this, so every timed call included a full model reload on top of actual inference. This was not caught by the harness itself — nothing internal flagged it, since every call looked equally slow. It surfaced only because the user asked in conversation whether there was any way to run OpenMed "in a lightweight fashion" that hadn't been tried, which prompted inspecting `openmed`'s public API for a caching/reuse mechanism instead of accepting the numbers at face value. With a cached, reused loader (`_get_loader` in `openmed_pii_prototype_v2.py`, module-scoped, keyed by model name): **small model ~13-17ms/text, large model ~59-70ms/text** — roughly 5-20× `regex+ner`'s ~2-4ms, not 300×-1000×. Recall/precision were verified byte-identical before and after the fix on every configuration — this was purely a cost-measurement bug, not a detection-accuracy one. Side effect: the full 24-configuration sweep that took over two and a half hours before the fix now completes in under eight minutes.

**Memory, re-measured in isolation post-fix:** `regex` ~281MB (floor), `regex+ner` +65MB (spaCy resident), OpenMed small model +431MB, OpenMed large model +323MB — the large model using *less* memory than the small one is unexpected but reproduced twice in fresh processes; most likely both are dominated by fixed PyTorch/transformers overhead at this parameter scale, and the original report's "large model uses 3× the memory" finding is itself probably an artifact of the same reload bug (repeated transient model construction inflating the peak-RSS high-water mark more for the bigger model's larger buffers).

**Headline result, corrected framing:** `regex` (no NER) is what HealthSteward actually ships — DEC-006's 2026-08-06 amendment confirmed spaCy is absent from both dependency manifests, so `regex+ner` is aspirational, not live. Against that real baseline, OpenMed wins recall by a wide margin (74%→94-100% on the bias-corrected corpus) at a cost that is no longer decisive the way the original 300×-1000× figure suggested — corrected, it's ~15-60ms/text (imperceptible per redaction call) and ~400-600MB resident (a real, but much smaller and now-accurately-characterized, memory tradeoff on an 8GB M3 target). Against `regex+ner` specifically, neither OpenMed configuration strictly dominates it on recall/precision (each wins one axis, loses the other), except on one axis: OpenMed does not reproduce the drug-name-as-`PERSON` over-redaction that is the documented reason `regex+ner` isn't shipped — this re-run's v2 corpus independently reproduced that exact bug (`Lisinopril`/`Atorvastatin` redacted whole under `regex+ner`, correctly left alone under both OpenMed variants), on fresh cases, at every confidence tested. **This does not reopen #125 or point at a cheap fix for spaCy itself**: that issue's own earlier follow-up already swept 205 real drug names through spaCy and found a ≥1-context `PERSON` misfire rate of 69%, too unreliable for a denylist/allowlist to patch, and closed with no forcing function since spaCy isn't installed anywhere it ships. **Decision: still no code change today** — keep not adopting full-anonymizer OpenMed, keep NER off, both remain correct calls. But the corrected cost numbers put one new, narrower option in reach that would have looked absurd under the original (buggy) figures: a name-detector-only integration using a clinical-taxonomy model instead of general-purpose spaCy, at ~15ms/~400MB rather than full OpenMed's larger scope — not built or scoped here, flagged as the one idea worth a follow-up if #125 is ever revisited. Also worth recording, not a new bug: a standalone zip code (`"mailing zip is 97205"`, no street address, no ZIP+4) survives both `regex` and `regex+ner` on v2, but `PII_PATTERNS['zip_code']`'s own comment already documents this as deliberate — "a bare 5-digit ZIP is indistinguishable from an ordinary number in clinical text" — so this re-run just supplies the first measured instance (2/50 cases) of an already-accepted tradeoff, not a new finding to file. Full numbers, per-configuration tables, the drug-name-as-PERSON section, the full loader-reuse account, and all leak/over-redaction detail: `eval/prototypes/OPENMED_FINDINGS_V2.md`; raw JSON in `eval/prototypes/reports/v2/`.

**No DEC entry** — same scope note as entry #50: this is an evaluation, not a production change. `src/utils/anonymization.py` is untouched and `openmed` remains absent from both dependency manifests.

**Files changed:** `eval/prototypes/openmed_pii_cases_v2.py`, `eval/prototypes/openmed_pii_prototype_v2.py`, `eval/prototypes/OPENMED_FINDINGS_V2.md`, `eval/prototypes/reports/v2/*.json`.

Related: issue #122, entry #50, PR #124, `OPENMED_FINDINGS.md`, DEC-006, DEC-009.

---

## 67. `PII_PATTERNS` Extended to Close 7 HIPAA Safe Harbor Gaps, With Two Adversarial False Positives Found and Fixed Before Merging (DEC-040)

**Date:** 2026-08-23

**Context:** direct continuation of entry #66's line of work. Mapping `PII_PATTERNS` against HIPAA Safe Harbor's 18 identifier categories (rather than an informal "PII protection" framing) found 8 of 16 testable categories already covered and 7 with no dedicated pattern: fax, account numbers, certificate/license numbers, vehicle identifiers, device identifiers, URLs, and IP addresses. (16, not 18: biometric identifiers and full-face photographs are out of scope by construction for a text-only document parser; the open-ended catch-all category, #18, can't be closed by any fixed pattern list.) A prototype eval harness (`eval/prototypes/phi_gap_prototype_v3.py`, `eval/prototypes/phi_gap_cases_v3.py`) scored `regex`, `regex-extended` (the 6 new patterns layered on top), `regex+ner-extended`, `openmed`, and `openmed-filtered` against a 20-case corpus targeting these categories: `regex` alone got 40% recall, `regex-extended` and `regex+ner-extended` both hit 100%/100% and 100%/90% respectively (the one over-redaction being the pre-existing, unrelated `Lisinopril`-as-`PERSON` bug, confirmed by checking — not caused by the new patterns), and — notably — `openmed-filtered` scored worst of all five (45% recall), because several raw labels OpenMed's own model produces (`ipv4`, `fax_number`, `vehicle_identifier`, `device_serial_number`) fall through `openmed.normalize_label()` to the generic `OTHER` bucket instead of their valid canonical label, even when that canonical label (e.g. `IP_ADDRESS`) is confirmed present in `critical_labels()`. Filed as upstream feedback for the OpenMed project (not yet submitted — drafted, held pending user review), since it's a bug in their normalization table, not an integration mismatch on this project's side.

**Before merging into production, two of the six new patterns were found to over-redact real clinical content on adversarial test cases not in the original 20-case corpus** — caught by deliberately trying to break them, the same discipline entry #66 applied to `regex+ner`'s drug-name bug:
- `license_number`'s bare `Certificate`/`Cert` trigger matched `"Certificate of medical necessity CMN-4471"` (a document type, not an identifier) and `"Prior authorization Certificate #: PA-991244"` (an insurance authorization number, arguably identifying but not what this pattern was meant to catch). Narrowed to `Driver's License`/`License`/`DEA` only.
- `device_serial`'s bare `Serial` trigger matched `"Batch Serial: LOT-88213"` — a vaccine/medication lot or batch number identifies a manufacturing run, not an individual, so this isn't even a real HIPAA identifier, and redacting it destroys clinically useful content (which lot was administered matters for recalls) for zero privacy benefit. Fixed with a negative lookbehind excluding `Lot`/`Batch` immediately before `Serial`.

Both narrowed patterns were re-verified against the two adversarial cases (now correctly left alone) plus the original positive cases (still caught) plus a combined 88-case negative sweep (the existing 70 v1/v2 cases + the new 18-case adversarial set) — zero false positives before merging.

**What shipped:** `src/utils/anonymization.py` — 6 new `PII_PATTERNS` entries (`url`, `ip_address`, `license_number`, `account_number`, `vehicle_id`, `device_serial`), 4 new `PII_REPLACEMENTS` label-anchored templates, 6 new `TOKEN_TYPES` entries, module docstring updated to state the 16-of-18 Safe Harbor coverage claim explicitly (with the fax/catch-all caveats spelled out rather than implied). `tests/test_anonymization.py` — `TestSafeHarborGapPatterns` class, 16 cases initially, including the two adversarial negative cases as regression guards against the exact over-redaction that was found and fixed. Verified against the full existing v1/v2 evaluation corpora (187 cases) with zero regressions — same 17 pre-existing name/standalone-zip leaks as before (regex's known, documented no-NER-name-detection gap), nothing new introduced.

**Follow-up, same session: an adversarial rigor gap and a real-document sanity check.** `account_number`/`vehicle_id` had shipped clean (no false positive found), but hadn't been adversarially probed with the same intensity that found and fixed `license_number`/`device_serial`'s issues — a real asymmetry, not just a hypothetical one, since those two patterns were only narrowed because someone specifically went looking for label-trigger overlap with non-identifying prose. A parity check (10 cases: `"Account of the patient's fall..."`, `"On account of the recent surgery..."`, `"Registration for the diabetes education class..."`, a valueless `"no VIN was recorded"` mention, plus 2 less-templated positive phrasings) found zero false positives — but had run as a throwaway script, not a committed test, so it was pinned as those same 10 cases, permanently, across 4 new test functions (`test_account_number_less_templated_phrasing_redacted`, `test_account_word_in_non_identifying_context_not_redacted`, `test_vin_hash_label_variant_redacted`, `test_vehicle_adjacent_words_in_non_identifying_context_not_redacted`) rather than left as evidence that only existed in a shell session. `TestSafeHarborGapPatterns` now collects **26 test cases** total (`pytest --collect-only`-verified — an earlier "16 + 18 = 34" claim in this entry was wrong arithmetic, caught before it reached the paper; the correct count is 16 + 10 = 26). Full `tests/test_anonymization.py` re-run in the real project conda env (`/opt/anaconda3/envs/healthsteward` — the earlier "153 passed" figure above was actually run against a shell missing `sqlalchemy`/spaCy and had to be re-verified with the real env to mean anything): **153 passed, 28 skipped** (spaCy-dependent cases, expected), zero failures.

Also ran a real-document spot check — the 3 actual AVS PDFs in `data/avs/` (gitignored, local-only, the user's own real documents), through the project's real `pdfplumber` extractor, not synthetic text. Reported as aggregate counts only, nothing extracted/redacted printed to the conversation, out of respect for the fact these are real documents. Result: `AVS-2.pdf` contained 2 real URLs that the new `url` pattern correctly caught — a genuine before/after finding on real data (these would have leaked into every Claude API call this document's data went through, before this session's work), not just a synthetic-corpus result — and zero leftover unredacted 7+ digit identifier-shaped runs across all three documents post-redaction. `license_number`/`device_serial`/`account_number`/`vehicle_id`/`ip_address` didn't fire on any of the three documents, so this doesn't independently validate those five specifically; they're just not present in these three notes.

**Fax numbers (#5) got a pinning test, not a new pattern** — they have no distinguishing format of their own and were already caught incidentally by the `phone` pattern; this was previously asserted only in prose, now pinned so it can't silently regress.

**DEC-040 entry added** — this changes what gets redacted on the DEC-006 trust boundary, so it gets the same documentation discipline as DEC-025's `mrn_unlabeled` amendment, not a quiet merge.

**Files changed:** `src/utils/anonymization.py`, `tests/test_anonymization.py`, `docs/notes/DECISIONS.md` (DEC-040), `eval/prototypes/phi_gap_cases_v3.py`, `eval/prototypes/phi_gap_prototype_v3.py`.

Related: issue #122, entry #66, DEC-040, DEC-006, DEC-025, DEC-009, issue #125.

---

*This document will be updated at periodic checkpoints as development continues.*
