"""HIPAA Safe Harbor coverage-gap eval — tests regex-extended, regex+ner-extended,
openmed, and openmed-filtered against `phi_gap_cases_v3.py`.

**PROTOTYPE / EVALUATION ONLY.** The "extended" regex patterns here are a
prototype, not a proposal to merge as-is — `src/utils/anonymization.py` is
untouched. This script exists to produce evidence for that future decision,
same as `openmed_pii_prototype_v2.py`.

## What's being tested

Six categories with no dedicated pattern in production `PII_PATTERNS`: `url`,
`ip_address`, `license_number`, `account_number`, `vehicle_id`, `device_serial`.
`regex-extended` / `regex+ner-extended` layer six new patterns (defined below,
same label-anchored style as the existing `mrn`/`insurance_id` patterns) on top
of the current `Anonymizer`'s output. `openmed` / `openmed-filtered` are
unmodified — OpenMed's own `CANONICAL_LABELS` already include `URL`,
`IP_ADDRESS`, `VIN`, `ACCOUNT_NUMBER`, `VEHICLE_REGISTRATION`, so this checks
whether it already handles these categories for free.

## Usage

    /tmp/venv-openmed-v2/bin/python -m eval.prototypes.phi_gap_prototype_v3 \\
        --systems regex,regex-extended,regex+ner-extended,openmed,openmed-filtered \\
        --confidences 0.3,0.5 --models small --json report_phi_gap.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Callable, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from eval.prototypes.phi_gap_cases_v3 import (  # noqa: E402
    ALL_CATEGORIES,
    NEGATIVE_CASES,
    POSITIVE_CASES,
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
from eval.prototypes.openmed_pii_prototype_v2 import (  # noqa: E402
    build_openmed_redactor,
    project_redact_labels,
)

# --- Prototype extension patterns --------------------------------------
#
# Same style as the existing label-anchored patterns in PII_PATTERNS
# (mrn, insurance_id): a named `label` group kept in the output, the value
# redacted. Validated (see conversation / dev log) against the full v1+v2
# negative corpus (70 cases) with zero false positives before being layered
# on top of the shipped Anonymizer here.

EXTENDED_PATTERNS = {
    "url": re.compile(r"https?://[^\s<>\"]+", re.IGNORECASE),
    "ip_address": re.compile(
        r"\b(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)\b"
    ),
    "license_number": re.compile(
        r"(?P<label>\b(?:Driver.?s?\s+License|License|Certificate|Cert|DEA)"
        r"\s*(?:Number|No\.?|#)?\s*[:#]?\s*)"
        r"(?=[A-Z0-9-]*\d)[A-Z0-9][A-Z0-9-]{3,}\b",
        re.IGNORECASE,
    ),
    "account_number": re.compile(
        r"(?P<label>\bAccount\s*(?:Number|No\.?|#)?\s*[:#]?\s*)"
        r"(?=[A-Z0-9-]*\d)[A-Z0-9][A-Z0-9-]{3,}\b",
        re.IGNORECASE,
    ),
    "vehicle_id": re.compile(
        r"(?P<label>\bVIN\s*[:#]?\s*)[A-HJ-NPR-Z0-9]{11,17}\b", re.IGNORECASE
    ),
    "device_serial": re.compile(
        r"(?P<label>\b(?:Device\s+)?Serial\s*(?:Number|No\.?|#)?\s*[:#]?\s*)[A-Z0-9-]{4,}\b",
        re.IGNORECASE,
    ),
}

LABEL_ANCHORED = {"license_number", "account_number", "vehicle_id", "device_serial"}


def _apply_extended_patterns(text: str) -> str:
    for name, pattern in EXTENDED_PATTERNS.items():
        if name in LABEL_ANCHORED:
            text = pattern.sub(r"\g<label>[REDACTED]", text)
        else:
            text = pattern.sub("[REDACTED]", text)
    return text


def build_regex_extended_redactor() -> tuple[Callable[[str], str], str]:
    base, _ = build_regex_redactor()

    def redact(text: Optional[str]) -> Optional[str]:
        if text is None:
            return text
        return _apply_extended_patterns(base(text))

    return redact, "Anonymizer(use_ner=False) + 6 prototype patterns (url/ip/license/account/vin/device)"


def build_regex_ner_extended_redactor() -> tuple[Optional[Callable[[str], str]], str]:
    base, detail = build_regex_ner_redactor()
    if base is None:
        return None, detail

    def redact(text: Optional[str]) -> Optional[str]:
        if text is None:
            return text
        return _apply_extended_patterns(base(text))

    return redact, detail + " + 6 prototype patterns"


def run_system(name, builder, positives, negatives):
    import time
    rss_before = _peak_rss_mb()
    load_start = time.perf_counter()
    try:
        redact, detail = builder()
    except Exception as exc:  # noqa: BLE001
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


def _pct(passed, total):
    return f"{passed}/{total} ({100.0 * passed / total:.0f}%)" if total else "n/a"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument(
        "--systems",
        default="regex,regex-extended,regex+ner-extended,openmed,openmed-filtered",
    )
    parser.add_argument("--models", default="small")
    parser.add_argument("--confidences", default="0.5")
    parser.add_argument("--json", dest="json_path", default=None)
    args = parser.parse_args(argv)

    systems = [s.strip() for s in args.systems.split(",") if s.strip()]
    model_aliases = {"small": "OpenMed/OpenMed-PII-SuperClinical-Small-44M-v1",
                      "large": "OpenMed/OpenMed-PII-SuperClinical-Large-434M-v1"}
    models = [m.strip() for m in args.models.split(",") if m.strip()]
    confidences = [float(c) for c in args.confidences.split(",") if c.strip()]
    label_filter = project_redact_labels()

    builders_static = {
        "regex": build_regex_redactor,
        "regex-extended": build_regex_extended_redactor,
        "regex+ner-extended": build_regex_ner_extended_redactor,
    }

    all_results = []
    for name in systems:
        if name in builders_static:
            r = run_system(name, builders_static[name], POSITIVE_CASES, NEGATIVE_CASES)
            all_results.append(("n/a", "n/a", r))
        elif name in ("openmed", "openmed-filtered"):
            for model_alias in models:
                model_name = model_aliases.get(model_alias, model_alias)
                for conf in confidences:
                    lf = label_filter if name == "openmed-filtered" else None
                    r = run_system(
                        name,
                        lambda mn=model_name, c=conf, lf=lf: build_openmed_redactor(mn, c, lf),
                        POSITIVE_CASES, NEGATIVE_CASES,
                    )
                    all_results.append((model_alias, conf, r))
        else:
            parser.error(f"unknown system: {name}")

    print()
    print("=" * 100)
    print("HIPAA Safe Harbor coverage-gap eval — url / ip / license / account / vin / device")
    print("=" * 100)
    print(f"Corpus: {len(POSITIVE_CASES)} positive, {len(NEGATIVE_CASES)} negative, "
          f"{len(ALL_CATEGORIES)} categories")
    print()
    print(f"{'model':<8} {'conf':<6} {'system':<22} {'recall':<20} {'precision':<20} {'mean ms':>9}")
    for model_alias, conf, r in all_results:
        if not r.available:
            print(f"{model_alias:<8} {conf!s:<6} {r.name:<22} SKIPPED — {r.unavailable_reason}")
            continue
        pos_pass = sum(1 for c in r.positives if c.passed)
        neg_pass = sum(1 for c in r.negatives if c.passed)
        print(f"{model_alias:<8} {conf!s:<6} {r.name:<22} "
              f"{_pct(pos_pass, len(r.positives)):<20} {_pct(neg_pass, len(r.negatives)):<20} "
              f"{r.mean_ms_per_text:>9.1f}")

    print()
    for model_alias, conf, r in all_results:
        if not r.available or not r.leaks:
            continue
        print(f"-- {r.name} ({model_alias}, conf={conf}) leaks --")
        for c in r.leaks:
            print(f"  [{c.category}] {c.text!r} -> survived: {c.survived}")

    if args.json_path:
        from dataclasses import asdict
        out = {
            "corpus": {"positive": len(POSITIVE_CASES), "negative": len(NEGATIVE_CASES),
                       "categories": list(ALL_CATEGORIES)},
            "results": [
                {
                    "model_alias": model_alias, "confidence": conf,
                    **{k: v for k, v in asdict(r).items() if k not in ("positives", "negatives")},
                    "positive_pass": sum(1 for c in r.positives if c.passed),
                    "negative_pass": sum(1 for c in r.negatives if c.passed),
                    "leaks": [asdict(c) for c in r.leaks],
                    "over_redactions": [asdict(c) for c in r.over_redactions],
                }
                for model_alias, conf, r in all_results
            ],
        }
        Path(args.json_path).write_text(json.dumps(out, indent=2))
        print(f"JSON report written to {args.json_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
