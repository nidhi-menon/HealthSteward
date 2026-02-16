# HealthSteward

Privacy-first AI health coordination system that centralizes your fragmented health information across multiple doctors and chronic conditions. All data stays on your local machine.

## What It Does

- **Health profile management** — conditions (with ICD-10 codes), medications, doctors, appointments
- **AI visit preparation** — generates personalized questions for upcoming doctor visits using Claude API, with intelligent context selection from past visits
- **AVS PDF parsing** — upload after-visit summary PDFs, parse locally with Ollama, review extracted items, and update your profile
- **PII anonymization** — all data sent to external LLMs is anonymized (names, DOB, contact info removed)
- **Complete privacy** — health data stays local; PDF parsing uses only local Ollama (no PHI leaves your machine)

## Architecture

| Layer | Technology |
|-------|-----------|
| Backend | FastAPI + SQLAlchemy (async) + SQLite |
| Frontend | React 19 + TypeScript + Tailwind CSS + Vite |
| AI (agentic) | Claude API (Sonnet) for visit prep |
| AI (local) | Ollama (qwen2.5:7b) for PDF parsing |
| Database | SQLite via aiosqlite, migrations via Alembic |

## Quick Start

### Prerequisites

- Python 3.11+ (conda or venv)
- Node.js 18+ and pnpm
- [Ollama](https://ollama.ai) (for PDF parsing)
- [Anthropic API Key](https://console.anthropic.com/) (optional, for AI visit prep)

### Backend

```bash
# Activate your Python environment
conda activate healthsteward  # or your venv

# Install dependencies
pip install -r requirements.txt

# Run database migrations
python -m alembic upgrade head

# Start the API server
python -m uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend

```bash
cd frontend
pnpm install
pnpm dev  # starts on http://localhost:3000
```

### Ollama (for PDF parsing)

```bash
ollama serve
ollama pull qwen2.5:7b
```

### Environment

Create a `.env` file in the project root:

```env
# Required for AI visit prep (optional if only using PDF parsing)
ANTHROPIC_API_KEY=your_key_here

# Defaults (override as needed)
LLM_PROVIDER=claude
OLLAMA_BASE_URL=http://localhost:11434
AVS_PARSER_MODEL=qwen2.5:7b
DATABASE_URL=sqlite+aiosqlite:///data/healthsteward.db
```

## Project Structure

```
HealthSteward/
├── src/
│   ├── main.py              # FastAPI app entry point
│   ├── config.py            # Pydantic Settings configuration
│   ├── api/                 # API route handlers
│   │   ├── health_profile.py
│   │   ├── conditions.py
│   │   ├── medications.py
│   │   ├── doctors.py
│   │   ├── appointments.py
│   │   ├── documents.py     # PDF scan/parse/apply
│   │   └── visits.py        # AI visit prep
│   ├── data/
│   │   ├── models.py        # SQLAlchemy ORM models
│   │   └── database.py      # Async engine + session
│   ├── models/
│   │   └── schemas.py       # Pydantic request/response schemas
│   ├── parsers/             # AVS PDF parser module
│   │   ├── avs_parser.py    # SectionRouter (deterministic + LLM)
│   │   ├── text_extraction.py
│   │   ├── text_utils.py
│   │   └── agent/           # Ollama chat, prompts, section splitter
│   ├── agents/
│   │   ├── visit_prep.py    # AI visit preparation agent
│   │   └── ollama_client.py
│   └── utils/
│       ├── anonymization.py # PII removal for LLM calls
│       └── context_selection.py
├── frontend/                # React + TypeScript + Tailwind
│   └── src/
│       ├── pages/           # ProfileList, ProfileDetail, VisitPrep
│       ├── components/      # UI components + DocumentCard, ParsedItemsReview
│       ├── api/client.ts    # Typed API client
│       └── types/index.ts   # TypeScript interfaces
├── alembic/                 # Database migrations
├── data/                    # SQLite DB + AVS PDFs in data/avs/ (git-ignored)
├── docs/                    # Decision log, chat history, sandbox experiments
└── requirements.txt
```

## Database Models

| Model | Purpose |
|-------|---------|
| HealthProfile | User profile with personal info |
| Condition | Medical conditions with ICD-10 codes |
| Medication | Current and past medications |
| Doctor | Healthcare providers |
| Appointment | Scheduled visits with prep/visit notes |
| Document | Uploaded PDFs with parse status |
| Vitals | Weight, BMI, BP, HR, temp from parsed docs |
| LabOrder | Lab tests ordered during visits |
| Referral | Specialist referrals |
| FollowUp | Follow-up recommendations |
| VisitPrep | AI-generated visit preparation |
| ConversationLog | Anonymized LLM conversation history |

## Key Features in Detail

### PDF Parsing Flow

```
Drop PDF in data/avs/ → Open Documents tab → Parse locally (Ollama) → Review extracted items → Confirm → Update profile
```

The parser uses a **section-routing architecture**:
- **Deterministic parsers** for structured sections (patient info, medication changes, follow-ups, appointments, diagnoses with ICD codes)
- **Focused LLM calls** for unstructured sections (vitals, lab orders, notes, referrals)
- All LLM calls go to localhost Ollama only — a safety check blocks non-localhost URLs

### Visit Prep

Uses a 4-stage context selection pipeline:
1. Rules-based filtering (same doctor, PCP visits, related specialties)
2. Local LLM relevance scoring (Ollama, if >5 past visits)
3. Token budget management
4. Anonymize and send to Claude for question generation

## Documentation

- `docs/DECISIONS.md` — architectural decision log (DEC-001 through DEC-010)
- `docs/CHAT_HISTORY.md` — development conversation history
- `docs/SANDBOX_PROMPT.md` — sandbox experiment prompts

## Data Privacy

All health data stays local. The `.gitignore` protects:
- `data/` (database + AVS PDFs)
- `.env` files
- Log files

PDF parsing uses only local Ollama — no PHI is sent to external services. Visit prep anonymizes all PII before sending to Claude API.

## License

Private project — All rights reserved
