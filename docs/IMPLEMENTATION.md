# HealthSteward Implementation Journal

This document tracks implementation details, architectural decisions, and how components work together. Use this as a reference when working on the project or to understand how things were built.

---

## Table of Contents
- [Project Overview](#project-overview)
- [Phase 1: Health Profile + Visit Prep](#phase-1-health-profile--visit-prep)
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
- **AI:** Anthropic Claude API
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
│ VisitPrepAgent._build_context() │
│ - Formats health data           │
│ - Adds additional concerns      │
└─────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────┐
│ BaseAgent._call_claude()        │
│ - Sends to Claude API           │
│ - Logs conversation to DB       │
└─────────────────────────────────┘
     │
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
                       └──── (*) Appointment ──── (1) VisitPrep

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
- `_build_context()` to format patient data as markdown
- Fallback questions if Claude API fails

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
| POST | `/api/visits/{appt_id}/prepare` | Generate visit prep (calls Claude) |
| GET | `/api/visits/{appt_id}/prep` | Get existing visit prep |

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
```python
with patch("src.agents.base.AsyncAnthropic") as mock_anthropic:
    mock_client = AsyncMock()
    mock_client.messages.create = AsyncMock(return_value=mock_message)
    mock_anthropic.return_value = mock_client
    # ... test code
```

### Running Tests
```bash
pytest tests/ -v           # All tests
pytest tests/ -v -k visit  # Only visit prep tests
```

---

## Future Phases

### Phase 2: Calendar Integration
- Google Calendar sync
- Apple Calendar support (macOS)
- Appointment reminders

### Phase 3: After-Visit PDF Processing
- Upload PDFs from patient portals
- Extract text (pdfplumber / Claude Vision / OCR)
- LLM parses: new conditions, medication changes, vitals, lab results
- User reviews & confirms before adding to profile
- Encrypted PDF storage (local or cloud)
- See DEC-005 in DECISIONS.md for full details

### Phase 4: RAG for Health Documents
- ChromaDB vector store
- Search across all uploaded documents
- Context-aware health queries

### Phase 5: Medication Reminders
- Redis for task queue
- Scheduled reminder notifications
- Medication interaction checks

### Phase 6: Local Model Distillation
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
│   │   └── client.ts         # API client with typed methods
│   ├── components/
│   │   ├── Layout.tsx        # App shell with nav
│   │   ├── Button.tsx        # Reusable button variants
│   │   ├── Card.tsx          # Card components
│   │   ├── Input.tsx         # Form inputs
│   │   └── Modal.tsx         # Modal dialog
│   ├── pages/
│   │   ├── ProfileList.tsx   # List/create profiles
│   │   ├── ProfileDetail.tsx # Profile with tabs for health data
│   │   └── VisitPrep.tsx     # AI visit preparation
│   ├── types/
│   │   └── index.ts          # TypeScript interfaces
│   ├── App.tsx               # Routes and providers
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
   - Generate button calls Claude API
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

*Last updated: 2026-02-05 (Phase 1 + Frontend complete)*
