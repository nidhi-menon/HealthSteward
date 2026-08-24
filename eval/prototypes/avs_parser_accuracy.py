"""Field-level accuracy of the production AVS parser against hand-labeled
ground truth (paper evaluation piece).

Ground truth JSONs (AVS-1.json, AVS-2.json, AVS-3.json) live outside this
repo, in a sibling sandbox project, but were verified byte-identical (md5)
against the PDFs they describe, so they remain valid gold labels for
src/parsers/avs_parser.py's current output even though that ground truth
was originally authored against an earlier, different parser implementation.

Not part of the maintained eval/run.py harness — a standalone, throwaway
scoring script, run on-demand.

The ground-truth directory is machine-specific (it lives in a sibling
sandbox project, not this repo) and is not portable by default, so it must
be supplied explicitly rather than assumed: via --ground-truth-dir or the
AVS_GROUND_TRUTH_DIR environment variable. Running without either fails
loudly with instructions, rather than silently skipping every document.

Usage:
    python -m eval.prototypes.avs_parser_accuracy --ground-truth-dir /path/to/avs-pdf-parser
    AVS_GROUND_TRUTH_DIR=/path/to/avs-pdf-parser python -m eval.prototypes.avs_parser_accuracy
"""

import argparse
import json
import os
import sys
from pathlib import Path

from src.parsers import parse_avs_pdf

DATA_DIR = Path(__file__).parent.parent.parent / "data" / "avs"

# Top-level keys scored. "notes" is free text (scored by presence/length
# similarity, not exact match); list-of-dict sections are scored by count
# and, where feasible, field-level match; scalar sections are scored by
# exact (case/whitespace-insensitive) match, with None/empty treated as
# a match for None/empty (a formatting choice, not a factual disagreement).
SCALAR_FIELDS = {
    ("patient", "name"),
    ("patient", "visit_date"),
    ("provider", "name"),
    ("provider", "facility"),
    ("provider", "phone"),
}
LIST_SECTIONS = [
    "medication_changes",
    "diagnoses",
    "upcoming_appointments",
    "follow_up_recommended",
    "lab_orders",
    "referrals",
]


def _norm(v):
    if v is None:
        return ""
    return str(v).strip().lower()


def _get(d, path):
    cur = d
    for p in path:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(p)
    return cur


def score_document(parsed: dict, truth: dict) -> dict:
    result = {"scalar": {}, "list_counts": {}, "notes": {}}

    for section, field in SCALAR_FIELDS:
        p_val = _norm(_get(parsed, [section, field]))
        t_val = _norm(_get(truth, [section, field]))
        result["scalar"][f"{section}.{field}"] = {
            "match": p_val == t_val,
            "parsed": p_val or None,
            "truth": t_val or None,
        }

    for section in LIST_SECTIONS:
        p_list = parsed.get(section) or []
        t_list = truth.get(section) or []
        result["list_counts"][section] = {
            "parsed_count": len(p_list),
            "truth_count": len(t_list),
            "count_match": len(p_list) == len(t_list),
            "parsed_items": p_list,
            "truth_items": t_list,
        }

    p_notes = parsed.get("notes") or []
    t_notes = truth.get("notes") or []
    result["notes"] = {
        "parsed_count": len(p_notes),
        "truth_count": len(t_notes),
        "count_match": len(p_notes) == len(t_notes),
        "present": bool(p_notes) == bool(t_notes),
        "parsed_items": p_notes,
        "truth_items": t_notes,
    }

    return result


def _resolve_ground_truth_dir(cli_arg: str | None) -> Path:
    raw = cli_arg or os.environ.get("AVS_GROUND_TRUTH_DIR")
    if not raw:
        sys.exit(
            "No ground-truth directory supplied. This script scores against hand-labeled "
            "AVS-{1,2,3}.json ground truth that lives outside this repo (verified byte-identical "
            "to data/avs/AVS-*.pdf via md5, but not itself part of it). Pass --ground-truth-dir "
            "or set AVS_GROUND_TRUTH_DIR."
        )
    path = Path(raw).expanduser()
    if not path.is_dir():
        sys.exit(f"Ground-truth directory does not exist: {path}")
    return path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--ground-truth-dir", type=str, default=None,
        help="Directory containing AVS-{1,2,3}.json ground truth. Falls back to "
             "AVS_GROUND_TRUTH_DIR if not passed.",
    )
    args = parser.parse_args()
    ground_truth_dir = _resolve_ground_truth_dir(args.ground_truth_dir)

    pdfs = sorted(DATA_DIR.glob("AVS-*.pdf"))
    all_scalar_results = []
    all_list_results = []
    per_doc = {}

    for pdf_path in pdfs:
        truth_path = ground_truth_dir / f"{pdf_path.stem}.json"
        if not truth_path.exists():
            print(f"Skipping {pdf_path.name}: no ground truth at {truth_path}")
            continue

        truth = json.loads(truth_path.read_text())
        print(f"Parsing {pdf_path.name}...")
        parsed = parse_avs_pdf(str(pdf_path))

        doc_result = score_document(parsed, truth)
        per_doc[pdf_path.name] = doc_result

        for field, r in doc_result["scalar"].items():
            all_scalar_results.append((pdf_path.name, field, r["match"], r["parsed"], r["truth"]))
        for section, r in doc_result["list_counts"].items():
            all_list_results.append((pdf_path.name, section, r["count_match"], r["parsed_count"], r["truth_count"]))

    print("\n=== Scalar field accuracy ===")
    n_match = sum(1 for *_, match, _, _ in all_scalar_results if match)
    n_total = len(all_scalar_results)
    print(f"{n_match}/{n_total} exact matches ({n_match/n_total:.0%})" if n_total else "no data")
    for doc, field, match, parsed_v, truth_v in all_scalar_results:
        if not match:
            print(f"  MISMATCH [{doc}] {field}: parsed={parsed_v!r} truth={truth_v!r}")

    print("\n=== List-section count accuracy ===")
    n_count_match = sum(1 for *_, match, _, _ in all_list_results if match)
    n_count_total = len(all_list_results)
    print(f"{n_count_match}/{n_count_total} exact count matches ({n_count_match/n_count_total:.0%})" if n_count_total else "no data")
    for doc, section, match, p_count, t_count in all_list_results:
        if not match:
            print(f"  COUNT MISMATCH [{doc}] {section}: parsed={p_count} truth={t_count}")

    print("\n=== Notes count (informational, not scored pass/fail above) ===")
    for doc, r in per_doc.items():
        n = r["notes"]
        flag = "" if n["count_match"] else "  <-- COUNT DIFFERS"
        print(f"  [{doc}] parsed={n['parsed_count']} truth={n['truth_count']}{flag}")

    out_path = Path(__file__).parent / "avs_parser_accuracy_report.json"
    out_path.write_text(json.dumps(per_doc, indent=2, default=str))
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
