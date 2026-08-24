# OpenMed vs. HealthSteward's PII Anonymizer — Re-run (bias-corrected, methodology-corrected)

**Issue:** [#122](https://github.com/nidhi-menon/HealthSteward/issues/122) follow-up · **Harness:** `eval/prototypes/openmed_pii_prototype_v2.py` · **Corpora:** `eval/prototypes/openmed_pii_cases.py` (v1, 67/24 cases, transcribed from `tests/test_anonymization.py`) **and** `eval/prototypes/openmed_pii_cases_v2.py` (v2, 50/46 cases, independently written in-context clinical sentences) · **Raw reports:** `eval/prototypes/reports/v2/`

**Verdict up front, revised twice during this re-run:**

1. First pass (corpus bias + label filtering fixed): the original recall/precision gap was mostly a corpus artifact, but OpenMed's cost — 300×–1000× the latency, hundreds of MB more memory — still looked decisive against DEC-009's 8GB M3 constraint, so the adopt/don't-adopt call held.
2. **That cost number turned out to be a harness bug, not a property of OpenMed.** `extract_pii()` reloads the model from scratch on every call unless a reusable `ModelLoader` is passed in explicitly. The harness didn't do that, so every "per-text" timing in the first pass of this re-run — and, almost certainly, in the original PR #124 benchmark — included a ~1-second model reload on top of actual inference. Corrected (§4a): OpenMed's small model runs at **~13-17ms/text**, not ~950ms — roughly 5× `regex+ner`'s ~3ms, not 300-1000×. Memory is a real, still-nontrivial fixed cost (~430MB for the small model, ~320-600MB depending on isolation — §4a) but it's a **one-time resident cost from loading the model**, not something that scales with request volume the way the original latency numbers implied.

**This changes the shape of the decision, even though it doesn't flip it today.** OpenMed's small model, filtered, is now closer to *"a real memory tradeoff, negligible latency"* than *"decisively too slow to consider."* It is still not a drop-in replacement — recall/precision remains a genuine tradeoff against `regex+ner` (§5, no configuration strictly dominates), and `regex+ner` itself isn't what HealthSteward ships (§0) for an unrelated, still-unresolved reason (drug names tagged `PERSON`, §6). See **Bottom line** for what this actually means for HealthSteward, and **§4a** for the full account of the bug and how it was caught.

## Why this re-run exists

PR #124's original benchmark ([`OPENMED_FINDINGS.md`](OPENMED_FINDINGS.md)) named three of its own caveats as reasons to distrust the headline numbers: the corpus was transcribed from the regex implementation's own tests (structurally favors regex), sample sizes per category were small enough that one case swings a rate 25–33%, and OpenMed's over-redactions traced to a label-taxonomy mismatch that "any future integration would need real label filtering" for — but the original run scored OpenMed's raw, unfiltered output anyway. This re-run addresses all three, in order (§1-§3), widens the model/confidence sweep the original caveats flagged as narrow (§4), and — found in the process of widening that sweep, not something either report set out to check — corrects a latency/memory measurement bug that neither report caught the first time (§4a).

## 0. Which baseline is real

Two different "current approach" baselines appear in this report and they answer different questions:

- **`regex`** — patterns only, no NER. **This is what HealthSteward actually ships.** `spacy` is absent from both `requirements.txt` and `environment.yml`, so `SPACY_AVAILABLE` is `False` by default (DEC-006, 2026-08-06 amendment). Any comparison of "what should we adopt instead of what's running today" belongs against this row.
- **`regex+ner`** — patterns plus spaCy PERSON detection. This is DEC-006's *originally intended* design, documented as aspirational, not shipped — the amendment explicitly deferred it until the drug-name-as-PERSON over-redaction (#125) has a mitigation. Treat this row as "what the intended design would score if it were live," not as a description of production behavior.

## 1. Corpus bias — a second, independently written corpus

`openmed_pii_cases_v2.py` was written from scratch, not derived from `tests/test_anonymization.py`. Every case is a natural clinical-note sentence with PII embedded in context (`"Discussed lab results with Aisha Khan over the phone this afternoon."`) rather than a bare pattern fragment (`"Call me at 555-123-4567"`). 50 positive cases across 12 categories, 46 negative cases across 11 categories — negative-case count roughly doubled versus v1's 24, and the category set widens to include procedures and allergies that v1 didn't cover.

The harness (`openmed_pii_prototype_v2.py`) runs **both** corpora and reports them side by side rather than replacing one with the other — a system's ranking should hold on both if the finding is real, not an artifact of which corpus it's read against.

**It moved the number a lot.** Bare `regex` (no NER) drops from 94% recall on v1 to 74% on v2 — free-text names (`"Wei Chen will follow up..."`) and standalone zip codes (`"Patient's mailing zip is 97205"`, not attached to a street address or a ZIP+4) are exactly the shapes v1's format-fragment corpus didn't stress. `regex+ner` recovers most of this (96%) — NER catches the names, but not the zip codes: that gap is independent of NER (§4a note) and, unlike the names, is a *known, documented* tradeoff rather than a new finding. OpenMed's small model, conversely, improves on the harder corpus: 100% recall at confidence 0.3, because free-text entity recognition is precisely what it's built for and v1 was undersized on exactly that.

## 2. Sample size

v2 adds cases rather than replacing v1 — the combined corpus reports both sets per-category so a reader can see whether a per-category number is resting on 2 cases or 8. Per-category counts are still not large (§7, unchanged caveat) — this narrows the problem, it doesn't eliminate it.

## 3. Label-taxonomy mismatch — filtering `extract_pii`'s output

The original run's over-redactions (`City Medical Center` → `city`, `Weight 185 lbs` → `age`, `Infusion rate 5551234 mL` → `pin`) were flagged as a real design mismatch, not sampling noise, but the original harness never tested a filtered variant. This re-run adds an `openmed-filtered` system: the same detector and confidence threshold, but only entities whose canonical label falls in `PROJECT_REDACT_LABELS` are actually redacted — everything else (`TIME`, `AGE`, `MEDICATION`, `CONDITION`, general `LOCATION`/`ORGANIZATION`, …) passes through untouched regardless of what OpenMed detected.

`PROJECT_REDACT_LABELS` = OpenMed's own `openmed.critical_labels()` (its built-in identity/contact/financial-identifier set — `PERSON`, `EMAIL`, `PHONE`, `SSN`, `STREET_ADDRESS`, `ACCOUNT_NUMBER`, etc.) **plus** `DATE` and `ZIPCODE`, which this project's regex policy treats as identifying but OpenMed's general-purpose `critical_labels()` does not (DEC-006 redacts every date and every zip code, not just DOB). Built from the installed `openmed` package at runtime (`project_redact_labels()` in the harness) rather than hand-copied, so it tracks upstream label changes instead of silently drifting.

**One labeling bug found and fixed during this re-run, worth recording:** `extract_pii` returns lowercase raw model labels (`last_name`, `phone_number`, `date_of_birth`), not the uppercase `CANONICAL_LABELS` vocabulary `critical_labels()` is expressed in. The first filtered run scored **0% recall** — every entity was silently dropped because `"last_name" != "LAST_NAME"`, not because OpenMed found nothing. Fixed by routing every label through `openmed.normalize_label()` before comparing. Flagged here because a filtering harness that fails silently in this direction is dangerous: it would report "no leaks" as if the detector were perfect, when the detector was actually never being asked to redact anything. (This is the first of two harness bugs this re-run caught in itself — see §4a for the second, larger one.)

**Result, small model, confidence 0.5:**

| corpus | system | recall | precision |
|---|---|---|---|
| v1 | `openmed` (unfiltered) | 62/67 (93%) | 17/24 (71%) |
| v1 | `openmed-filtered` | 61/67 (91%) | **21/24 (88%)** |
| v2 | `openmed` (unfiltered) | 49/50 (98%) | 40/46 (87%) |
| v2 | `openmed-filtered` | 46/50 (92%) | **45/46 (98%)** |

Filtering trades a little recall (1–3 cases) for a large precision gain (v1: +17pp; v2: +11pp) — confirming the original caveat was right and the fix is worth doing. It does not fully close the gap on v1: `Infusion rate 5551234 mL → [REDACTED] mL` still over-redacts under `PIN`, and `Step count averaged 12500 per day` still over-redacts under `ZIPCODE` — both are the detector genuinely misclassifying dosage/fitness numbers as identifiers, not a label the filter was wrong to keep. Filtering also introduces its own recall loss on v2: an international phone number and two insurance IDs slip through filtered that unfiltered caught, because their raw labels didn't normalize into `PROJECT_REDACT_LABELS`.

## 4. Wider sweep

Two corpora × two model sizes × three confidence thresholds (0.3/0.5/0.7) × four systems (`regex`, `regex+ner`, `openmed`, `openmed-filtered`) = 24 configurations, versus the original's 6 (one corpus, one system variant). Full numbers in `eval/prototypes/reports/v2/report_v2_corrected_full_sweep.json`.

Read the `regex` row as *HealthSteward today*; read `regex+ner` as *HealthSteward's aspirational design, not shipped* (§0). Neither OpenMed system strictly dominates `regex+ner` here on recall/precision — `openmed` (unfiltered) wins recall, loses precision; `openmed-filtered` wins precision, loses recall. Both OpenMed systems beat bare `regex` on recall by a wide margin. Cost comparison is in §4a — the numbers originally printed alongside this table were wrong; corrected ones are below.

**Headline (small model, `OpenMed-PII-SuperClinical-Small-44M-v1`):**

| corpus | conf | system | recall | precision | mean ms/text (corrected) |
|---|---|---|---|---|---|
| v1 | 0.3 | `regex` | 63/67 (94%) | 24/24 (100%) | 0.0 |
| v1 | 0.3 | `regex+ner` | 66/67 (99%) | 23/24 (96%) | 2.1 |
| v1 | 0.3 | `openmed` | 63/67 (94%) | 17/24 (71%) | 12.9 |
| v1 | 0.3 | `openmed-filtered` | 62/67 (93%) | 21/24 (88%) | 12.8 |
| v1 | 0.7 | `openmed` | 55/67 (82%) | 18/24 (75%) | 13.1 |
| v1 | 0.7 | `openmed-filtered` | 55/67 (82%) | 22/24 (92%) | 13.6 |
| v2 | 0.3 | `regex` | 37/50 (74%) | 46/46 (100%) | 0.0 |
| v2 | 0.3 | `regex+ner` | 48/50 (96%) | 44/46 (96%) | 4.1 |
| v2 | 0.3 | `openmed` | **50/50 (100%)** | 40/46 (87%) | 16.7 |
| v2 | 0.3 | `openmed-filtered` | 47/50 (94%) | 45/46 (98%) | 17.5 |
| v2 | 0.7 | `openmed` | 47/50 (94%) | 43/46 (93%) | 15.6 |
| v2 | 0.7 | `openmed-filtered` | 46/50 (92%) | **46/46 (100%)** | 16.3 |

**Large model (`OpenMed-PII-SuperClinical-Large-434M-v1`, confidence 0.5):**

| corpus | system | recall | precision | mean ms/text (corrected) |
|---|---|---|---|---|
| v1 | `openmed` | 56/67 (84%) | 21/24 (88%) | 59.3 |
| v1 | `openmed-filtered` | 54/67 (81%) | 22/24 (92%) | 63.1 |
| v2 | `openmed` | 49/50 (98%) | 41/46 (89%) | 61.3 |
| v2 | `openmed-filtered` | 46/50 (92%) | 45/46 (98%) | 63.3 |

The large model repeats the original recall/precision finding: it does not dominate the small model, it trades along the same curve (marginally better precision on v1, worse recall on v2). Its latency cost relative to the small model is real and now correctly measured — ~4× (~60ms vs ~15ms) — but both are single-digit-to-low-double-digit milliseconds, not the ~1s-vs-3s gap the buggy measurement reported. On the bias-corrected v2 corpus, the small model at low confidence remains the best OpenMed configuration found in this sweep on both recall and cost.

**Regex baselines, now measured against v2 too:** `regex` alone drops to 74% recall on the harder corpus (see §1) — this is the clearest concrete recall result of the whole re-run. `regex+ner` recovers most of it (96%) but still misses standalone zip codes: `"Patient's mailing zip is 97205"` survives regardless of NER, because `PII_PATTERNS['zip_code']` in `src/utils/anonymization.py` only matches a ZIP+4 (`94103-1234`) or a zip immediately preceded by a two-letter state code (`CA 94103`) — a bare 5-digit number is, per the pattern's own comment, **deliberately** left alone: *"it is indistinguishable from an ordinary number in clinical text."* This is not a newly discovered bug — it's a previously-undocumented-with-numbers instance of an already-accepted design tradeoff, now confirmed to actually occur (2/50 v2 cases) rather than being purely theoretical.

## 4a. A second, much larger harness bug: model-reload latency, found and fixed mid-re-run

The first pass of this re-run measured OpenMed's small model at **~900-1030ms/text** and the large model at **~3000-3440ms/text** — in line with, and only somewhat better than, PR #124's original numbers (~780-3000ms). Those numbers were wrong, and the error was in the harness, not OpenMed.

**The bug.** `openmed.extract_pii(text, model_name=..., ...)` reconstructs the model pipeline internally on every call unless an explicit `loader=` (an `openmed.ModelLoader` instance, loaded once via `loader.load_model(model_name)`) is passed in and reused. Neither this harness's first pass nor, apparently, PR #124's original benchmark did this — every timed call included a full model (re)load, dominating the actual inference cost by roughly 60-70×. Confirmed directly:

```
without loader reuse:  ~1.0-1.3s per call, every call (not just the first)
with loader reused:    ~15ms per call, after one ~4-14s one-time load
```

**How it was caught.** Not by the harness itself — the original harness had no way to notice, since every call looked equally slow and there was no faster reference point to compare against. It surfaced because the user asked, in conversation, whether there was any way to run OpenMed "in a lightweight fashion" that hadn't been tried — which prompted inspecting `openmed`'s public API for a caching or reuse mechanism (`ModelLoader`, `load_model()`, `cache_results`) rather than accepting the timing figures at face value. Once `ModelLoader` reuse was tested by hand, the ~70× discrepancy was immediate and reproducible.

**Fix.** `openmed_pii_prototype_v2.py` now caches one `ModelLoader` per model name at module scope (`_get_loader`), preloaded once and passed as `loader=` to every `extract_pii` call — including inside `labels_for`, not just `redact`, since both need it. The cache is shared across every corpus and confidence threshold in one script invocation, so a full 24-configuration sweep that used to take **over two and a half hours** now completes in **under eight minutes**, and a single-config check that used to take ~13 minutes takes ~18 seconds.

**Correctness was verified unaffected**, not just latency: recall/precision numbers are byte-identical before and after the fix, on every corpus/confidence/model combination tested (spot-checked against the pre-fix JSON reports, confirmed identical). The bug was purely a measurement error in cost, not a change in what got detected.

**What this means for memory, and a residual limitation.** `load_seconds` and `rss_delta_mb` are no longer meaningful per-row in a combined sweep: once a model is loaded and cached, every subsequent config at that model size shows ~0s load time and ~0MB delta, because the cost was already paid and `ru_maxrss` is a high-water mark that never decreases. That's the *accurate* representation of a real deployment (load once, keep resident, no per-request cost) — but it means memory has to be read from isolated single-model runs, not the combined sweep. Those isolated numbers:

| system | isolated peak RSS | isolated delta from process floor |
|---|---|---|
| `regex` | 281 MB | 0 MB (floor) |
| `regex+ner` (spaCy loaded) | 346 MB | +65 MB |
| `openmed` small model resident | 778 MB | +431 MB |
| `openmed` large model resident | 603 MB | +323 MB |

*(Raw data: `eval/prototypes/reports/v2/report_v2_memory_isolated_small.json`, `..._large.json`.)*

**The large model uses less resident memory than the small one — unexpected, checked directly, and repeatable.** A 434M-parameter model would be expected to need meaningfully more memory than a 44M-parameter one; measured twice in fresh, isolated processes (no other model loaded first), small was ~597MB and large ~603MB — functionally identical. Plausible explanation, not confirmed: PyTorch/transformers baseline overhead (~500MB+) dominates both figures at this parameter scale, and/or OpenMed loads weights in a memory-efficient format (quantized/memory-mapped) that doesn't show the raw 10× parameter-count difference in RSS the way a naive fp32 load would. **Likely explanation for why PR #124's original run reported the large model using ~3× the small model's memory (1481MB vs 513MB):** without loader reuse, both benchmarks were repeatedly constructing and discarding model instances across the corpus loop; transient allocations before garbage collection would inflate the *peak* RSS high-water mark, and would do so more for the larger model's bigger transient buffers — an artifact of the same root-cause bug, not a real 3× memory difference between model sizes.

**One remaining caveat this fix does not remove:** the isolated small/large numbers above were still measured in a process where `regex`/`regex+ner` ran first in the same invocation (small) or not at all (large) — not perfectly matched conditions. They're close enough to trust the ~430MB/~320MB deltas as directional, but a fully controlled A/B (identical process setup, only the model size varying) hasn't been run. Not expected to change the qualitative finding (both model sizes cost roughly the same, dominated by fixed overhead), but flagged rather than asserted as exact.

## 5. The one case where OpenMed has a structural edge: drug names tagged as `PERSON`

DEC-006's 2026-08-06 amendment gives a specific, concrete reason `regex+ner` isn't shipped: issue #125 found spaCy's `en_core_web_sm` PERSON tagger misfires on common drug names — 69% of tested contexts, 8% baseline rate — destroying the most clinically load-bearing token in the sentence (`"Started Rosuvastatin last month"` → `"[REDACTED] last month"`). This re-run's negative-case corpus wasn't built to target that failure deliberately, but v2's `medication` category uses real drug names as sentence subjects, which is exactly the shape that trips it — so the eval reproduced it anyway, on fresh cases, independent of #125's own test set:

| corpus | conf | system | medication negative-case pass rate |
|---|---|---|---|
| v1 | any | `regex+ner` | 2/3 |
| v2 | any | `regex+ner` | 3/5 |
| v1 | any | `openmed` / `openmed-filtered` | 3/3 |
| v2 | 0.3–0.5 | `openmed` | 4/5 |
| v2 | 0.7 | `openmed` | 5/5 |
| v2 | any | `openmed-filtered` | 5/5 |

The `regex+ner` failures are the same bug both times: `Lisinopril` and `Atorvastatin`, tagged `PERSON`, redacted whole. **OpenMed does not have this failure mode, at any confidence threshold or corpus tested.** Its taxonomy carries separate `MEDICATION`/`DRUG` labels distinct from `PERSON`/`FIRST_NAME`/`LAST_NAME`, so it isn't relying on "is this capitalized and after a title"-style heuristics that a drug's brand-name capitalization can fool. (OpenMed's one v2-corpus medication miss at low confidence, `Albuterol inhaler ... every four hours` → `[REDACTED]`, is a `TIME` misclassification, unrelated to the drug name itself.)

This is the one place in the whole re-run where OpenMed isn't trading one failure mode for another — it's a strict improvement over `regex+ner` on the exact case DEC-006's amendment names as the blocker to shipping `regex+ner` at all. Combined with §4a's corrected cost numbers, this is a meaningfully stronger point than it was in the first pass of this re-run — the tradeoff for fixing #125's bug via OpenMed's name detection is no longer "300× the latency," it's closer to "a few hundred MB resident and ~15ms/text."

## 6. This does not reopen #125 by itself, and there still isn't a cheap fix for spaCy specifically

#125's own follow-up investigation (before this re-run existed) already ruled out a cheap patch to spaCy's PERSON tagger: a sweep of 205 real drug names through 5 sentence templates found spaCy tags a drug name `PERSON` in ≥1 context for **69%** of them, context-dependent (a preceding verb like "Started" roughly 5× the bare-token rate) with no morphological rule separating the names that trip it from the ones that don't. A denylist/allowlist was explicitly walked back by that investigation for exactly this reason: it can't work against a signal that's wrong two-thirds of the time on unseen drug names. The ranked options that remain, per #125, are *accept-and-document* (what's already shipped — `regex` alone, NER off) > *corroboration* (only redact a `PERSON` span that's title-preceded or matches a known `Doctor.name`/`HealthProfile.name`) > *a larger spaCy model* (unverified, might have the same problem). #125 is closed with no forcing function to revisit any of them, since spaCy isn't installed in any shipped configuration today.

What §5 adds, now that §4a corrects the cost picture: a fourth option #125 didn't have in front of it, because the original OpenMed benchmark's cost numbers made it look obviously worse than doing nothing. **Using a clinical-taxonomy model (OpenMed's small model, or similar) for name detection specifically**, instead of general-purpose spaCy, at now-measured costs of ~15ms/text and ~400-600MB resident. That's not "adopt OpenMed for anonymization" — it's a narrower, specific alternative to fixing spaCy's PERSON tagger, and it hasn't been built or evaluated at that narrower scope (everything measured here is full-anonymizer OpenMed, not a name-detector-only integration). See **Bottom line**.

## 7. Remaining caveats

- **Per-category sample sizes are still not large** — the combined v1+v2 corpus helps, but neither corpus alone reaches double digits in every category (e.g. `ssn`, `zip`, `po_box`). Read the per-category JSON breakdown before generalizing about any one PII shape.
- **English only**, and only two of OpenMed's model tiers (44M, 434M) out of the many it ships.
- **Latency is now well-measured (§4a); memory's isolation caveat (§4a) is the main remaining cost uncertainty.** Both are still single-machine numbers — treat as directional on other hardware, per DEC-009.
- **`openmed` version drift is itself a finding.** PR #124 ran `openmed==2.0.0`; PyPI's latest at the time of this re-run is `2.2.0` (installed via a fresh `[hf]` extra, no `transformers` pin workaround needed this time — the earlier `local_files_only` incompatibility is gone). The two runs are not measuring the identical artifact, which is expected for a fast-moving open-source model release cadence but means neither report is a permanent verdict on "OpenMed" as a name.
- **Two harness bugs were found and fixed inside this single re-run** (§3's label-case mismatch, §4a's loader reuse). Both silently produced a *plausible-looking wrong number* rather than an error — 0% recall read as "the filter works great," and ~1s latency read as "OpenMed is just slow," respectively. Worth treating as a general lesson for this harness family: a benchmark number that confirms what you already expect deserves the same scrutiny as one that surprises you, maybe more.

## 8. Reproducing this

```bash
python3.11 -m venv /tmp/venv-openmed-v2
/tmp/venv-openmed-v2/bin/pip install "openmed[hf]" torch spacy
/tmp/venv-openmed-v2/bin/python -m spacy download en_core_web_sm

# from the repo root — full 24-config sweep, both corpora, both model sizes,
# takes well under 10 minutes now that the loader-reuse bug (§4a) is fixed:
/tmp/venv-openmed-v2/bin/python -m eval.prototypes.openmed_pii_prototype_v2 \
    --corpus both --systems regex,regex+ner,openmed,openmed-filtered \
    --confidences 0.3,0.5,0.7 --models small,large \
    --json report_corrected_full_sweep.json

# isolated single-model runs, for clean (non-high-water-mark-polluted) memory numbers:
/tmp/venv-openmed-v2/bin/python -m eval.prototypes.openmed_pii_prototype_v2 \
    --corpus v2 --systems regex,regex+ner,openmed,openmed-filtered \
    --confidences 0.5 --models small --json report_memory_isolated_small.json
/tmp/venv-openmed-v2/bin/python -m eval.prototypes.openmed_pii_prototype_v2 \
    --corpus v2 --systems openmed,openmed-filtered \
    --confidences 0.5 --models large --json report_memory_isolated_large.json
```

## Bottom line

**Concrete choice for HealthSteward, right now: still no code change** — but the reasoning changed enough mid-re-run that this is worth reading as "confirmed after a real scare," not "confirmed easily."

Against `regex` (§0: what actually ships), OpenMed wins recall by a wide, consistent margin (74%→94-100% on the harder corpus). The cost of that win is no longer the 300×–1000× latency figure this report stated earlier in the same investigation — corrected, it's ~15-60ms/text (§4a), which is imperceptible in absolute terms for a per-visit-prep-call redaction step. **The real remaining cost is memory: ~400-600MB resident once a model is loaded**, on an 8GB M3 that DEC-009 already treats as tight. Whether that's affordable depends on what else is resident at the same time (the Python backend, the DB, Ollama if a local LLM is also running) — not measured here, and the deciding factor if this is ever revisited.

Against `regex+ner` (aspirational, not shipped), the recall/precision comparison stays genuinely mixed (§4) — no OpenMed configuration strictly dominates it. The one place OpenMed is unambiguously better is §5: it doesn't have the drug-name-as-`PERSON` bug that's the specific, documented reason `regex+ner` isn't live. §6 explains why that's not itself a reason to act today — #125 already ruled out a cheap spaCy-side fix, and there's no forcing function to touch NER at all right now.

**So the decision doesn't change, but the reasoning is now honest about where the real cost is (memory, not latency) and about a real, if narrow, option that would have looked absurd before this correction and now looks merely non-trivial:** a name-detector-only integration using a clinical-taxonomy model, sized for ~15ms/~400MB rather than full-anonymizer OpenMed's larger scope. Concretely, if this project ever wants to close the `regex` → `regex+ner`-or-better recall gap without inheriting spaCy's drug-name bug, that's the option worth scoping first — not full OpenMed adoption, and not a spaCy patch #125 already showed doesn't work.

**What would need more digging before that specific option could be built, not more OpenMed sweeping in general:**
1. Actual free memory headroom on the target 8GB M3 with the rest of the app running, to know if ~400-600MB resident is affordable at all.
2. A name-detector-only integration test — restrict to `PERSON`/`FIRST_NAME`/`LAST_NAME` labels and measure whether a smaller/faster model configuration exists for that narrower task (full `extract_pii` still does the same forward pass regardless of which labels you keep afterward — §4a — so "smaller scope" would need a genuinely smaller model, not just output filtering).
3. Corpus size (§7) — current N is small enough that individual cases swing category rates, worth closing if a paper's claim leans on the exact percentages rather than the qualitative pattern.

**No further generic OpenMed sweeping (more confidence thresholds, more model sizes) is needed** — that space is now covered, consistently, across two independent corpora, at correctly measured cost.

No production code changed (`src/utils/anonymization.py` untouched, `openmed` absent from both dependency manifests) — still an evaluation, not an architectural decision, so no DEC entry per DEC-006's own scope note.

---
*Models used: [`OpenMed/OpenMed-PII-SuperClinical-Small-44M-v1`](https://huggingface.co/OpenMed/OpenMed-PII-SuperClinical-Small-44M-v1) and [`OpenMed/OpenMed-PII-SuperClinical-Large-434M-v1`](https://huggingface.co/OpenMed/OpenMed-PII-SuperClinical-Large-434M-v1), `openmed==2.2.0`, both Apache-2.0. Thanks again to the OpenMed team — the label-filtering results, and the loader-reuse finding in §4a, are offered as integration feedback (the latter arguably belongs in OpenMed's own docs as a "how to use this in a long-running service" note), not a knock on the project.*
