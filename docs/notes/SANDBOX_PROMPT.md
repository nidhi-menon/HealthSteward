# HealthSteward Sandbox Experiments

Standalone prompts for prototyping features in a separate Claude session before integrating into the main app. Copy the relevant section into a new conversation.

**How to use:** Pick an experiment, copy everything in its "Prompt" block, paste into a fresh Claude chat.

---

## Table of Contents

1. [SB-001: AVS PDF Parser](#sb-001-avs-pdf-parser)
2. [SB-002: Agentic Visit Prep with Tool Use](#sb-002-agentic-visit-prep-with-tool-use)

---

## Shared Context

Paste this at the top of any sandbox prompt so Claude has project context:

```
PROJECT CONTEXT: I'm building HealthSteward, a privacy-first health management app.
- Backend: Python, FastAPI, async, SQLAlchemy + SQLite
- Frontend: React + TypeScript + Tailwind + Vite
- Vector DB: ChromaDB (available, not yet populated)
- LLM: Pluggable backend (local Ollama by default, or Claude API Sonnet, or any custom OpenAI-compatible provider — DEC-016) for visit prep's agentic tool-use loop; Ollama also handles PDF parsing and context-selection relevance scoring
- PII: All patient data is anonymized before reaching Claude or a custom provider (patient name omitted entirely, DOB → age, doctor names → "your cardiologist", etc.) — not needed for the local Ollama default, since nothing leaves the machine
- Machine: Apple M3, 8GB RAM
```

### Sample Anonymized Patient Data

Reuse across experiments as needed:

```python
patient_context = {
    "age": "45 years old",
    "blood_type": "A+",
    "allergies": "Penicillin, Sulfa drugs",
    "conditions": [
        {"name": "Type 2 Diabetes", "status": "active", "severity": "moderate", "notes": "Diagnosed 2019, HbA1c trending down"},
        {"name": "Hypertension", "status": "active", "severity": "mild", "notes": "Well-controlled on current medication"},
        {"name": "Hyperlipidemia", "status": "active", "severity": "mild", "notes": "Started statin therapy 6 months ago"},
    ],
    "medications": [
        {"name": "Metformin", "dosage": "1000mg", "frequency": "twice daily", "purpose": "Type 2 Diabetes"},
        {"name": "Lisinopril", "dosage": "10mg", "frequency": "once daily", "purpose": "Hypertension"},
        {"name": "Atorvastatin", "dosage": "20mg", "frequency": "once daily", "purpose": "Hyperlipidemia"},
        {"name": "Aspirin", "dosage": "81mg", "frequency": "once daily", "purpose": "Cardiovascular prevention"},
    ],
    "upcoming_appointment": {
        "doctor_title": "your cardiologist",
        "specialty": "Cardiology",
        "clinic": "HeartCare Associates",
        "date": "2026-02-28",
        "purpose": "6-month cardiovascular risk assessment follow-up",
    },
    "past_visits": [
        {
            "doctor": "your primary care physician",
            "date": "2026-01-15",
            "purpose": "Quarterly diabetes check",
            "notes": "HbA1c improved to 6.8% from 7.2%. Blood pressure 128/82. Cholesterol panel pending. Continue current medications. Discussed increasing exercise.",
        },
        {
            "doctor": "your cardiologist",
            "date": "2025-08-20",
            "purpose": "Initial cardiovascular risk assessment",
            "notes": "EKG normal. Started aspirin 81mg. Recommended cardiac stress test if symptoms develop. Follow up in 6 months.",
        },
    ],
}
```

---

## SB-001: AVS PDF Parser

**Decisions:** DEC-005 (After-Visit PDF Processing & Storage), DEC-007 (Action Items Extraction)
**Goal:** Local medical document parser that extracts structured data from after-visit summary PDFs — no PHI leaves the machine.
**Link:** [healthsteward-sandbox/avs-pdf-parser](https://github.com/nidhi-menon/healthsteward-sandbox/tree/main/avs-pdf-parser)
**Status:** Done — Integrated into HealthSteward (DEC-010, 2026-02-14)

### What it does

Parses after-visit summary PDFs and extracts structured items: instructions, medications, follow-ups, referrals, diagnoses, vitals, lab orders, and notes.

**Architecture — Section routing:**
- **Deterministic parsers** handle: patient info, medications, follow-ups, appointments, diagnoses (when ICD codes are present)
- **Focused single-turn LLM calls** (Qwen 2.5 7B via Ollama) handle: vitals, lab orders, referrals, notes

**Supported formats:**
- Sutter Health AVS
- Tebra clinical notes

**Privacy:** All processing runs locally — no PHI leaves the machine. Uses Ollama with Qwen 2.5 7B for the LLM portions.

### What to bring back

- Parser output schemas → align with HealthSteward's data models (Condition, Medication, Appointment, ActionItem)
- Integration path: upload PDF in UI → parse locally → present extracted items for user confirmation → update profile
- Determine whether to vendor the parser into HealthSteward or keep as a separate package/dependency

---

## SB-002: Agentic Visit Prep with Tool Use

**Decision:** DEC-009
**Goal:** Prototype the agentic loop pattern — Claude calling tools and asking clarifying questions in a multi-step loop before producing visit prep.
**Link:** Sandbox (new Claude session)
**Status:** Superseded — a bounded version shipped directly as DEC-013 (`src/agents/llm_backend.py`, `src/agents/tools.py`) without running this prototype first. Shipped scope is narrower than what's prompted below: two read-only tools (medication lookup, past-visit lookup), no RAG/ChromaDB, no drug-interaction API, no web search, and no user-facing clarifying-question pause (all descoped as follow-ups — see DEC-013). This prompt is kept for reference if those descoped pieces get picked up later.

### Prompt

```
PROJECT CONTEXT: I'm building HealthSteward, a privacy-first health management app.
- Backend: Python, FastAPI, async, SQLAlchemy + SQLite
- Frontend: React + TypeScript + Tailwind + Vite
- Vector DB: ChromaDB (available, not yet populated)
- LLM: Pluggable backend (local Ollama by default, or Claude API Sonnet, or any custom OpenAI-compatible provider — DEC-016) for visit prep's agentic tool-use loop; Ollama also handles PDF parsing and context-selection relevance scoring
- PII: All patient data is anonymized before reaching Claude or a custom provider (patient name omitted entirely, DOB → age, doctor names → "your cardiologist", etc.) — not needed for the local Ollama default, since nothing leaves the machine
- Machine: Apple M3, 8GB RAM

## Task

I need to prototype an **agentic visit prep agent** using Claude API's native tool use (function calling).

### What it does today (single-shot, no tools)

The visit prep agent takes a patient's anonymized health profile (conditions, medications, allergies, age) and an upcoming appointment, stuffs it all into one prompt, and gets back a list of questions to ask the doctor. One call, done.

### What I want it to do (agentic, multi-step)

Convert this into an **agentic loop** where the agent can:

1. **Use tools** to gather information before generating the final prep:
   - **RAG tool (local)**: Search a local vector database (ChromaDB) of medical guidelines, drug info, condition management guides. This runs locally — no API calls.
   - **Drug interaction lookup**: Check for interactions between the patient's current medications (could use a public API like OpenFDA, or a local database).
   - **Web search**: Look up recent medical information about the patient's conditions or medications (e.g., new treatment guidelines, recalls, relevant studies).
   - **Past visit context**: Retrieve relevant past visit notes (already implemented — this is the context selection system).

2. **Ask the user clarifying questions** before generating prep:
   - "Have you experienced any new symptoms since your last visit?"
   - "Are there specific concerns you want to address at this appointment?"
   - "Have you had trouble with any of your medications?"

3. **Reason through multiple steps** to produce a richer, more personalized visit prep.

### What I need from you

Build me a **standalone Python prototype** that demonstrates the agentic loop. Keep it simple and runnable — I want to understand the pattern before integrating it into the real app. Specifically:

1. **Define 3-4 tools** as Claude tool schemas:
   - `search_medical_knowledge` — simulates RAG lookup against local medical knowledge base
   - `check_drug_interactions` — checks interactions between medications
   - `search_web` — looks up current medical info online
   - `ask_patient` — asks the user a clarifying question

2. **Implement the agent loop**:
   - Send the initial health context + tools to Claude
   - When Claude calls a tool, execute it (mock/stub implementations are fine) and send the result back
   - When Claude asks the patient a question, get input from the user and send it back
   - Loop until Claude returns a final response (no more tool calls)

3. **Use this realistic mock data**:

patient_context = {
    "age": "45 years old",
    "blood_type": "A+",
    "allergies": "Penicillin, Sulfa drugs",
    "conditions": [
        {"name": "Type 2 Diabetes", "status": "active", "severity": "moderate", "notes": "Diagnosed 2019, HbA1c trending down"},
        {"name": "Hypertension", "status": "active", "severity": "mild", "notes": "Well-controlled on current medication"},
        {"name": "Hyperlipidemia", "status": "active", "severity": "mild", "notes": "Started statin therapy 6 months ago"},
    ],
    "medications": [
        {"name": "Metformin", "dosage": "1000mg", "frequency": "twice daily", "purpose": "Type 2 Diabetes"},
        {"name": "Lisinopril", "dosage": "10mg", "frequency": "once daily", "purpose": "Hypertension"},
        {"name": "Atorvastatin", "dosage": "20mg", "frequency": "once daily", "purpose": "Hyperlipidemia"},
        {"name": "Aspirin", "dosage": "81mg", "frequency": "once daily", "purpose": "Cardiovascular prevention"},
    ],
    "upcoming_appointment": {
        "doctor_title": "your cardiologist",
        "specialty": "Cardiology",
        "clinic": "HeartCare Associates",
        "date": "2026-02-28",
        "purpose": "6-month cardiovascular risk assessment follow-up",
    },
    "past_visits": [
        {
            "doctor": "your primary care physician",
            "date": "2026-01-15",
            "purpose": "Quarterly diabetes check",
            "notes": "HbA1c improved to 6.8% from 7.2%. Blood pressure 128/82. Cholesterol panel pending. Continue current medications. Discussed increasing exercise.",
        },
        {
            "doctor": "your cardiologist",
            "date": "2025-08-20",
            "purpose": "Initial cardiovascular risk assessment",
            "notes": "EKG normal. Started aspirin 81mg. Recommended cardiac stress test if symptoms develop. Follow up in 6 months.",
        },
    ],
}

4. **Show me the full conversation trace** — I want to see each step the agent takes, which tools it calls and why.

### Key constraints
- All data sent to Claude is already anonymized (no real names, DOBs, etc.)
- The agent should be conversational — it can ask the patient things
- Tool implementations can be mocked/stubbed for now, but design the schemas as if they're real
- Use `anthropic` Python SDK with `model="claude-sonnet-4-5-20250929"`
- Print each step of the agent loop so I can follow the reasoning
```

### What to bring back

After running this experiment, bring back:
- The tool schemas that worked well
- The agent loop pattern (how many turns it typically takes)
- Any issues with tool calling reliability
- Whether the clarifying questions felt natural or forced

---

## Template for New Experiments

```markdown
## SB-XXX: Title

**Decisions:** DEC-XXX (if applicable)
**Goal:** One-line description of what you're prototyping
**Link:** Separate repo / Inside HealthSteward / Sandbox (new Claude session)
**Status:** Not started / In progress / Done / Integrated

### Prompt

\```
(paste full prompt here)
\```

### What to bring back

- (what to evaluate / bring back to the main project)
```

---

*Last updated: 2026-02-13*
