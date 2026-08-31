# Single-shot vs. Agentic Ablation — Numbers

Generated 2026-08-30. `review_study_outputs_singleshot.json` / `judge_review_study_results_singleshot.json`
(30 cases, `AGENT_TOOL_USE_ENABLED=false`, `raw_result.agentic_path == false` for all 30 — confirmed).
Updated same day with a 3-pass judge-noise check on the single-shot side
(`judge_noise_check_review_study_singleshot.py`, same method/judge/prompt version as the agentic noise check),
so both sides are now compared on a noise-controlled 3-pass basis.

## Data-integrity caveat

The currently-checked-in "agentic baseline" files (`judge_review_study_results.json`, `review_study_outputs.json`)
reflect the **pre-fix** guardrail-regex state (DEC-042 addendum, commit b23bb3b fixed it) — they are
byte-identical to `*_prefix_backup.json`, not to the postfix files. **Postfix is the true current-code baseline
and is the only agentic figure used in the 3-pass comparison below.** The pre-fix numbers (single-pass 6.01%,
3-pass mean 5.30%) are reported once, in their own row, explicitly labeled **pre-fix, different code snapshot,
not part of the current-code range** — they must never be folded into a postfix min-max range or averaged
alongside postfix/single-shot numbers anywhere in this document.

## Claim-level unsupported rate (aggregate, single judge pass — first pass of each 3-pass set)

| Run | Cases | Grounded | Unsupported | Scored (grounded+unsupported) | Unsupported rate |
|---|---|---|---|---|---|
| Single-shot (pass 1) | 30 | 235 | 21 | 256 | 8.20% |
| Agentic — pre-fix, historical only, not current code (checked-in `judge_review_study_results.json`) | 30 | 219 | 14 | 233 | 6.01% |
| Agentic — post-fix, current code (`judge_review_study_results_postfix.json`) | 30 | 223 | 9 | 232 | 3.88% |

## 3-pass noise-checked comparison (current code only)

Both sides now have a 3-pass judge-noise check, run with the identical method: same judge script pattern
(`eval/judge_noise_check_review_study.py` / `..._singleshot.py`), same judge model (`claude-opus-4-8`), same
judge prompt version (`v1-2026-08-29`), same claim-scoring/rubric logic (`eval/judge.py`'s
`score_factual_groundedness`), re-judging the SAME already-generated output file multiple times (no
regeneration). Single-shot pass 1 is the original single-pass run above; passes 2-3 are new
(`judge_noise_check_review_study_singleshot.json`).

| Run | Pass 1 | Pass 2 | Pass 3 | Range (min-max) | Mean |
|---|---|---|---|---|---|
| Single-shot | 8.20% (21/256) | 6.72% (17/253) | 7.29% (18/247) | **6.72%-8.20%** | **7.40%** |
| Agentic — post-fix (current code) | 4.07% | 5.26% | 4.11% | **4.07%-5.26%** | **4.48%** |

**The two 3-pass ranges do not overlap**: single-shot's minimum (6.72%) is above agentic post-fix's maximum
(5.26%). This is the strong form of the claim the data supports — not just "the mean was lower," but that
every observed single-shot pass rate exceeds every observed agentic post-fix pass rate on this 30-case suite,
under an identical judge instrument/methodology on both sides.

Do not use 4.48% vs. 8.20% (mean vs. single-pass) as the headline comparison — use the two 3-pass means
(7.40% vs. 4.48%) or, for the strongest defensible statement, the non-overlapping ranges above. Do not use
3.88% (a single-pass, pre-noise-check postfix number, now superseded by the 3-pass mean 4.48%) as the
comparator going forward.

## Historical: pre-fix agentic 3-pass (different code snapshot — NOT part of the current-code range)

| Run | Rates | Mean |
|---|---|---|
| Agentic — pre-fix (historical, different code snapshot, not current code) | 4.72%, 5.91%, 5.26% | 5.30% |

This row exists for provenance only. It reflects the pre-DEC-042-fix guardrail-regex state and must not be
blended into, averaged with, or presented as part of the current-code (postfix) 4.07%-5.26% range above.

## Accuracy rollup category counts (single-shot pass 1, 30 cases x up to 6 categories each)

| Category verdict | Count |
|---|---|
| Fully Supported | 110 |
| N/A | 33 |
| Partially Supported | 10 |
| Unsupported | 9 |

No separate scope-violation flag exists in `eval/judge.py`'s schema — `accuracy_rollup` per-category verdicts
and `groundedness_claims` verdicts are the only judge-side signals; there is no distinct "out of scope" category.

## Parse / format failures

| Run | Cases judged | Failed |
|---|---|---|
| Single-shot | 30 | 0 |
| Agentic (pre-fix and post-fix, per existing files) | 30 | 0 |

No `raw_result.used_fallback` field is present in the single-shot generator output; not applicable since
`AGENT_TOOL_USE_ENABLED=false` forces single-shot generation directly (no fallback path to trigger).

## Latency

| Run | n | Mean (s) | Median (s) | Min (s) | Max (s) |
|---|---|---|---|---|---|
| Single-shot | 30 | 12.86 | 12.16 | 8.62 | 17.65 |

**Agentic per-case latency at matching scale/model is not available.** `review_study_outputs.json` does not
carry `duration_s` (the generator that produced it doesn't forward it). The only file with both `duration_s`
and agentic tool use (`eval/results/231a2dc-20260829T053204Z.json`) is a **5-case Ollama/llama3.2 stability
check**, not a 30-case run on the paper's model — not comparable, so it is omitted rather than reported as
an agentic latency figure.

## Bottom line

On a 3-pass judge-noise-controlled comparison, current-code agentic (post-fix) has both a lower mean
unsupported-claim rate (4.48% vs. 7.40%) and a non-overlapping range (4.07%-5.26% vs. 6.72%-8.20%) than
single-shot generation on this 30-case suite — the strongest form of the claim ("agentic beats single-shot on
this suite, under an identical judge instrument") is now supported by the data, not just a single-pass point
estimate. The pre-fix agentic figures (single-pass 6.01%, 3-pass mean 5.30%) are historical only, reflect a
different code snapshot, and are excluded from this current-code range. Agentic per-case latency at matching
scale remains a data gap, not measured here.
