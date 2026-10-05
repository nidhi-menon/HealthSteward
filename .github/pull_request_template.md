## Summary

<!-- What does this PR change? Keep it terse and code-level. -->

## Test plan

<!-- Concrete, checkable steps — mirror how existing PRs do this, e.g.:
- [ ] `pytest` passes
- [ ] `npx tsc --noEmit` passes (frontend)
- [ ] Alembic migration applied cleanly against a copy of the dev DB
- [ ] Manual: <describe what you actually clicked/ran and what you saw> -->

## Checklist

- [ ] Added an Alembic migration if `src/data/models.py` changed, and checked it by hand
- [ ] If this sends data to an external LLM or adds a new agentic-loop tool, it goes through `Anonymizer` first (see CONTRIBUTING.md's privacy section)

Related: <!-- Closes #123 -->
