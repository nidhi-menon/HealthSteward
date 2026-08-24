"""Wall-clock latency timing for AVS PDF parsing (paper evaluation piece).

Not part of the maintained eval/run.py harness — a standalone, throwaway
timing script against the real sample PDFs in data/avs/, run on-demand.

Usage:
    python -m eval.prototypes.avs_parse_latency
"""

import json
import time
from pathlib import Path

from src.parsers import parse_avs_pdf

DATA_DIR = Path(__file__).parent.parent.parent / "data" / "avs"


def main() -> None:
    pdfs = sorted(DATA_DIR.glob("AVS-*.pdf"))
    if not pdfs:
        print(f"No AVS-*.pdf files found in {DATA_DIR}")
        return

    durations = []
    for pdf_path in pdfs:
        print(f"Parsing {pdf_path.name}...")
        start = time.perf_counter()
        try:
            result = parse_avs_pdf(str(pdf_path))
            duration_s = time.perf_counter() - start
            durations.append(duration_s)
            print(f"  duration_s={duration_s:.2f} keys={list(result.keys())}")
        except Exception as exc:
            duration_s = time.perf_counter() - start
            print(f"  FAILED after {duration_s:.2f}s: {exc}")

    if durations:
        n = len(durations)
        durations_sorted = sorted(durations)
        summary = {
            "n": n,
            "mean_s": sum(durations) / n,
            "median_s": durations_sorted[n // 2],
            "min_s": durations_sorted[0],
            "max_s": durations_sorted[-1],
        }
        print(f"\n=== AVS parse latency (n={n}) ===")
        print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
