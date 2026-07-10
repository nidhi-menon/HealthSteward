## Summary

<!-- What does this PR do, and why? Reference the DEC-XXX or issue that scoped it if one exists. -->

## Test plan

<!-- Concrete, checkable steps — mirror how existing PRs do this, e.g.:
- [ ] `pytest` passes
- [ ] `npx tsc --noEmit` passes (frontend)
- [ ] Alembic migration applied cleanly against a copy of the dev DB
- [ ] Manual: <describe what you actually clicked/ran and what you saw> -->

## Checklist

- [ ] Added/updated a `docs/notes/DECISIONS.md` entry (DEC-XXX) if this makes or changes an architectural/technology choice
- [ ] Added/updated a `docs/notes/DEVELOPMENT_LOG.md` entry if this is more than a small fix
- [ ] Updated `docs/notes/DESIGN.md` only if this is a genuine architectural shift (new/removed subsystem, changed trust boundary) — not required for most PRs
- [ ] Added an Alembic migration if `src/data/models.py` changed, and checked it by hand
- [ ] If this sends data to an external LLM or adds a new agentic-loop tool, it goes through `Anonymizer` first (see CONTRIBUTING.md's privacy section)

Related: <!-- Closes #123, DEC-XXX -->
