"""Generates real (non-adversarially-cherry-picked-order) AI outputs for all
30 review-study cases and saves them to a single JSON file, so the packet
builder (eval/build_review_packets.py) never has to re-run generation.

Ordering matches eval.build_review_assignments' 3 rounds, flattened in
round order (round 1 -> examples 1-10, round 2 -> 11-20, round 3 -> 21-30),
matching how the human reviewer groups are being labeled.

Usage:
    python -m eval.generate_review_outputs [--seed N] [--out PATH]
"""

import argparse
import asyncio
import json
from pathlib import Path

from eval.build_review_assignments import DEFAULT_SEED, build_rounds
from eval.fixtures import GENERATION_CASES
from eval.fixtures_review_study import REVIEW_STUDY_CASES
from eval.run import _make_session, run_generation_case

RESULTS_DIR = Path(__file__).parent / "results"


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--out", type=Path, default=RESULTS_DIR / "review_study_outputs.json")
    args = parser.parse_args()

    all_cases = {c.id: c for c in GENERATION_CASES + REVIEW_STUDY_CASES}
    rounds = build_rounds(args.seed)
    ordered_ids = [cid for r in rounds for cid in r]
    assert len(ordered_ids) == 30

    db, engine = await _make_session()
    outputs = []
    try:
        for i, case_id in enumerate(ordered_ids, start=1):
            case = all_cases[case_id]
            print(f"  [{i}/30] generating {case_id}...")
            report = await run_generation_case(db, case, judge_backend=None)
            outputs.append({
                "example_number": i,
                "case_id": case_id,
                "description": case.description,
                "raw_result": report["raw_result"],
            })
    finally:
        await engine.dispose()

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({"seed": args.seed, "examples": outputs}, indent=2))
    print(f"\nWrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
