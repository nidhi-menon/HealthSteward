"""Visit-prep evaluation harness (issue #29).

Deterministic-only v1 — see docs/tdd.html's Evaluation Plan tab for the full
plan this is scoped from, and docs/notes/DEVELOPMENT_LOG.md for the entry
documenting what v1 covers and what's deferred to v2 (LLM-as-judge).

This is a smoke test, not a quality measure: it catches gross regressions
(hallucination, scope violations, malformed output, missed/redundant tool
retrieval) at a fixed sampling temperature so runs are comparable to each
other. It does not measure whether the generated questions are actually
good, relevant, or non-redundant — that needs a judge model, deliberately
out of scope for v1.
"""
