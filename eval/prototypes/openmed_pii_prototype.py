"""OpenMed PII-detection prototype benchmark (issue #122).

**PROTOTYPE / EVALUATION ONLY.** This script does not touch the production
anonymization path and `openmed` is deliberately absent from `requirements.txt`
and `environment.yml`. Nothing in `src/` imports this module, and `tests/` does
not collect it. Swapping the production implementation would be a real
architectural decision (new dependency in the actual manifest, a change adjacent
to DEC-006's trust boundary) needing its own DEC entry and explicit sign-off —
this script exists only to produce the evidence such a decision would need.

## What it measures

Three systems, scored on the identical corpus (`eval/prototypes/openmed_pii_cases.py`,
transcribed from `tests/test_anonymization.py`):

- ``regex`` — the current `Anonymizer` with NER disabled. This is what actually
  runs whenever spaCy or its model is not installed, which is the default state
  of a fresh clone (spaCy is in neither manifest).
- ``regex+ner`` — the current `Anonymizer` as DEC-006 describes it, regex plus
  spaCy `en_core_web_sm` PERSON detection. Skipped with a clear note if spaCy or
  the model is unavailable, rather than silently reported as the regex numbers.
- ``openmed`` — OpenMed's detector, with its spans redacted using the same
  ``[REDACTED]`` placeholder so the three are scored by one rule.

Scoring is deliberately asymmetric, because the two failure directions are not
symmetric in consequence:

- **Leak** (positive case): a PII substring survives redaction. This is the
  failure DEC-006 exists to prevent — it means the identifier reaches an
  external LLM.
- **Over-redaction** (negative case): clinical text is altered. Nothing leaks,
  but the visit-prep call loses the content that makes it useful. A detector
  that redacts everything scores a perfect leak rate and is worthless.

Both are reported per category, never collapsed into one accuracy number.

## Resource measurement caveat

Latency and memory here are measured on whatever machine runs this script. The
binding constraint in DEC-009 is an **8GB M3**, so treat the numbers as
directional unless this is being run on that machine — `--json` output records
the platform so a report can't be read out of context. Model size on disk and
parameter count transfer across hardware; wall-clock and peak RSS do not.

## Usage

Install into an isolated environment — NOT the project env:

    python -m venv /tmp/venv-openmed
    /tmp/venv-openmed/bin/pip install "openmed[hf]"
    # optional, to score the regex+ner system too:
    /tmp/venv-openmed/bin/pip install spacy && \
        /tmp/venv-openmed/bin/python -m spacy download en_core_web_sm

    /tmp/venv-openmed/bin/python -m eval.prototypes.openmed_pii_prototype
    /tmp/venv-openmed/bin/python -m eval.prototypes.openmed_pii_prototype --json report.json

`--systems` limits which systems run (e.g. `--systems regex,regex+ner`), which
makes the baselines runnable in the plain project env without openmed installed.
"""

from __future__ import annotations

import argparse
import json
import platform
import resource
import statistics
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from eval.prototypes.openmed_pii_cases import (  # noqa: E402
    ALL_CATEGORIES,
    NEGATIVE_CASES,
    POSITIVE_CASES,
    NegativeCase,
    PositiveCase,
)
from src.utils.anonymization import DEFAULT_REDACTION, Anonymizer  # noqa: E402

# Latency is averaged over this many passes per text. A single pass on a short
# string is dominated by measurement noise; the model is warmed once first so
# the first-call graph/tokenizer setup doesn't land in the average.
LATENCY_PASSES = 3

# Peak RSS once this module's own imports are done, before any system is built.
# `ru_maxrss` is a high-water mark for the whole process and never decreases, so
# every system's peak includes whatever earlier ones allocated. Recording the
# floor here lets the report say what was already resident before measurement
# began — which matters a lot in the isolated env, where importing
# `src.utils.anonymization` alone costs ~500MB if spaCy is installed next to
# torch (spaCy's thinc backend imports torch when it finds it), versus ~15MB in
# the plain project env. Per-system `rss_delta_mb` is the number to compare; run
# with `--systems <one>` for a clean absolute figure.
POST_IMPORT_RSS_KB = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss

SYSTEM_REGEX = "regex"
SYSTEM_REGEX_NER = "regex+ner"
SYSTEM_OPENMED = "openmed"
DEFAULT_SYSTEMS = (SYSTEM_REGEX, SYSTEM_REGEX_NER, SYSTEM_OPENMED)


# --- Results --------------------------------------------------------------


@dataclass
class CaseResult:
    text: str
    category: str
    passed: bool
    # For positives: the must_remove substrings that survived. For negatives:
    # empty, since the failure is "output != input" and `output` records it.
    survived: tuple[str, ...] = ()
    output: str = ""
    # Detector-reported entity labels, when the system exposes them. Empty for
    # the regex systems, which have no comparable per-match taxonomy worth
    # reporting. On a failing negative case this is the diagnosis: it says
    # *which* category the detector thought it saw in clinical text.
    detected_labels: tuple[str, ...] = ()


@dataclass
class SystemResult:
    name: str
    available: bool
    # Why the system could not run, when available is False.
    unavailable_reason: Optional[str] = None
    detail: str = ""
    positives: list[CaseResult] = field(default_factory=list)
    negatives: list[CaseResult] = field(default_factory=list)
    load_seconds: Optional[float] = None
    mean_ms_per_text: Optional[float] = None
    p95_ms_per_text: Optional[float] = None
    peak_rss_mb_after: Optional[float] = None
    rss_delta_mb: Optional[float] = None

    @property
    def leaks(self) -> list[CaseResult]:
        return [c for c in self.positives if not c.passed]

    @property
    def over_redactions(self) -> list[CaseResult]:
        return [c for c in self.negatives if not c.passed]

    def category_table(self) -> dict[str, dict[str, int]]:
        table: dict[str, dict[str, int]] = {}
        for kind, cases in (("positive", self.positives), ("negative", self.negatives)):
            for c in cases:
                row = table.setdefault(
                    c.category,
                    {"positive_total": 0, "positive_pass": 0,
                     "negative_total": 0, "negative_pass": 0},
                )
                row[f"{kind}_total"] += 1
                if c.passed:
                    row[f"{kind}_pass"] += 1
        return table


# --- Redactors ------------------------------------------------------------
#
# A "redactor" is any `str -> str` that returns the text with PII replaced. The
# three systems differ only in how they find spans; scoring never sees the
# difference.


def _peak_rss_mb() -> float:
    """Peak RSS of this process, in MB.

    `ru_maxrss` is kilobytes on Linux and bytes on macOS — this script is
    expected to be run on both (CI-less local dev on an M3, plus Linux
    containers), so normalize rather than silently reporting a 1024x-off number.
    """
    raw = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return raw / 1024 if sys.platform != "darwin" else raw / (1024 * 1024)


def build_regex_redactor() -> tuple[Callable[[str], str], str]:
    anonymizer = Anonymizer(use_ner=False)
    return anonymizer.anonymize_text, "Anonymizer(use_ner=False) — regex patterns only"


def build_regex_ner_redactor() -> tuple[Optional[Callable[[str], str]], str]:
    """The DEC-006 configuration: regex plus spaCy PERSON detection.

    Returns `(None, reason)` when spaCy or its model is missing. That is not an
    edge case worth glossing over — spaCy is in neither `requirements.txt` nor
    `environment.yml`, so a fresh clone runs the regex-only path, and reporting
    the regex numbers under this label would overstate the real baseline.
    """
    try:
        import spacy  # noqa: F401
    except ImportError:
        return None, "spaCy not installed"

    anonymizer = Anonymizer(use_ner=True)
    # Touch the lazy property: `nlp` flips `use_ner` to False if the model file
    # is missing, so this is the only reliable way to tell the two apart.
    _ = anonymizer.nlp
    if not anonymizer.use_ner or anonymizer.nlp is None:
        return None, "spaCy installed but en_core_web_sm model not downloaded"

    return anonymizer.anonymize_text, "Anonymizer(use_ner=True) — regex + spaCy en_core_web_sm PERSON"


def _redact_spans(text: str, spans: list[tuple[int, int]]) -> str:
    """Replace character spans with the shared placeholder, right to left.

    Right-to-left so earlier offsets stay valid as later ones are rewritten.
    Overlapping spans are merged first — some detectors emit both a coarse and a
    fine entity over the same characters, and replacing them independently would
    produce "[REDACTED][REDACTED]" and inflate the apparent over-redaction.
    """
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
        result = result[:start] + DEFAULT_REDACTION + result[end:]
    return result


def build_openmed_redactor(
    model: Optional[str],
    confidence: float,
) -> tuple[Optional[Callable[[str], str]], str]:
    """Build a redactor backed by `openmed.extract_pii`.

    `extract_pii` is the entry point issue #122 names and the one whose contract
    matches what is being measured: it returns entity spans, leaving redaction
    to the caller, so OpenMed's spans can be rewritten with the *same*
    ``[REDACTED]`` placeholder the current anonymizer uses. `openmed.deidentify`
    would do its own masking with per-label placeholders (`[NAME]`, `[EMAIL]`),
    which would make the two systems incomparable on the negative cases — an
    exact-equality check can't tell a better placeholder from a worse one.

    A probe call is made up front rather than lazily, because the first call is
    what downloads model weights: an environment that can't reach the model host
    should be reported as an unavailable system, not as a system that detected
    no PII anywhere (which would score as a total miss and read as a real result).
    """
    try:
        import openmed
    except ImportError:
        return None, "openmed not installed in this environment"

    version = getattr(openmed, "__version__", "unknown")
    model_name = model or openmed.get_default_pii_model("en")

    kwargs = {"model_name": model_name, "confidence_threshold": confidence}
    probe_text = "Call Dr. Smith at 555-123-4567"
    try:
        probe = openmed.extract_pii(probe_text, **kwargs)
    except Exception as exc:  # noqa: BLE001 — the failure itself is the finding
        return None, (
            f"openmed {version} installed, but extract_pii(model_name={model_name!r}) "
            f"raised {type(exc).__name__}: {exc}"
        )

    if _spans_from_entities(probe, probe_text) is None:
        return None, (
            f"openmed {version}: extract_pii returned an unrecognized shape "
            f"({type(probe).__name__}) — cannot read entity offsets"
        )

    def labels_for(text: str) -> tuple[str, ...]:
        result = openmed.extract_pii(text, **kwargs)
        entities = getattr(result, "entities", None) or []
        return tuple(
            str(getattr(e, "canonical_label", None) or getattr(e, "label", "?"))
            for e in entities
        )

    def redact(text: Optional[str]) -> Optional[str]:
        if not text:
            return text
        result = openmed.extract_pii(text, **kwargs)
        return _redact_spans(text, _spans_from_entities(result, text) or [])

    redact.label_fn = labels_for  # type: ignore[attr-defined]
    return redact, (
        f"openmed {version} via extract_pii(model_name={model_name!r}, "
        f"confidence_threshold={confidence})"
    )


def _spans_from_entities(result, text: str) -> Optional[list[tuple[int, int]]]:
    """Normalize a detector result into character spans.

    Accepts the shapes these libraries actually return: a list of dicts or
    objects with start/end offsets, or a wrapper object holding such a list
    under a conventional attribute. Returns `None` — not `[]` — when the shape
    isn't recognized, so "API returned something we can't read" is never
    mistaken for "no PII found", which would silently score as a total miss.
    """
    if result is None:
        return None

    entities = result
    if not isinstance(entities, (list, tuple)):
        for attr in ("entities", "pii_entities", "results", "matches", "spans"):
            candidate = getattr(entities, attr, None)
            if candidate is None and isinstance(entities, dict):
                candidate = entities.get(attr)
            if isinstance(candidate, (list, tuple)):
                entities = candidate
                break
        else:
            return None

    spans: list[tuple[int, int]] = []
    for ent in entities:
        start = end = None
        for key_start, key_end in (("start", "end"), ("start_char", "end_char"), ("begin", "end")):
            if isinstance(ent, dict):
                if key_start in ent and key_end in ent:
                    start, end = ent[key_start], ent[key_end]
                    break
            else:
                if hasattr(ent, key_start) and hasattr(ent, key_end):
                    start, end = getattr(ent, key_start), getattr(ent, key_end)
                    break
        if start is None or end is None:
            # An entity carrying only the matched string, no offsets: fall back
            # to locating it, which is correct for the first occurrence and is
            # all these short single-entity test strings need.
            word = ent.get("word") if isinstance(ent, dict) else getattr(ent, "word", None)
            if isinstance(word, str) and word:
                idx = text.find(word.replace("##", ""))
                if idx >= 0:
                    spans.append((idx, idx + len(word.replace("##", ""))))
                    continue
            return None
        try:
            spans.append((int(start), int(end)))
        except (TypeError, ValueError):
            return None

    return spans


# --- Scoring --------------------------------------------------------------


def _labels(redact: Callable[[str], str], text: str, passed: bool) -> tuple[str, ...]:
    """Entity labels behind a result, when the system can report them.

    Only fetched for failures. Labels cost a second detector call per case, and
    on a passing case they add nothing a reader would act on.
    """
    label_fn = getattr(redact, "label_fn", None)
    if passed or label_fn is None:
        return ()
    try:
        return label_fn(text)
    except Exception:  # noqa: BLE001 — diagnostics must not fail the run
        return ()


def score_positive(case: PositiveCase, redact: Callable[[str], str]) -> CaseResult:
    output = redact(case.text) or ""
    survived = tuple(s for s in case.must_remove if s in output)
    passed = not survived
    return CaseResult(
        text=case.text,
        category=case.category,
        passed=passed,
        survived=survived,
        output=output,
        detected_labels=_labels(redact, case.text, passed),
    )


def score_negative(case: NegativeCase, redact: Callable[[str], str]) -> CaseResult:
    output = redact(case.text) or ""
    passed = output == case.text
    return CaseResult(
        text=case.text,
        category=case.category,
        passed=passed,
        output=output,
        detected_labels=_labels(redact, case.text, passed),
    )


def measure_latency(redact: Callable[[str], str], texts: list[str]) -> tuple[float, float]:
    """Return (mean_ms, p95_ms) per text, after one warm-up pass.

    The warm-up matters more for OpenMed than for the regex path: the first call
    pays tokenizer construction and (for a transformer) graph setup, which is a
    one-time cost a long-lived process amortizes and a benchmark shouldn't
    attribute to steady-state latency.
    """
    for text in texts[:3]:
        redact(text)

    timings: list[float] = []
    for _ in range(LATENCY_PASSES):
        for text in texts:
            start = time.perf_counter()
            redact(text)
            timings.append((time.perf_counter() - start) * 1000)

    timings.sort()
    p95_index = min(len(timings) - 1, int(round(0.95 * (len(timings) - 1))))
    return statistics.fmean(timings), timings[p95_index]


def run_system(
    name: str,
    builder: Callable[[], tuple[Optional[Callable[[str], str]], str]],
) -> SystemResult:
    rss_before = _peak_rss_mb()
    load_start = time.perf_counter()
    try:
        redact, detail = builder()
    except Exception as exc:  # noqa: BLE001 — a failed build is a reportable result
        return SystemResult(
            name=name,
            available=False,
            unavailable_reason=f"{type(exc).__name__}: {exc}",
        )
    load_seconds = time.perf_counter() - load_start

    if redact is None:
        return SystemResult(name=name, available=False, unavailable_reason=detail)

    result = SystemResult(name=name, available=True, detail=detail, load_seconds=load_seconds)
    result.positives = [score_positive(c, redact) for c in POSITIVE_CASES]
    result.negatives = [score_negative(c, redact) for c in NEGATIVE_CASES]

    texts = [c.text for c in POSITIVE_CASES] + [c.text for c in NEGATIVE_CASES]
    result.mean_ms_per_text, result.p95_ms_per_text = measure_latency(redact, texts)
    result.peak_rss_mb_after = _peak_rss_mb()
    result.rss_delta_mb = result.peak_rss_mb_after - rss_before
    return result


# --- Reporting ------------------------------------------------------------


def _pct(passed: int, total: int) -> str:
    return f"{passed}/{total} ({100.0 * passed / total:.0f}%)" if total else "n/a"


def print_report(results: list[SystemResult]) -> None:
    print()
    print("=" * 78)
    print("OpenMed PII prototype benchmark — issue #122")
    print("=" * 78)
    print(f"Platform : {platform.platform()}")
    print(f"Python   : {platform.python_version()}  ({platform.machine()})")
    print(f"Corpus   : {len(POSITIVE_CASES)} positive, {len(NEGATIVE_CASES)} negative "
          f"across {len(ALL_CATEGORIES)} categories")
    print("Note     : latency/RSS reflect THIS machine. DEC-009's binding")
    print("           constraint is an 8GB M3 — treat as directional elsewhere.")
    print()

    print("-" * 78)
    print("Headline")
    print("-" * 78)
    print(f"{'system':<12} {'PII caught (recall)':<24} {'clinical text intact':<24}")
    for r in results:
        if not r.available:
            print(f"{r.name:<12} SKIPPED — {r.unavailable_reason}")
            continue
        pos_pass = sum(1 for c in r.positives if c.passed)
        neg_pass = sum(1 for c in r.negatives if c.passed)
        print(f"{r.name:<12} {_pct(pos_pass, len(r.positives)):<24} "
              f"{_pct(neg_pass, len(r.negatives)):<24}")
    print()

    print("-" * 78)
    print("Cost")
    print("-" * 78)
    floor = POST_IMPORT_RSS_KB / 1024 if sys.platform != "darwin" else POST_IMPORT_RSS_KB / (1024 * 1024)
    print("Peak RSS is a process-wide high-water mark, so each row includes")
    print("everything earlier rows allocated. Compare `delta`, or isolate a")
    print(f"system with --systems <name>. RSS after imports: {floor:.0f} MB.")
    print()
    print(f"{'system':<12} {'load (s)':>10} {'mean (ms)':>12} {'p95 (ms)':>10} "
          f"{'peak RSS (MB)':>15} {'delta (MB)':>12}")
    for r in results:
        if not r.available:
            continue
        print(f"{r.name:<12} {r.load_seconds:>10.2f} {r.mean_ms_per_text:>12.2f} "
              f"{r.p95_ms_per_text:>10.2f} {r.peak_rss_mb_after:>15.0f} "
              f"{r.rss_delta_mb:>12.0f}")
    print()

    print("-" * 78)
    print("Per-category — positive cases (PII that must be redacted)")
    print("-" * 78)
    available = [r for r in results if r.available]
    header = f"{'category':<16}" + "".join(f"{r.name:>14}" for r in available)
    print(header)
    tables = {r.name: r.category_table() for r in available}
    for cat in ALL_CATEGORIES:
        cells = []
        any_positive = False
        for r in available:
            row = tables[r.name].get(cat, {})
            total = row.get("positive_total", 0)
            if total:
                any_positive = True
                cells.append(f"{row['positive_pass']}/{total}".rjust(14))
            else:
                cells.append("-".rjust(14))
        if any_positive:
            print(f"{cat:<16}" + "".join(cells))
    print()

    print("-" * 78)
    print("Per-category — negative cases (clinical text that must survive)")
    print("-" * 78)
    print(header)
    for cat in ALL_CATEGORIES:
        cells = []
        any_negative = False
        for r in available:
            row = tables[r.name].get(cat, {})
            total = row.get("negative_total", 0)
            if total:
                any_negative = True
                cells.append(f"{row['negative_pass']}/{total}".rjust(14))
            else:
                cells.append("-".rjust(14))
        if any_negative:
            print(f"{cat:<16}" + "".join(cells))
    print()

    for r in available:
        print("-" * 78)
        print(f"{r.name} — failures  ({r.detail})")
        print("-" * 78)
        if not r.leaks and not r.over_redactions:
            print("  none")
        for c in r.leaks:
            print(f"  LEAK      [{c.category}] {c.text!r}")
            print(f"            survived: {', '.join(repr(s) for s in c.survived)}")
            print(f"            output:   {c.output!r}")
            if c.detected_labels:
                print(f"            labels:   {', '.join(c.detected_labels)}")
        for c in r.over_redactions:
            print(f"  OVER-REDACT [{c.category}] {c.text!r}")
            print(f"            output:   {c.output!r}")
            if c.detected_labels:
                print(f"            labels:   {', '.join(c.detected_labels)}")
        print()


def to_json(results: list[SystemResult]) -> dict:
    return {
        "issue": 122,
        "prototype_only": True,
        "platform": {
            "platform": platform.platform(),
            "machine": platform.machine(),
            "python": platform.python_version(),
            "post_import_rss_mb": POST_IMPORT_RSS_KB / 1024
            if sys.platform != "darwin"
            else POST_IMPORT_RSS_KB / (1024 * 1024),
            "note": "Latency and RSS are machine-specific. DEC-009's binding "
                    "constraint is an 8GB M3; numbers from other hardware are "
                    "directional only. peak_rss_mb_after is a process-wide "
                    "high-water mark shared across systems in one run — compare "
                    "rss_delta_mb, or run one system at a time.",
        },
        "corpus": {
            "positive_cases": len(POSITIVE_CASES),
            "negative_cases": len(NEGATIVE_CASES),
            "categories": list(ALL_CATEGORIES),
            "source": "tests/test_anonymization.py (transcribed in eval/prototypes/openmed_pii_cases.py)",
        },
        "systems": [
            {
                **{k: v for k, v in asdict(r).items() if k not in ("positives", "negatives")},
                "positive_pass": sum(1 for c in r.positives if c.passed),
                "negative_pass": sum(1 for c in r.negatives if c.passed),
                "categories": r.category_table(),
                "leaks": [asdict(c) for c in r.leaks],
                "over_redactions": [asdict(c) for c in r.over_redactions],
            }
            for r in results
        ],
    }


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument(
        "--systems",
        default=",".join(DEFAULT_SYSTEMS),
        help=f"comma-separated subset of {DEFAULT_SYSTEMS}",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="OpenMed model id (default: openmed.get_default_pii_model('en'))",
    )
    parser.add_argument(
        "--confidence",
        type=float,
        default=0.5,
        help="OpenMed confidence threshold (default: 0.5, extract_pii's own default)",
    )
    parser.add_argument("--json", dest="json_path", default=None, help="write a JSON report here")
    args = parser.parse_args(argv)

    requested = [s.strip() for s in args.systems.split(",") if s.strip()]
    unknown = [s for s in requested if s not in DEFAULT_SYSTEMS]
    if unknown:
        parser.error(f"unknown system(s): {', '.join(unknown)}")

    builders: dict[str, Callable[[], tuple[Optional[Callable[[str], str]], str]]] = {
        SYSTEM_REGEX: build_regex_redactor,
        SYSTEM_REGEX_NER: build_regex_ner_redactor,
        SYSTEM_OPENMED: lambda: build_openmed_redactor(args.model, args.confidence),
    }

    results = [run_system(name, builders[name]) for name in requested]
    print_report(results)

    if args.json_path:
        Path(args.json_path).write_text(json.dumps(to_json(results), indent=2))
        print(f"JSON report written to {args.json_path}")

    # Exit 0 even with leaks: a leak is a finding to report, not a harness
    # failure. Only a system that could not be built at all is worth a nonzero
    # exit, and only when it was explicitly requested.
    return 0 if any(r.available for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
