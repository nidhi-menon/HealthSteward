# HealthSteward Implementation Journal

This document tracks implementation details, architectural decisions, and how components work together. Use this as a reference when working on the project or to understand how things were built.

---

## Table of Contents
- [Project Overview](#project-overview)
- [Phase 1: Health Profile + Visit Prep](#phase-1-health-profile--visit-prep)
- [Phase 2: AVS PDF Processing](#phase-2-avs-pdf-processing)
- [Phase 3: Proactive Action Items](#phase-3-proactive-action-items)
- [Phase 4: Pluggable LLM Backend + Agentic Tool-Use](#phase-4-pluggable-llm-backend--agentic-tool-use)
- [Architecture](#architecture)
- [Component Deep Dives](#component-deep-dives)
- [API Reference](#api-reference)
- [Testing Strategy](#testing-strategy)
- [Future Phases](#future-phases)

---

## Project Overview

**HealthSteward** is a privacy-first AI health coordination system that helps users:
- Track health profiles, conditions, medications, and doctors
- Prepare for doctor visits with AI-generated questions
- (Future) Sync with calendars, send medication reminders, use RAG for health documents

**Tech Stack:**
- **Backend:** FastAPI (async)
- **Frontend:** React + TypeScript + Tailwind CSS
- **Database:** SQLite (dev) / PostgreSQL (prod) via SQLAlchemy 2.0 async
- **AI:** Pluggable backend (local Ollama by default, or Anthropic Claude API, or any custom OpenAI-compatible provider — DEC-016) for visit prep's agentic tool-use loop; Ollama also handles PDF parsing and context-selection relevance scoring
- **Migrations:** Alembic
- **Testing:** pytest with pytest-asyncio

---

## Phase 1: Health Profile + Visit Prep

**Completed:** 2026-02-05

### What Was Built

A complete vertical slice enabling users to:
1. Create and manage health profiles with personal info
2. Track medical conditions, medications, and doctors
3. Schedule appointments
4. Generate AI-powered visit preparation questions

### Files Created

```
src/
├── config.py                 # Pydantic Settings (env loading)
├── utils/
│   └── logging.py            # Loguru setup with rotation
├── data/
│   ├── database.py           # Async SQLAlchemy engine + sessions
│   └── models.py             # ORM models (7 tables)
├── models/
│   └── schemas.py            # Pydantic request/response schemas
├── api/
│   ├── health_profile.py     # /api/profiles/ CRUD
│   ├── conditions.py         # /api/profiles/{id}/conditions/ CRUD
│   ├── medications.py        # /api/profiles/{id}/medications/ CRUD
│   ├── doctors.py            # /api/profiles/{id}/doctors/ CRUD
│   ├── appointments.py       # /api/profiles/{id}/appointments/ CRUD
│   └── visits.py             # /api/visits/{appt_id}/prepare + /prep
├── agents/
│   ├── base.py               # BaseAgent with Claude client
│   └── visit_prep.py         # VisitPrepAgent for question generation
└── main.py                   # FastAPI app with lifespan + routers

tests/
├── conftest.py               # Fixtures (in-memory SQLite, test client)
├── test_health_profile.py    # CRUD tests
└── test_visit_prep.py        # Visit prep tests (mocked Claude)

alembic/
├── env.py                    # Async-configured for SQLAlchemy
└── versions/
    └── 1579e0bef709_initial_migration.py

docs/
└── IMPLEMENTATION.md         # This file
```

### Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| **UUIDs as primary keys** | Privacy-friendly, portable across databases, no sequential ID leakage |
| **Async everywhere** | Better performance for I/O-bound operations (DB, API calls) |
| **`src/models/` = Pydantic, `src/data/` = ORM** | Avoids naming conflicts; clear separation of concerns |
| **Profile-nested routes** | `/api/profiles/{id}/conditions/` naturally enforces data ownership |
| **Conversation logging** | Every Claude call logged with token counts for future model distillation |
| **JSON response parsing with fallback** | Robust handling: direct parse → code block extraction → raw text |

---

## Phase 2: AVS PDF Processing

**Completed:** 2026-06 (see DEC-010)

### What Was Built

Local-first processing of After-Visit Summary PDFs:
1. Drop PDFs into `data/avs/` and scan for new files via API
2. Parse with Ollama (local LLM) — deterministic section routing for structured sections, LLM for unstructured
3. Review parsed results and selectively apply to the health profile
4. Extracted models: Vitals, LabOrder, Referral, FollowUp (persisted to DB)

### Files Added

```
src/
├── utils/
│   ├── anonymization.py      # Three-layer PII scrubbing before external LLM calls
│   └── context_selection.py  # Four-stage context selection for visit prep
├── api/
│   └── documents.py          # /api/profiles/{id}/documents/* — scan, parse, apply
├── parsers/
│   ├── __init__.py
│   ├── avs_parser.py         # Orchestrator: section routing → structured + LLM parsers
│   ├── structured_sections.py# Deterministic extractors for vitals, meds, diagnoses
│   ├── llm_sections.py       # Ollama-backed extractors for free-text sections
│   └── agent/
│       ├── ollama_chat.py    # Ollama HTTP client with localhost safety check
│       └── tools.py          # Structured output tool definitions
```

### Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| **Section-routing parser** | Deterministic for structured fields (vitals, ICD codes), Ollama only where needed |
| **Localhost safety check** | `_check_localhost()` blocks any non-localhost Ollama URL — PHI never leaves the machine |
| **Selective apply** | User reviews and approves each parsed item before it's written to the profile |
| **Apply returns action items** | Apply endpoint returns extracted FollowUp/LabOrder/Referral inline — avoids a second fetch |

---

## Phase 3: Proactive Action Items

**Completed:** 2026-07 (see DEC-012)

### What Was Built

Proactive nudges surfaced from existing profile data — no new data entry required:
1. **Post-AVS panel** — shown immediately after applying an AVS; lists extracted follow-ups, lab orders, referrals with one-click confirmation
2. **Overview action items section** — always-visible dashboard on the Overview tab

### Nudge Types

| Nudge | Trigger | Aging |
|-------|---------|-------|
| Visit prep needed | Scheduled appointment in next 30 days, no VisitPrep record | Days until appointment |
| Appointments to close out | Past appointment still in `scheduled` status | Days since appointment |
| Missing AVS | Completed appointment, no Document within 14-day window | — |
| Vitals trends | ≥2 Vitals records; thresholds: weight ≥5 lbs, BMI ≥1.5, BP ≥10 mmHg, HR ≥10 bpm | Visit count |
| Follow-up appointments | FollowUp records in `pending` status | Fraction of timeframe elapsed; red if overdue |
| Lab orders | LabOrder records in `ordered` status | Stale after 21 days; warning if next appt ≤21 days |
| Referrals | Referral records in `pending` status | Stale after 60 days |

### Files Added

```
src/
├── api/
│   └── action_items.py       # GET/PATCH endpoints for follow-ups, lab orders, referrals,
│                             # vitals alerts, upcoming-without-prep, completed-without-avs

frontend/src/
├── components/
│   ├── PostAvsActionPanel.tsx # Amber panel shown after AVS apply; quick-confirm buttons
│   └── ActionItemsSection.tsx # Overview tab dashboard; all nudge types with badge counts
```

### Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| **Server-side past-due endpoint** | `GET /past-due-appointments` filters via NudgeState so snooze survives page refresh — consistent with all other computed nudges |
| **`timeframeToDays()` heuristic** | Parses free-text timeframes ("6 weeks", "3 months") to days for aging calculations |
| **14-day proximity window** | Matches completed appointments to documents by visit_date proximity since the FK isn't always populated |
| **`refetchInterval: 30_000`** | Documents tab auto-polls so scan results appear without manual refresh |
| **Snooze via NudgeState** | Computed nudges (no persistent row) store snooze state in `NudgeState` table; FollowUp/LabOrder/Referral store it inline on `snoozed_until` |
| **Resolved history** | `?include_resolved=true` on list endpoints returns completed items (capped at 20, `nullslast` on `completed_at desc`); frontend lazy-loads only when toggle is on |
| **Previously snoozed indicator** | Any active item with non-null `snoozed_until` had an expired snooze — backend already filters active snoozes, so no date comparison needed in frontend |
| **Flexible snooze** | `[1w][2w][1m]` pill group replaces single "Snooze 1w" button; `snoozeDate(days)` takes an argument; same pattern in ActionItemsSection and PostAvsActionPanel |

---

## Phase 4: Pluggable LLM Backend + Agentic Tool-Use

**Completed:** 2026-07-06 (see DEC-013)

### What Was Built

DEC-009's agentic visit-prep architecture, implemented from the start behind a pluggable backend that works for both Claude API and local Ollama — previously `prepare_visit()` was single-shot only, with no tool-calling anywhere in the codebase.

1. **`LLMBackend` abstraction** (`src/agents/llm_backend.py`) — `ClaudeBackend` and `OllamaBackend` implementations behind a common interface (`call()`, `build_assistant_message()`, `build_tool_result_message()`); `get_llm_backend()` factory keyed off `settings.llm_provider`
2. **Tools** (`src/agents/tools.py`) — `get_medication_details` and `lookup_past_visits`, both read-only, anonymized before returning to the loop for either backend
3. **Agentic loop** (`VisitPrepAgent._run_agentic_loop`) — bounded by `agent_max_turns`; falls back to the original single-shot call on `ToolCallParsingError` or non-convergence

### Files Added

```
src/agents/
├── llm_backend.py   # LLMBackend ABC, ClaudeBackend, OllamaBackend, ToolCall/LLMTurnResult
└── tools.py          # VisitPrepTools, claude_tools()/ollama_tools() spec adapters

tests/
├── test_llm_backend.py
└── test_agent_tools.py
```

### Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| **Fallback, not hard failure** | If the loop can't converge within `agent_max_turns` or a backend's tool-call output is malformed, `prepare_visit()` falls back to the single-shot `_call_backend()` (consolidated across all three providers per DEC-016) — no regression risk on any backend |
| **Descoped: real drug-interaction checker** | `get_medication_details` exposes existing structured medication data for the model to reason over; it is not a real interaction-checking API/DB (would need a licensed external service) — tracked in GitHub issue #24 |
| **Descoped: user-facing clarifying-question pause** | Would need new DB state, a new API endpoint, and new frontend UI to resume a paused conversation — tracked in GitHub issue #15 |
| **Anonymize tool results the same way for both backends** | Consistent with how the main context was already anonymized regardless of provider before this change — avoids fragile backend-aware branching |

---

## Architecture

### Request Flow

```
Client Request
     │
     ▼
┌─────────────┐
│   FastAPI   │  ← Validates with Pydantic schemas
│   Router    │
└─────────────┘
     │
     ▼
┌─────────────┐
│  get_db()   │  ← Dependency injection for async session
│  Dependency │
└─────────────┘
     │
     ▼
┌─────────────┐
│  SQLAlchemy │  ← ORM operations on models
│   Session   │
└─────────────┘
     │
     ▼
┌─────────────┐
│   SQLite/   │  ← Persistent storage
│  PostgreSQL │
└─────────────┘
```

### Visit Prep Flow

```
POST /api/visits/{appt_id}/prepare
     │
     ▼
┌─────────────────────────────────┐
│ Load Appointment with:          │
│ - Profile (conditions, meds)    │
│ - Doctor info                   │
└─────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────┐
│ 4-stage context selection       │
│ + PII anonymization             │
└─────────────────────────────────┘
     │
     ▼
┌───────────────────────────────────────────────────┐
│ VisitPrepAgent._run_agentic_loop()                 │
│ - get_llm_backend(): Ollama (default), Claude,     │
│   or custom (DEC-016)                              │
│ - Model may call tools before finishing:           │
│   get_medication_details,                          │
│   lookup_past_visits (tool results                 │
│   anonymized before re-entering loop)              │
│ - Bounded by agent_max_turns                       │
│ - Logs conversation to DB                          │
└───────────────────────────────────────────────────┘
     │  (falls back to single-shot _call_backend()
     │   if loop doesn't converge or tool-calling
     │   fails — see DEC-013)
     ▼
┌─────────────────────────────────┐
│ Parse JSON response             │
│ - Extract questions by category │
│ - Generate context summary      │
└─────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────┐
│ Store VisitPrep in database     │
│ Return to client                │
└─────────────────────────────────┘
```

---

## Component Deep Dives

### 1. Configuration (`src/config.py`)

Uses Pydantic Settings to load from `.env` file with sensible defaults:

```python
class Settings(BaseSettings):
    anthropic_api_key: Optional[str] = None
    database_url: str = "sqlite+aiosqlite:///data/healthsteward.db"
    log_level: str = "INFO"
    # ... more settings
```

Access anywhere via `get_settings()` (cached with `@lru_cache`).

### 2. Database Models (`src/data/models.py`)

Seven tables with relationships:

```
HealthProfile (1) ─────┬──── (*) Condition
                       ├──── (*) Medication
                       ├──── (*) Doctor ──── (*) Appointment
                       ├──── (*) Appointment ──── (1) VisitPrep
                       ├──── (*) Document ──── (*) Vitals
                       │                  ──── (*) LabOrder
                       │                  ──── (*) Referral
                       └──── (*) FollowUp

ConversationLog (standalone - for AI training data)
```

Key model patterns:
- All use `Mapped` type hints (SQLAlchemy 2.0 style)
- UUID primary keys via `default=generate_uuid`
- `created_at` / `updated_at` timestamps with `func.now()`
- Cascade deletes for child relationships

### 3. Database Sessions (`src/data/database.py`)

```python
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()  # Auto-commit on success
        except Exception:
            await session.rollback()  # Rollback on error
            raise
```

Used as FastAPI dependency: `db: AsyncSession = Depends(get_db)`

### 4. API Routes Pattern

All routes follow the same CRUD pattern:

```python
@router.post("/", response_model=ResponseSchema, status_code=201)
async def create_item(item: CreateSchema, db: AsyncSession = Depends(get_db)):
    db_item = Model(**item.model_dump())
    db.add(db_item)
    await db.flush()      # Get ID without committing
    await db.refresh(db_item)  # Load generated fields
    return db_item
```

Nested routes verify parent exists first:
```python
async def verify_profile_exists(profile_id: str, db: AsyncSession):
    result = await db.execute(select(HealthProfile).where(...))
    if not result.scalar_one_or_none():
        raise HTTPException(404, "Profile not found")
```

### 5. Claude Agent (`src/agents/base.py`)

Base class provides:
- `AsyncAnthropic` client initialization
- `_call_claude()` method with automatic conversation logging
- `_parse_json_response()` with fallback chain

```python
async def _call_claude(self, messages, system=None, max_tokens=None):
    response = await self.client.messages.create(
        model=self.settings.anthropic_model,
        messages=messages,
        system=system or "",
        # ...
    )
    await self._log_conversation(...)  # Save to ConversationLog table
    return response.content[0].text
```

### 6. Visit Prep Agent (`src/agents/visit_prep.py`)

Extends `BaseAgent` with:
- System prompt requesting categorized, prioritized questions
- `_build_anonymized_context()` to format patient data as markdown, after 4-stage context selection and anonymization
- `_run_agentic_loop()` (per DEC-009/DEC-013) — drives the tool-use loop via a pluggable `LLMBackend` (`src/agents/llm_backend.py`, Ollama by default, or Claude or a custom OpenAI-compatible provider, DEC-016), executing `get_medication_details`/`lookup_past_visits` tool calls (`src/agents/tools.py`) as requested, bounded by `settings.agent_max_turns`
- Falls back to the single-shot `_call_backend()` (provider-agnostic since DEC-016) if the agentic loop doesn't converge, tool-calling fails (`ToolCallParsingError`), or `agent_tool_use_enabled=False`
- Fallback questions if the LLM call fails entirely

Expected Claude response format:
```json
{
  "questions": {
    "Medication Questions": ["Question 1", "Question 2"],
    "Lifestyle Questions": ["Question 3"]
  },
  "context_summary": "Brief patient context..."
}
```

---

## API Reference

### Health Profiles
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/profiles/` | Create profile |
| GET | `/api/profiles/` | List all profiles |
| GET | `/api/profiles/{id}` | Get single profile |
| PATCH | `/api/profiles/{id}` | Update profile |
| DELETE | `/api/profiles/{id}` | Delete profile |

### Conditions (nested under profile)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/profiles/{id}/conditions/` | Add condition |
| GET | `/api/profiles/{id}/conditions/` | List conditions |
| GET | `/api/profiles/{id}/conditions/{cid}` | Get condition |
| PATCH | `/api/profiles/{id}/conditions/{cid}` | Update condition |
| DELETE | `/api/profiles/{id}/conditions/{cid}` | Delete condition |

*(Same pattern for `/medications/`, `/doctors/`, `/appointments/`)*

### Visit Preparation
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/visits/{appt_id}/prepare` | Generate visit prep (agentic loop, Ollama by default, or Claude / custom per `LLM_PROVIDER`, switchable from Settings) |
| GET | `/api/visits/{appt_id}/prep` | Get existing visit prep |

### Documents
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/profiles/{id}/documents/scan` | Scan `data/avs/` for new PDFs |
| POST | `/api/profiles/{id}/documents/parse-file` | Parse a PDF with Ollama |
| GET | `/api/profiles/{id}/documents/{doc_id}/parsed` | Get parsed items |
| POST | `/api/profiles/{id}/documents/{doc_id}/apply` | Apply selected items to profile |

### Action Items
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/profiles/{id}/follow-ups` | List active follow-ups (excludes completed + snoozed); `?include_resolved=true` returns completed items instead |
| PATCH | `/api/profiles/{id}/follow-ups/{fid}` | Update status or snoozed_until; auto-stamps completed_at |
| GET | `/api/profiles/{id}/lab-orders` | List active lab orders; `?include_resolved=true` returns completed items instead |
| PATCH | `/api/profiles/{id}/lab-orders/{lid}` | Update status or snoozed_until |
| GET | `/api/profiles/{id}/referrals` | List active referrals; `?include_resolved=true` returns completed items instead |
| PATCH | `/api/profiles/{id}/referrals/{rid}` | Update status or snoozed_until |
| POST | `/api/profiles/{id}/nudge-states` | Upsert snooze for a computed nudge (appointment-based, vitals) |
| GET | `/api/profiles/{id}/past-due-appointments` | Scheduled appointments whose date has passed; respects NudgeState snooze |
| GET | `/api/profiles/{id}/upcoming-without-prep` | Appointments in next 30 days with no VisitPrep; respects NudgeState snooze |
| GET | `/api/profiles/{id}/vitals-alerts` | Trend alerts across Vitals records; respects NudgeState snooze |
| GET | `/api/profiles/{id}/completed-without-avs` | Completed appointments missing a document; respects NudgeState snooze |

---

## Testing Strategy

### Test Database
- Uses in-memory SQLite (`sqlite+aiosqlite:///:memory:`)
- Fresh database per test function
- New session per request (prevents caching issues)

### Fixtures (`tests/conftest.py`)
- `db_engine` - Creates in-memory SQLite with all tables
- `client` - AsyncClient with dependency override for `get_db`
- `sample_*_data` - Test data fixtures

### Mocking Claude API
Since DEC-013, `AsyncAnthropic` is imported in two places (`src/agents/base.py` for the legacy single-shot fallback, `src/agents/llm_backend.py` for the agentic loop's `ClaudeBackend`) — tests exercising the full `prepare_visit()` flow patch both:
```python
with patch("src.agents.base.AsyncAnthropic") as mock_anthropic, \
     patch("src.agents.llm_backend.AsyncAnthropic") as mock_anthropic_backend:
    mock_client = AsyncMock()
    mock_client.messages.create = AsyncMock(return_value=mock_message)
    mock_anthropic.return_value = mock_client
    mock_anthropic_backend.return_value = mock_client
    # ... test code
```
Note this repo's `.env` sets `LLM_PROVIDER=ollama` by default — tests that need the Claude path force it with `monkeypatch.setattr(get_settings(), "llm_provider", "claude")` (see `tests/test_visit_prep.py`). Ollama's backend is mocked separately in `tests/test_llm_backend.py` by patching `httpx.AsyncClient.post`.

### Running Tests
```bash
pytest tests/ -v           # All tests
pytest tests/ -v -k visit  # Only visit prep tests
```

---

## Future Phases

### Next: Action Item Persistence (medium complexity, deferred — see DEC-012)
- Snooze / mark-completed state for nudges (new DB model + migration)
- Scheduled/repeated nudges via APScheduler
- 6-month lookahead for appointment scheduling from free-text timeframes

### Calendar Integration
- Google Calendar sync
- Apple Calendar support (macOS)
- Appointment reminders

### RAG for Health Documents
- ChromaDB vector store
- Search across all uploaded documents
- Context-aware health queries

### Medication Reminders
- Redis for task queue
- Scheduled reminder notifications
- Medication interaction checks

### Local Model Distillation
- Use ConversationLog data for fine-tuning
- Deploy smaller local model
- Reduce API costs

---

## Common Tasks

### Adding a New Entity

1. **Model** (`src/data/models.py`):
   ```python
   class NewEntity(Base):
       __tablename__ = "new_entities"
       id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
       # ... fields
   ```

2. **Migration**:
   ```bash
   alembic revision --autogenerate -m "Add new_entity table"
   alembic upgrade head
   ```

3. **Schemas** (`src/models/schemas.py`):
   ```python
   class NewEntityCreate(BaseModel): ...
   class NewEntityUpdate(BaseModel): ...
   class NewEntityResponse(BaseModel): ...
   ```

4. **Routes** (`src/api/new_entity.py`):
   - Create router with CRUD endpoints
   - Include in `src/main.py`

5. **Tests** (`tests/test_new_entity.py`):
   - Add fixtures to `conftest.py`
   - Write CRUD tests

### Adding a New Agent

1. Create `src/agents/new_agent.py`:
   ```python
   class NewAgent(BaseAgent):
       SYSTEM_PROMPT = "..."

       async def do_task(self, ...):
           messages = [{"role": "user", "content": ...}]
           response = await self._call_claude(messages, system=self.SYSTEM_PROMPT)
           return self._parse_json_response(response)
   ```

2. Add endpoint to call the agent
3. Write tests with mocked Claude API

---

## Frontend (React + Tailwind)

**Added:** 2026-02-05

### Tech Stack
- **Vite** - Build tool and dev server
- **React 19** - UI framework
- **TypeScript** - Type safety
- **Tailwind CSS 4** - Utility-first styling
- **React Router 7** - Client-side routing
- **TanStack Query** - Server state management

### File Structure

```
frontend/
├── src/
│   ├── api/
│   │   └── client.ts              # API client with typed methods
│   ├── components/
│   │   ├── Layout.tsx             # App shell with nav
│   │   ├── Button.tsx             # Reusable button variants
│   │   ├── Card.tsx               # Card components
│   │   ├── Input.tsx              # Form inputs
│   │   ├── Modal.tsx              # Modal dialog
│   │   ├── PostAvsActionPanel.tsx # Post-apply panel: extracted follow-ups/labs/referrals
│   │   └── ActionItemsSection.tsx # Overview tab: all proactive nudge types
│   ├── pages/
│   │   ├── ProfileList.tsx        # List/create profiles
│   │   ├── ProfileDetail.tsx      # Profile with tabs for health data
│   │   └── VisitPrep.tsx          # AI visit preparation
│   ├── types/
│   │   └── index.ts               # TypeScript interfaces
│   ├── App.tsx                    # Routes and providers
│   └── index.css             # Tailwind import
├── vite.config.ts            # Vite + Tailwind + proxy config
└── package.json
```

### Key Patterns

**API Client** (`src/api/client.ts`):
```typescript
const API_BASE = '/api';

async function request<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${endpoint}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!response.ok) throw new Error(await response.text());
  return response.json();
}

export const profiles = {
  list: () => request<HealthProfile[]>('/profiles/'),
  create: (data) => request<HealthProfile>('/profiles/', { method: 'POST', body: JSON.stringify(data) }),
  // ...
};
```

**TanStack Query** for data fetching:
```typescript
const { data: profiles, isLoading } = useQuery({
  queryKey: ['profiles'],
  queryFn: profiles.list,
});

const mutation = useMutation({
  mutationFn: profiles.create,
  onSuccess: () => queryClient.invalidateQueries({ queryKey: ['profiles'] }),
});
```

**Proxy Configuration** (`vite.config.ts`):
```typescript
server: {
  port: 3000,
  proxy: {
    '/api': { target: 'http://localhost:8000', changeOrigin: true },
  },
}
```

### Pages

1. **ProfileList** (`/`)
   - Grid of profile cards
   - Create profile modal
   - Click to navigate to detail

2. **ProfileDetail** (`/profiles/:profileId`)
   - Tabs: Overview, Conditions, Medications, Doctors, Appointments
   - Add modals for each entity type
   - "Prepare Visit" button on appointments

3. **VisitPrep** (`/profiles/:profileId/appointments/:appointmentId/prep`)
   - Shows appointment details
   - Generate button triggers the agentic visit-prep loop (Ollama by default, or Claude / custom, switchable at runtime from Settings)
   - Displays categorized questions
   - Regenerate option

### Running the Frontend

```bash
# Terminal 1: Backend
cd /path/to/HealthSteward
python -m uvicorn src.main:app --reload --port 8000

# Terminal 2: Frontend
cd frontend
pnpm dev
```

Then open http://localhost:3000

### Design Decisions

| Decision | Rationale |
|----------|-----------|
| **TanStack Query over useState** | Handles caching, loading states, refetching automatically |
| **Proxy in Vite config** | Avoids CORS issues during development |
| **Component-per-entity modals** | Keeps ProfileDetail readable despite size |
| **Tailwind utility classes** | Fast styling without separate CSS files |

---

*Last updated: 2026-07-05 (Phase 3: Proactive Action Items complete)*
