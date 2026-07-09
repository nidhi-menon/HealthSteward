# Contributing to HealthSteward

HealthSteward is early-stage and the codebase evolves through a handful of documented conventions. This doc explains them so a PR fits in without a round of back-and-forth.

## Before you start

- Check [open issues](https://github.com/nidhi-menon/HealthSteward/issues) first — most non-trivial work is scoped there before it's built, including open questions and explicit non-goals.
- For anything architectural (new dependency, new external service, a schema change, a new subsystem), open an issue or start a [Discussion](https://github.com/nidhi-menon/HealthSteward/discussions) before writing code. See "Decision log" below for why.

## Decision log and development log

Two docs record *why* the codebase looks the way it does — read them before assuming something is an oversight:

- **`docs/notes/DECISIONS.md`** — architectural decisions (framework choices, scope cuts, privacy trade-offs), one entry per `DEC-XXX`. If your PR makes or changes an architectural call, add an entry here in the same format (Date / Topic / Context / Options Considered / Decision / Reasoning / Status).
- **`docs/notes/DEVELOPMENT_LOG.md`** — narrative history of what was built and why, one entry per significant unit of work. Add an entry for anything beyond a small fix.
- **`docs/notes/DESIGN.md`** — a point-in-time architecture snapshot, not a living doc. Most DEC entries don't need it touched. Update it only if your DEC represents a genuine architectural shift: adds/removes a major subsystem, changes a trust boundary or core pattern, or deprecates something the doc currently describes. If you do update it, refresh the date/commit-stamp at the top.

Both DECISIONS.md and DEVELOPMENT_LOG.md exist so that "why is this deferred" or "why isn't X built yet" has a documented answer instead of living only in someone's memory. Skipping them isn't a blocker for a tiny PR, but is expected for anything that changes behavior or defers/descopes something.

## Privacy is a hard constraint, not a preference

This is the one rule that isn't negotiable in review:

- **PDF/document parsing must stay on local Ollama.** `src/parsers/agent/ollama_chat.py` enforces this with a localhost-only safety check — don't route parsing through an external API, even experimentally.
- **Any data sent to an external LLM (Claude API) must go through the anonymization layer first** (`src/utils/anonymization.py`, see DEC-006). If you add a new code path that sends patient data to an external service, it needs to go through `Anonymizer` or have a documented reason it doesn't.
- **Tool results fed back into the agentic loop must be anonymized too** — not just the initial context (see DEC-013). If you add a new tool to `src/agents/tools.py`, its result needs to pass through the same anonymization the existing tools use.

## Setup

See the [README Quick Start](README.md#quick-start) for backend/frontend setup and environment variables.

## Testing

- **Backend:** `pytest` — a new endpoint, tool, or agent behavior needs a test in `tests/`. Look at `tests/test_visit_prep.py` or `tests/test_agent_tools.py` for the existing patterns (fixtures in `conftest.py`, mocked LLM calls).
- **Frontend:** there is currently no test suite (tracked as a known gap — see open issues). If you're adding frontend logic non-trivial enough to want tests, flag it in your PR description rather than skipping silently.

## Database changes

Any change to `src/data/models.py` needs an Alembic migration:

```bash
python -m alembic revision --autogenerate -m "describe the change"
python -m alembic upgrade head
```

Check the generated migration by hand — autogenerate doesn't always get column type changes or renames right.

## Commit and PR style

- Keep commits scoped to one logical change; don't bundle an unrelated doc update into a feature PR (or vice versa).
- PR description should say *why*, not just *what* — the diff already shows what changed.
- If your change touches something DEC-XXX already covers, reference it in the PR description.

## Code style

- Python: type-annotated, async throughout the backend (SQLAlchemy async sessions, async route handlers). Follow the existing patterns in `src/api/*.py` for new endpoints — profile-nested routes (`/api/profiles/{id}/...`), Pydantic schemas in `src/models/schemas.py`.
- TypeScript: functional components, TanStack Query for server state, Tailwind for styling — follow existing components in `frontend/src/components/` rather than introducing a new state-management or styling approach.

## Questions

Open a [Discussion](https://github.com/nidhi-menon/HealthSteward/discussions) rather than an issue if you're unsure whether something is a bug, a missing feature, or intentional — issues are for scoped, actionable work.
