# HealthSteward — Prompt Changelog

Started 2026-07-19. Every LLM prompt in the codebase gets a version tag next to its definition (a `_VERSION` constant, or a `PROMPT_VERSIONS` dict for a module with several). Whenever a prompt's *content* changes — not just surrounding code — bump the version and add an entry here: what changed, why, and (when applicable) what eval evidence motivated or validated the change. This is separate from `docs/notes/DECISIONS.md` (architectural choices) and `docs/notes/DEVELOPMENT_LOG.md` (narrative build history) — this file is specifically the prompt-by-prompt version history, so "what did this prompt say at commit X" and "why did it change" are answerable without archaeology through git blame.

Convention:
- Version format: `v<N>-<date-of-change>` (e.g. `v2-2026-07-19`) for prompts with real content churn expected (visit-prep system prompts); a plain `v<N>` is fine for prompts expected to change rarely.
- A version bump is required for any wording change that could plausibly affect model behavior — not for comment/docstring-only edits to the surrounding code.
- Prompts logged to `ConversationLog` (currently: `visit_prep.py`'s two system prompts) carry their version into `extra_data["prompt_version"]` on every real run, so a logged conversation is traceable to the exact prompt that produced it. Prompts not logged anywhere yet (Stage 2 relevance scoring, the AVS parser's five section prompts) are versioned here for traceability but don't yet have a per-run log field — noted as a gap below, not silently skipped.

---

## `src/agents/visit_prep.py` — `SYSTEM_PROMPT_TEMPLATE` (specialty-aware) and `SYSTEM_PROMPT_GENERIC` (fallback)

### v3-2026-07-19
**Context:** v2's remaining open item was `cold_start` (one condition, nothing else) failing the fixed 8-question floor — investigating it surfaced a real tension: the prompt's own anti-hallucination rule ("don't ask about data that isn't provided") was in direct conflict with the hard "8-15 questions" requirement for any case with genuinely little real data. A model following the grounding rule honestly for a sparse case *cannot* also hit 8 well-grounded questions; the only way to satisfy both was to invent content, which is the exact failure mode the grounding rule exists to prevent.

**Change:**
- Prompt: added an explicit per-category grounding requirement — a category ("Condition Management", "Medication Review", "Lab Results & Monitoring", "Follow-up Planning") must have real listed patient data behind it to appear at all; "Lifestyle & Prevention" may stay data-light but still can't assert unprovided facts. Also added an explicit instruction to omit a category key entirely rather than emit it with an empty list, and — after the first re-run below surfaced a regression — a follow-up clarification that omitting empty categories does not lower the 8-15 count requirement, and that the model should go deeper within its *non-empty* categories (more angles on the same condition/medication) rather than settling for a shorter list.
- Scorer (`eval/scorers.py`): added `expected_min_questions(case)`, scaling the format-validity floor to `min(8, max(3, 2 × known_entity_count))` instead of a flat 8 for every case. `score_format` and `run.py`'s call site were updated to pass this per-case floor through instead of hardcoding 8.

**Reasoning:** Rather than relaxing the grounding rule (which would reopen the hallucination risk v2 fixed) or leaving `cold_start` permanently failing a bar it structurally can't meet, scaled the *bar* to the amount of real data available, and made the prompt's category-omission behavior explicit and symmetric with that scaling — both changes needed to land together since the scorer change alone would just be scoring the old prompt's already-inconsistent empty-category behavior more leniently.

**Eval evidence:** Baseline (v2) run: `eval/results/192bdf0-20260719T064925Z.json`.

First re-run after the initial change: `eval/results/e188fce-20260719T074942Z.json`.
- `cold_start`: format valid False→True (3 questions against a scaled floor of 3) — the model now works within its actual data rather than being pushed toward padding.
- `cross_specialty_scope`: still format-invalid (6 questions vs. floor 8) but grounded_rate improved 0.0→0.17.
- `groundedness_labs_vitals`: grounded_rate improved 0.5→0.8, stayed format-valid.
- `tool_call_necessity_dosing`: grounded_rate improved 0.56→0.67, stayed format-valid.
- **Regression found:** `retrieval_redundancy` flipped format valid True→False (3 questions against a floor of 4) — the model dropped from 5 categories to 2 (only "Condition Management" and "Lab Results & Monitoring" survived), undershooting even the scaled floor despite having real medication data available. The omit-empty-category instruction was being over-applied relative to the still-present 8-15 instruction, at least for llama3.2.

Second re-run after the "go deeper within non-empty categories" clarification above: `eval/results/e188fce-20260719T162421Z.json`.
- `retrieval_redundancy`: format valid False→True (9 questions, floor 4) — regression fixed.
- `tool_call_necessity_dosing`: format stayed valid (8 questions), grounded_rate dipped slightly 0.67→0.625.
- `groundedness_labs_vitals`: stayed format-valid but grounded_rate dropped 0.8→0.6; `retrieval_redundancy` grounded_rate also dropped 0.67→0.33. In both cases the additional questions used to hit the count are generic ones the prompt's own rules explicitly permit without a cited entity (e.g. general lifestyle tips, "when should we schedule a follow-up") — not new hallucinations, but the `score_groundedness` entity-match scorer doesn't currently know about that prompt-level exception and flags them as ungrounded anyway.
- `cross_specialty_scope`: still format-invalid (6 questions vs. floor 8) — grounded_rate improved further, 0.17→0.33. Not addressed by this version; appears to be a case where the specialty-scoping rule itself limits how many genuinely relevant questions exist, similar to `cold_start`'s data-sparsity limit. Not yet investigated further — tracked as [issue #75](https://github.com/nidhi-menon/HealthSteward/issues/75).

**Scorer follow-up (`eval/scorers.py`, not a prompt change — no `_VERSION` bump):** the grounded_rate dip above traced to `score_groundedness` not knowing about the prompt's own explicit "Lifestyle & Prevention" exception (that category is allowed to stay data-light — see the per-category grounding rule above). Fixed by excluding "Lifestyle & Prevention" from both the numerator and denominator of the entity-match check. Third re-run confirms this was purely a scorer gap, not model behavior: `eval/results/e188fce-20260719T163048Z.json` vs. the second re-run — `groundedness_labs_vitals` 0.6→0.625, `cold_start` 0.33→1.0 (its only two "ungrounded" questions were both Lifestyle ones), `tool_call_necessity_dosing` 0.625→0.667, `retrieval_redundancy` 0.33→0.43. Every case that changed improved; none regressed. "Follow-up Planning" was deliberately left as-is — the prompt only exempts *generic* follow-up phrasing there, not the whole category, and that's a fuzzier distinction than a clean per-category exclusion can capture safely.

Remaining ungrounded questions after the Lifestyle fix reference an implicit prior state or trend rather than a specific entity string (e.g. "since my last visit," "based on these lab results," "how is my TSH trending") — `score_groundedness`'s entity-string-match design can't tell these are conceptually grounded. This is the v1 "smoke test" scorer's known limit, not a new bug; `docs/tdd.html`'s eval plan already assigns deeper claim verification to a v2 NLI-judge pass. Tracked as [issue #76](https://github.com/nidhi-menon/HealthSteward/issues/76) rather than patched here.

### v2-2026-07-19
**Context:** The #29 eval harness's first real run against local Ollama (`llama3.2`) found every one of 5 test cases failing the prompt's own stated 8-15 question requirement (3-8 questions actually returned), plus at least one clear hallucination (`cold_start` — a case with zero vitals data — generated a question asking about blood pressure readings that were never provided).

**Change:**
- Moved the question-count requirement from a single soft trailing sentence into the task description itself (primacy), and restated it again as an explicit pre-response self-check (recency) — small local models are known to under-attend to instructions buried mid-prompt or stated only once (DEC-009).
- Added an explicit prohibition: don't ask about vitals/labs/conditions/medications that aren't in the provided data — the previous prompt only said what *to* reference, never what *not* to invent.
- `SYSTEM_PROMPT_GENERIC` picked up the same two changes, dropping its previously-absent grounding rule entirely (it had none before this version).

**Reasoning:** Both symptoms (short output, hallucination) plausibly share one root cause — the model under-attending to prompt instructions generally — so bundled into one change rather than two separate prompt edits, to be evaluated together via one harness re-run.

**Eval evidence:** Baseline (v1, pre-this-change) run: `eval/results/192bdf0-20260719T063412Z.json` — 0/5 cases passed format validity, `cold_start` showed the blood-pressure hallucination. Re-run after this change: `eval/results/192bdf0-20260719T064925Z.json` — 3/5 cases now pass format validity (`groundedness_labs_vitals`, `tool_call_necessity_dosing`, `retrieval_redundancy`, all False→True), grounded_rate improved in every case that changed and regressed in none. `cross_specialty_scope` and `cold_start` still fail the count — `cold_start` in particular has very little real patient data to draw from (one condition, no medications/labs/past-visits), so hitting 8+ *grounded* questions may be a harder ceiling for that case specifically rather than a remaining prompt-following failure of the same kind. Not yet investigated further — worth a look before declaring v2 fully sufficient.

### v1 (undated — prior to this changelog's existence)
Original prompt, no explicit anti-hallucination rule, count requirement stated once at the end. Not separately documented since it predates this tracking convention; preserved here only as the implicit baseline v2 supersedes.

---

## `src/utils/context_selection.py` — Stage 2 relevance-scoring prompt (`STAGE2_SCORING_PROMPT_VERSION`)

### v1 (baseline, 2026-07-19)
Built inline in `ContextSelector.stage2_llm_scoring`, not yet extracted to a named template constant. Rates a past visit's relevance to the target appointment 1-10. No content change made — version tag added for traceability as part of establishing this convention project-wide. **Gap:** not yet threaded into any per-run log — Stage 2 scoring results aren't currently persisted anywhere queryable after the fact, so a version bump here isn't yet traceable to a specific historical scoring run the way `visit_prep.py`'s prompts are via `ConversationLog`.

---

## `src/parsers/agent/prompts.py` — AVS section-extraction prompts (`PROMPT_VERSIONS` dict)

### v1 (baseline, 2026-07-19)
`VITALS_SYSTEM`, `DIAGNOSES_SYSTEM`, `LAB_ORDERS_SYSTEM`, `NOTES_SYSTEM`, `REFERRALS_SYSTEM` — no content changes made, version tags added for traceability as part of establishing this convention project-wide. **Gap:** same as Stage 2 scoring above — `Document.raw_parse_result` stores the parse *output* but not which prompt version produced it. Worth closing if/when the AVS parser's prompts start changing with any frequency; not urgent while they're stable.
