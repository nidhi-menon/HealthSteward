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

---

*Last updated: 2026-02-05*
