"""OpenMed PII re-run — bias corrections for issue #122 follow-up.

**PROTOTYPE / EVALUATION ONLY**, same non-production guarantee as
`openmed_pii_prototype.py`: no changes to `src/`, `openmed` stays out of both
dependency manifests.

## Why this script exists alongside `openmed_pii_prototype.py`

The original benchmark (PR #124, `OPENMED_FINDINGS.md`) found no OpenMed
configuration beat the current regex(+NER) anonymizer on both recall and
precision, but flagged concerns of its own that this script addresses in order:

1. **Corpus bias** — the original corpus was transcribed from
   `tests/test_anonymization.py`, i.e. from the regex implementation's own test
   suite, and is denser with exact-format fragments than natural free text.
   This script adds `eval/prototypes/openmed_pii_cases_v2.py`, an independently
   written, natural-sentence corpus, and runs *both* corpora rather than
   replacing one with the other (`--corpus v1|v2|both`).
2. **Small per-category samples** — v2's corpus roughly doubles negative-case
   coverage and broadens category breadth (23 categories vs. 14 negative-side).
   Both corpora are still reported per-category rather than pretending the
   combined N erases single-case swings.
3. **Label-taxonomy mismatch** — the original run scored OpenMed by accepting
   every entity `extract_pii` returned, which is what produced the confirmed
   over-redaction of clinic names, vitals, and dosages under labels
   (`city`, `time`, `age`, ...) this project's policy keeps. This script adds an
   `openmed-filtered` system: the same detector, restricted to the label set
   `PROJECT_REDACT_LABELS` below — OpenMed's own `critical_labels()` (identity,
   contact, and financial identifiers) plus `DATE` and `ZIPCODE`, which this
   project's regex anonymizer treats as identifying but OpenMed's general
   `critical_labels()` does not. A label outside this set is never redacted,
   regardless of what OpenMed detected.
4. **Narrow sweep** — `--confidences` and `--models` each take comma-separated
   lists; the harness runs the full cross product and reports every
   configuration, rather than one confidence value at a time.

## A fifth issue, found while building this script rather than inherited from #124

`openmed.extract_pii()` reconstructs its model pipeline on every call unless a
reusable `openmed.ModelLoader` is loaded once and passed in as `loader=`. This
script's own first draft didn't do that, and reported OpenMed's small model at
~900-1030ms/text — in the same range PR #124 originally reported. That number
was a harness bug, not a property of OpenMed: with the loader cached and reused
(`_get_loader` below, module-scoped, keyed by model name), the same model runs
at ~13-17ms/text, a ~60-70x difference. Recall/precision are unaffected — only
timing was wrong. See `OPENMED_FINDINGS_V2.md` §4a for the full account,
including why the original PR #124 numbers were very likely hitting the same
bug (its harness never reused a loader either).

## Usage

    /tmp/venv-openmed/bin/python -m eval.prototypes.openmed_pii_prototype_v2 \\
        --corpus both --systems regex,openmed,openmed-filtered \\
        --confidences 0.3,0.5,0.7 --models small,large --json report_v2.json
"""

from __future__ import annotations

import argparse
import json
import platform
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Callable, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from eval.prototypes.openmed_pii_cases import (  # noqa: E402
    ALL_CATEGORIES as V1_CATEGORIES,
    NEGATIVE_CASES as V1_NEGATIVE,
    POSITIVE_CASES as V1_POSITIVE,
)
from eval.prototypes.openmed_pii_cases_v2 import (  # noqa: E402
    ALL_CATEGORIES as V2_CATEGORIES,
    NEGATIVE_CASES as V2_NEGATIVE,
    POSITIVE_CASES as V2_POSITIVE,
)
from eval.prototypes.openmed_pii_prototype import (  # noqa: E402
    SystemResult,
    _peak_rss_mb,
    build_regex_ner_redactor,
    build_regex_redactor,
    measure_latency,
    score_negative,
    score_positive,
)

# OpenMed's own `critical_labels()` (identity/contact/financial identifiers)
# plus the two labels this project's policy redacts but OpenMed's general
# taxonomy does not treat as inherently critical: DATE (this project redacts
# *all* dates, not just DOB) and ZIPCODE (part of a redacted address). Built at
# runtime from `openmed.critical_labels()` when available so this list tracks
# upstream label changes rather than silently going stale; falls back to a
# pinned snapshot (captured from openmed==2.2.0) when openmed isn't importable
# yet (e.g. --systems regex, no venv).
_PINNED_CRITICAL_LABELS = frozenset({
    "PERSON", "IBAN", "LAST_NAME", "ETHNICITY", "DATE_OF_BIRTH", "API_KEY",
    "USERNAME", "ID_NUM", "PASSWORD", "BITCOIN_ADDRESS", "STREET_ADDRESS",
    "IP_ADDRESS", "USER_AGENT", "SSN", "LITECOIN_ADDRESS",
    "VEHICLE_REGISTRATION", "BIC", "ACCOUNT_NUMBER", "CREDIT_CARD",
    "GPS_COORDINATES", "MAC_ADDRESS", "IMEI", "EMAIL", "MASKED_NUMBER",
    "PHONE", "CVV", "ETHEREUM_ADDRESS", "FIRST_NAME", "PREFIX", "URL",
    "BUILDING_NUMBER", "VIN", "MIDDLE_NAME", "PIN",
})
_POLICY_ADDITIONS = frozenset({"DATE", "ZIPCODE"})


def project_redact_labels() -> frozenset[str]:
    try:
        import openmed
        return frozenset(openmed.critical_labels()) | _POLICY_ADDITIONS
    except ImportError:
        return _PINNED_CRITICAL_LABELS | _POLICY_ADDITIONS


CORPORA = {
    "v1": (V1_POSITIVE, V1_NEGATIVE, V1_CATEGORIES,
           "tests/test_anonymization.py (transcribed)"),
    "v2": (V2_POSITIVE, V2_NEGATIVE, V2_CATEGORIES,
           "independently written, in-context clinical sentences"),
}

MODEL_ALIASES = {
    "small": "OpenMed/OpenMed-PII-SuperClinical-Small-44M-v1",
    "large": "OpenMed/OpenMed-PII-SuperClinical-Large-434M-v1",
}

SYSTEM_REGEX = "regex"
SYSTEM_REGEX_NER = "regex+ner"
SYSTEM_OPENMED = "openmed"
SYSTEM_OPENMED_FILTERED = "openmed-filtered"
ALL_SYSTEMS = (SYSTEM_REGEX, SYSTEM_REGEX_NER, SYSTEM_OPENMED, SYSTEM_OPENMED_FILTERED)


def _redact_spans(text: str, spans: list[tuple[int, int]], placeholder: str) -> str:
    if not spans:
        return text
    merged: list[list[int]] = []
    for start, end in sorted(spans):
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    result = text
    for start, end in reversed(merged):
        result = result[:start] + placeholder + result[end:]
    return result


# `extract_pii` reloads the model from disk/HF cache on every call unless a
# reusable `ModelLoader` is passed in — a fresh load costs roughly 1s per
# call, which dominates and hides steady-state inference latency (~15ms).
# A real integration would obviously load once and reuse; scoring per-call
# reload cost as "latency" would overstate OpenMed's cost by ~60-70x, which is
# exactly what the first version of this harness did before this was caught.
# Cached at module scope, keyed by model name, so the loader — and the model
# weights it holds — are shared across every confidence threshold and every
# corpus in one script invocation, not just within a single `run_system` call.
_LOADER_CACHE: dict[str, "object"] = {}


def _get_loader(openmed_module, model_name: str):
    loader = _LOADER_CACHE.get(model_name)
    if loader is None:
        loader = openmed_module.ModelLoader()
        loader.load_model(model_name)
        _LOADER_CACHE[model_name] = loader
    return loader


def build_openmed_redactor(
    model: Optional[str],
    confidence: float,
    label_filter: Optional[frozenset[str]],
) -> tuple[Optional[Callable[[str], str]], str]:
    """Build a redactor backed by `openmed.extract_pii`.

    When `label_filter` is given, only entities whose canonical label is in the
    set are redacted — everything else (e.g. `TIME`, `AGE`, `MEDICATION`) passes
    through untouched, regardless of what OpenMed detected. This is the
    correction for the confirmed label-taxonomy mismatch: without it, OpenMed's
    general-purpose PII taxonomy over-redacts clinical content this project's
    policy keeps (see module docstring, point 3).
    """
    try:
        import openmed
    except ImportError:
        return None, "openmed not installed in this environment"

    version = getattr(openmed, "__version__", "unknown")
    model_name = model or openmed.get_default_pii_model("en")
    loader = _get_loader(openmed, model_name)
    kwargs = {"model_name": model_name, "confidence_threshold": confidence, "loader": loader}

    probe_text = "Call Dr. Smith at 555-123-4567"
    try:
        probe = openmed.extract_pii(probe_text, **kwargs)
    except Exception as exc:  # noqa: BLE001 — the failure itself is the finding
        return None, (
            f"openmed {version} installed, but extract_pii(model_name={model_name!r}) "
            f"raised {type(exc).__name__}: {exc}"
        )

    entities_attr = getattr(probe, "entities", None)
    if entities_attr is None and not isinstance(probe, (list, tuple)):
        return None, f"openmed {version}: extract_pii returned an unrecognized shape"

    def _entities(text: str):
        result = openmed.extract_pii(text, **kwargs)
        ents = getattr(result, "entities", None)
        if ents is None and isinstance(result, (list, tuple)):
            ents = result
        return ents or []

    def _label_of(ent) -> str:
        """Canonical (uppercase) label for one entity.

        `extract_pii` returns raw model labels (`last_name`, `phone_number`,
        `date_of_birth`, ...), not the `CANONICAL_LABELS` vocabulary that
        `critical_labels()` and `PROJECT_REDACT_LABELS` are expressed in.
        `canonical_label` is only present on some entity shapes, so normalize
        explicitly rather than trusting it to already match — an early version
        of this filter silently matched nothing because of this mismatch,
        which would have reported 0% recall as a real finding instead of a bug.
        """
        raw = str(
            getattr(ent, "canonical_label", None)
            or getattr(ent, "label", None)
            or (ent.get("label") if isinstance(ent, dict) else None)
            or "?"
        )
        try:
            return str(openmed.normalize_label(raw))
        except Exception:  # noqa: BLE001 — fall back to the raw label
            return raw.upper()

    def _span_of(ent) -> Optional[tuple[int, int]]:
        for ks, ke in (("start", "end"), ("start_char", "end_char"), ("begin", "end")):
            if isinstance(ent, dict):
                if ks in ent and ke in ent:
                    return int(ent[ks]), int(ent[ke])
            else:
                if hasattr(ent, ks) and hasattr(ent, ke):
                    return int(getattr(ent, ks)), int(getattr(ent, ke))
        return None

    def labels_for(text: str) -> tuple[str, ...]:
        ents = _entities(text)
        if label_filter is not None:
            ents = [e for e in ents if _label_of(e) in label_filter]
        return tuple(_label_of(e) for e in ents)

    def redact(text: Optional[str]) -> Optional[str]:
        if not text:
            return text
        ents = _entities(text)
        if label_filter is not None:
            ents = [e for e in ents if _label_of(e) in label_filter]
        spans = [s for s in (_span_of(e) for e in ents) if s is not None]
        return _redact_spans(text, spans, "[REDACTED]")

    redact.label_fn = labels_for  # type: ignore[attr-defined]
    filter_note = (
        f"filtered to {len(label_filter)} project-critical labels"
        if label_filter is not None else "unfiltered (accepts every OpenMed label)"
    )
    return redact, (
        f"openmed {version} via extract_pii(model_name={model_name!r}, "
        f"confidence_threshold={confidence}), {filter_note}"
    )


def run_system(
    name: str,
    builder: Callable[[], tuple[Optional[Callable[[str], str]], str]],
    positives,
    negatives,
) -> SystemResult:
    import time
    rss_before = _peak_rss_mb()
    load_start = time.perf_counter()
    try:
        redact, detail = builder()
    except Exception as exc:  # noqa: BLE001 — a failed build is a reportable result
        return SystemResult(name=name, available=False, unavailable_reason=f"{type(exc).__name__}: {exc}")
    load_seconds = time.perf_counter() - load_start

    if redact is None:
        return SystemResult(name=name, available=False, unavailable_reason=detail)

    result = SystemResult(name=name, available=True, detail=detail, load_seconds=load_seconds)
    result.positives = [score_positive(c, redact) for c in positives]
    result.negatives = [score_negative(c, redact) for c in negatives]
    texts = [c.text for c in positives] + [c.text for c in negatives]
    result.mean_ms_per_text, result.p95_ms_per_text = measure_latency(redact, texts)
    result.peak_rss_mb_after = _peak_rss_mb()
    result.rss_delta_mb = result.peak_rss_mb_after - rss_before
    return result


def _pct(passed: int, total: int) -> str:
    return f"{passed}/{total} ({100.0 * passed / total:.0f}%)" if total else "n/a"


def run_config(
    corpus_name: str, positives, negatives, categories,
    systems: list[str], model_alias: str, model_name: str, confidence: float,
    label_filter: frozenset[str],
) -> dict:
    builders = {
        SYSTEM_REGEX: build_regex_redactor,
        SYSTEM_REGEX_NER: build_regex_ner_redactor,
        SYSTEM_OPENMED: lambda: build_openmed_redactor(model_name, confidence, None),
        SYSTEM_OPENMED_FILTERED: lambda: build_openmed_redactor(model_name, confidence, label_filter),
    }
    results = []
    for name in systems:
        r = run_system(name, builders[name], positives, negatives)
        results.append(r)
    return {
        "corpus": corpus_name,
        "model_alias": model_alias,
        "model_name": model_name if any(s in systems for s in (SYSTEM_OPENMED, SYSTEM_OPENMED_FILTERED)) else None,
        "confidence": confidence,
        "categories": categories,
        "results": results,
    }


def print_summary(configs: list[dict]) -> None:
    print()
    print("=" * 100)
    print("OpenMed PII re-run — issue #122 follow-up")
    print("=" * 100)
    print(f"Platform : {platform.platform()}")
    print(f"Python   : {platform.python_version()} ({platform.machine()})")
    print("Note     : latency/RSS reflect THIS machine (DEC-009's 8GB M3 is the binding constraint).")
    print()
    print(f"{'corpus':<6} {'model':<7} {'conf':<6} {'system':<18} "
          f"{'recall':<20} {'precision':<20} {'mean ms':>9} {'p95 ms':>9}")
    for cfg in configs:
        for r in cfg["results"]:
            if not r.available:
                print(f"{cfg['corpus']:<6} {cfg['model_alias']:<7} {cfg['confidence']:<6} "
                      f"{r.name:<18} SKIPPED — {r.unavailable_reason}")
                continue
            pos_pass = sum(1 for c in r.positives if c.passed)
            neg_pass = sum(1 for c in r.negatives if c.passed)
            print(f"{cfg['corpus']:<6} {cfg['model_alias']:<7} {cfg['confidence']:<6} "
                  f"{r.name:<18} {_pct(pos_pass, len(r.positives)):<20} "
                  f"{_pct(neg_pass, len(r.negatives)):<20} "
                  f"{r.mean_ms_per_text:>9.1f} {r.p95_ms_per_text:>9.1f}")
    print()


def to_json(configs: list[dict], label_filter: frozenset[str]) -> dict:
    return {
        "issue": 122,
        "prototype_only": True,
        "rerun_of": "eval/prototypes/OPENMED_FINDINGS.md (PR #124)",
        "platform": {
            "platform": platform.platform(),
            "machine": platform.machine(),
            "python": platform.python_version(),
        },
        "project_redact_labels": sorted(label_filter),
        "configs": [
            {
                "corpus": cfg["corpus"],
                "model_alias": cfg["model_alias"],
                "model_name": cfg["model_name"],
                "confidence": cfg["confidence"],
                "systems": [
                    {
                        **{k: v for k, v in asdict(r).items() if k not in ("positives", "negatives")},
                        "positive_pass": sum(1 for c in r.positives if c.passed),
                        "negative_pass": sum(1 for c in r.negatives if c.passed),
                        "categories": r.category_table(),
                        "leaks": [asdict(c) for c in r.leaks],
                        "over_redactions": [asdict(c) for c in r.over_redactions],
                    }
                    for r in cfg["results"]
                ],
            }
            for cfg in configs
        ],
    }


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--corpus", choices=["v1", "v2", "both"], default="both")
    parser.add_argument("--systems", default=",".join(ALL_SYSTEMS),
                         help=f"comma-separated subset of {ALL_SYSTEMS}")
    parser.add_argument("--models", default="small",
                         help="comma-separated aliases (small,large) or full HF model ids")
    parser.add_argument("--confidences", default="0.5",
                         help="comma-separated confidence thresholds, e.g. 0.3,0.5,0.7")
    parser.add_argument("--json", dest="json_path", default=None)
    args = parser.parse_args(argv)

    systems = [s.strip() for s in args.systems.split(",") if s.strip()]
    unknown = [s for s in systems if s not in ALL_SYSTEMS]
    if unknown:
        parser.error(f"unknown system(s): {', '.join(unknown)}")

    corpora = ["v1", "v2"] if args.corpus == "both" else [args.corpus]
    model_aliases = [m.strip() for m in args.models.split(",") if m.strip()]
    confidences = [float(c) for c in args.confidences.split(",") if c.strip()]
    label_filter = project_redact_labels()

    needs_openmed = any(s in systems for s in (SYSTEM_OPENMED, SYSTEM_OPENMED_FILTERED))
    openmed_grid = [(a, MODEL_ALIASES.get(a, a)) for a in model_aliases] if needs_openmed else [("n/a", None)]
    conf_grid = confidences if needs_openmed else [0.5]

    configs = []
    for corpus_name in corpora:
        positives, negatives, categories, _source = CORPORA[corpus_name]
        for model_alias, model_name in openmed_grid:
            for confidence in conf_grid:
                configs.append(run_config(
                    corpus_name, positives, negatives, categories,
                    systems, model_alias, model_name, confidence, label_filter,
                ))
                # non-openmed systems don't vary by model/confidence — run once
                if not needs_openmed:
                    break
            if not needs_openmed:
                break

    print_summary(configs)

    if args.json_path:
        Path(args.json_path).write_text(json.dumps(to_json(configs, label_filter), indent=2))
        print(f"JSON report written to {args.json_path}")

    return 0 if any(r.available for cfg in configs for r in cfg["results"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
