# OpenMed vs. HealthSteward's PII Anonymizer — Benchmark Findings

**Issue:** [#122](https://github.com/nidhi-menon/HealthSteward/issues/122) · **Harness:** `eval/prototypes/openmed_pii_prototype.py` · **Corpus:** `eval/prototypes/openmed_pii_cases.py` (67 positive, 24 negative cases, transcribed from `tests/test_anonymization.py`)

**Verdict up front:** across every configuration tested — two OpenMed model sizes, three confidence thresholds — no OpenMed setup matched HealthSteward's current regex+NER anonymizer on both PII recall and clinical-content precision at the same time, and every OpenMed configuration was 400×–1500× slower and 2×–10× heavier in memory than what's running today. This isn't a marginal loss; it's decisive enough that no further tuning is likely to change the outcome for this project's constraints.

## Why this exists

HealthSteward sends patient data to an external LLM (Claude API) for visit-prep assistance. [DEC-006](../../docs/notes/DECISIONS.md) established a PII anonymization boundary — nothing leaves the machine unredacted. The current approach is regex patterns plus optional spaCy NER for person names. [OpenMed](https://github.com/OpenMed) is an open-source suite of clinical NLP models, including PII detectors, and issue #122 asked: is it a better fit than what's already running?

## Methodology

**Corpus.** 91 cases transcribed (not imported) from `tests/test_anonymization.py`, tagged by PII category. 67 *positive* cases (text containing PII that must not survive redaction — a miss is a **leak**) and 24 *negative* cases (clinical text with no PII, which must pass through byte-identical — any change is **over-redaction**). Every case cites the test it came from.

**Systems compared:**
- `regex` — `Anonymizer(use_ner=False)`. What a fresh clone of HealthSteward actually runs today, since spaCy is in neither `requirements.txt` nor `environment.yml`.
- `regex+ner` — `Anonymizer(use_ner=True)`, i.e. regex plus spaCy `en_core_web_sm` PERSON detection. What DEC-006 describes as the intended design.
- `openmed` — `openmed.extract_pii()`, scored on the same corpus with the same `[REDACTED]` placeholder so all three are held to one rule. Tested at two model sizes and three confidence thresholds (see below).

**Scoring is intentionally asymmetric**, because a PII detector fails in two directions with different consequences: a *leak* means an identifier reaches an external LLM (the exact failure DEC-006 exists to prevent); *over-redaction* doesn't leak anything but degrades the clinical content the visit-prep call needs to be useful. A detector that redacts everything scores a perfect leak rate and is worthless — so both are reported, never collapsed into one accuracy number.

**Environment.** macOS arm64 (Apple M3, 8GB RAM — the hardware DEC-009 identifies as the binding constraint for this project), Python 3.11.7, `openmed==2.0.0`. OpenMed's `[hf]` extra pulled in `transformers==5.14.1`, which broke pipeline construction (`AutoConfig.from_pretrained() got multiple values for keyword argument 'local_files_only'` — an internal OpenMed/transformers incompatibility, not a bug in this harness). Downgrading to `transformers==4.44.2` fixed it. This means results reflect an older `transformers` pin than OpenMed's default install resolves to today — a confound worth knowing about if these numbers are reproduced later and don't match.

## Results

### Baselines (regex-only vs. regex+NER)

| system | PII caught | clinical content intact | mean latency/text | peak RSS |
|---|---|---|---|---|
| `regex` (what a fresh clone runs) | 63/67 (94%) | 24/24 (100%) | 0.007 ms | 15 MB |
| `regex+ner` (what DEC-006 describes) | 66/67 (99%) | 23/24 (96%) | 1.9 ms | ~304 MB |

`regex+ner`'s one miss is `Anonymizer(use_ner=False)`-independent: `"Call Dr. Smith at 555-123-4567"` still leaks `Smith` even with NER on — single-token surnames after a title are the weak case (tracked separately). Its one over-redaction — `"Lisinopril 10 mg daily"` → `"[REDACTED] 10 mg daily"`, spaCy tagging a drug name as PERSON — is tracked as [#125](https://github.com/nidhi-menon/HealthSteward/issues/125), since the NER path had zero negative-case test coverage before this benchmark.

### OpenMed: confidence threshold sweep (small model, `OpenMed-PII-SuperClinical-Small-44M-v1`)

| confidence | PII caught | clinical content intact | mean latency/text | peak RSS |
|---|---|---|---|---|
| 0.3 | 63/67 (94%) | 17/24 (71%) | 780 ms | ~513 MB |
| 0.5 (library default) | 62/67 (93%) | 17/24 (71%) | 785 ms | ~513 MB |
| 0.7 | 55/67 (82%) | 18/24 (75%) | 872 ms | ~513 MB |

Lowering the threshold recovers a little recall without moving precision; raising it trades meaningful recall for almost no precision gain. No point on this curve reaches `regex+ner`'s combination of 99% recall and 96% precision, let alone beats it.

### OpenMed: model size (`Small-44M` vs. `Large-434M`, both at confidence 0.5)

| model | PII caught | clinical content intact | mean latency/text | peak RSS |
|---|---|---|---|---|
| Small (44M params) | 62/67 (93%) | 17/24 (71%) | 785 ms | ~513 MB |
| Large (434M params) | 56/67 (84%) | 21/24 (88%) | 2993 ms | ~1481 MB |

The larger model is a real precision improvement (17/24 → 21/24, fewer over-redactions) — but it trades recall to get there (93% → 84%), and costs ~4× the latency and ~3× the memory of the small model to do it. Bigger did not mean strictly better here; it moved along the same precision/recall tradeoff rather than dominating it.

### What OpenMed got wrong, concretely

**Leaks the regex baseline catches by construction** (small model, conf 0.5): plain SSN format `123.45.6789`, international phone `+44 (0)20 7946 0958`, insurance IDs (`Policy #: ABC-12345678`, `Group Number: 0012345`), an unlabeled MRN (`Chart 12345678 shows no changes`). These are exactly the structured, format-driven PII shapes regex is built to catch — OpenMed, tuned more for free-text clinical entity recognition, does worse on them than a pattern-matcher.

**Over-redactions confirm a real label-taxonomy mismatch**, not a fluke:

| text | OpenMed's label | why it's wrong here |
|---|---|---|
| `Seen at City Medical Center` | `city` | DEC-006 keeps clinic names deliberately |
| `Follow-up scheduled at Metro Health` | `company_name` | same |
| `Appointment at 10:30` | `time` | scheduling context, not identifying |
| `Weight 185 lbs` | `age` | a vital sign, not a birthdate |
| `Step count averaged 12500 per day` | `postcode` | a fitness metric, not an address |
| `Follow up in January 2026` | `date` | scheduling context DEC-006 explicitly preserves (see `test_month_and_year_without_day_preserved`) |
| `Infusion rate 5551234 mL` | `pin` | a dosage number, not a PIN |

OpenMed's `CANONICAL_LABELS` includes categories like `AGE`, `CONDITION`, `MEDICATION`, and general-purpose `time`/`date`/`postcode` tags this project's policy deliberately does *not* treat as identifiers. Any integration would need real label filtering, not wholesale acceptance of OpenMed's output — this was predicted before running any weights (see PR #124 review discussion) and the run confirms it.

## Caveats — how much to trust this

**High confidence, unlikely to change with more tuning:**
- **Latency.** 780ms–3000ms/text vs. 0.007ms–1.9ms for the baselines is a 400×–1,500,000× gap depending on comparison point. No threshold or model-size choice closes this.
- **Memory.** 513MB–1481MB delta vs. 0–305MB for the baselines.
- **The label-taxonomy mismatch is structural**, not sampling noise — it's a design mismatch between OpenMed's general-purpose PII taxonomy and this project's clinical-content allowlist.

**Lower confidence, treat as directional:**
- **Sample size per category is small** — some categories (`ssn`, `insurance_id`) have only 3-4 cases; a single miss swings the reported rate by 25-33%.
- **Corpus bias toward the incumbent.** These 91 cases were transcribed from tests written to validate the *regex* approach, and are dense with exact-format edge cases (PO box variants, zip+4, address suffixes) that regex is essentially defined to catch. It's comparatively light on the free-text, context-dependent PII that NER-style models are built for. This is the incumbent's home turf, not a neutral corpus.
- **`transformers` version confound** — see Environment above. Results may not reproduce exactly against OpenMed's default install today.
- **Only English models tested**, only two of the many size tiers OpenMed ships (33M–568M+ across families), only three points on the confidence curve.
- **Single run, no repeated trials** — inference is deterministic so point estimates wouldn't move, but there are no error bars on latency/memory, both of which fluctuate with system load.

## Reproducing this

```bash
python -m venv /tmp/venv-openmed
/tmp/venv-openmed/bin/pip install "openmed[hf]"
/tmp/venv-openmed/bin/pip install "transformers<4.45"   # works around the local_files_only crash — see Environment
/tmp/venv-openmed/bin/pip install spacy && /tmp/venv-openmed/bin/python -m spacy download en_core_web_sm

# from the repo root:
/tmp/venv-openmed/bin/python -m eval.prototypes.openmed_pii_prototype --json report.json
/tmp/venv-openmed/bin/python -m eval.prototypes.openmed_pii_prototype --systems openmed --confidence 0.3 --json report_conf03.json
/tmp/venv-openmed/bin/python -m eval.prototypes.openmed_pii_prototype --systems openmed --confidence 0.7 --json report_conf07.json
/tmp/venv-openmed/bin/python -m eval.prototypes.openmed_pii_prototype --systems openmed \
    --model OpenMed/OpenMed-PII-SuperClinical-Large-434M-v1 --json report_large434m.json
```

## Bottom line

For a project whose binding hardware constraint is an 8GB M3 and whose anonymization boundary already achieves 94-99% recall at sub-2ms latency, OpenMed — as tested, across two model sizes and three thresholds — does not clear the bar. It is evaluated and not adopted. No production code changed (`src/utils/anonymization.py` is untouched, `openmed` is absent from both dependency manifests), so this doesn't need a DEC entry per DEC-006's own scope note; it's a closed evaluation, not an architectural decision.

This isn't a general verdict on OpenMed's quality — the corpus here is small and skews toward exactly the PII shapes regex handles well. It's a specific answer to a specific question: does OpenMed improve on what HealthSteward already ships, under HealthSteward's constraints? No.

---
*Models used: [`OpenMed/OpenMed-PII-SuperClinical-Small-44M-v1`](https://huggingface.co/OpenMed/OpenMed-PII-SuperClinical-Small-44M-v1) and [`OpenMed/OpenMed-PII-SuperClinical-Large-434M-v1`](https://huggingface.co/OpenMed/OpenMed-PII-SuperClinical-Large-434M-v1), both Apache-2.0, built on `microsoft/deberta-v3-{small,large}`. Thanks to the OpenMed team for shipping an open-source clinical PII toolkit worth benchmarking against — the label-taxonomy findings above are offered as integration feedback, not a knock on the project.*
