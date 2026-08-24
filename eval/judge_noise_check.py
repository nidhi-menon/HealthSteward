"""Ad hoc analysis script (not part of the regular eval CLI): isolates judge
verdict noise from generation noise, per DEC-042.

Generation at temperature=0.0 on the local default model is confirmed
deterministic (eval/run.py's --trials repeats matched exactly on
groundedness/scope in earlier runs), but the judge model
(settings.anthropic_judge_model) cannot be pinned to temperature=0.0 (see
DEC-042 / the temperature-deprecation fix in llm_backend.py) — so its
verdicts can vary run-to-run on identical input text. Re-running generation
under two different prompts (baseline vs. v7) and judging once each
conflates "did the prompt change help" with "is this just judge noise."

This script instead re-judges the SAME two already-generated, fixed sets of
output (loaded from existing eval/results/*.json report files, not
regenerated) multiple times each, to get a noise distribution for the
judge's own unsupported-claim rate under each prompt version, so the two
distributions can be compared directly.

Usage:
    python -m eval.judge_noise_check <baseline_results.json> <fixed_prompt_results.json> [--repeats N]
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

from eval.fixtures import GENERATION_CASES
from eval.judge import score_factual_groundedness
from src.agents.llm_backend import ClaudeBackend
from src.config import get_settings

RESULTS_DIR = Path(__file__).parent / "results"


async def _judge_pass(cases_and_results: list[tuple], judge_backend: ClaudeBackend) -> dict:
    """One full pass: judge all 5 fixed outputs once each, pool the claims,
    return the aggregate unsupported_rate for this pass."""
    all_claims = []
    for case, raw_result in cases_and_results:
        report = await score_factual_groundedness(case, raw_result, judge_backend)
        all_claims.extend(report["claims"])

    scored = [c for c in all_claims if c.get("verdict") in ("grounded", "unsupported")]
    unsupported = [c for c in scored if c["verdict"] == "unsupported"]
    return {
        "unsupported_rate": (len(unsupported) / len(scored)) if scored else None,
        "scored_claims": len(scored),
        "unsupported_claims": len(unsupported),
    }


def _load_cases_and_results(report_path: Path) -> list[tuple]:
    data = json.loads(report_path.read_text())
    cases_by_id = {c.id: c for c in GENERATION_CASES}
    out = []
    for case_report in data["cases"]:
        case = cases_by_id[case_report["case_id"]]
        out.append((case, case_report["raw_result"]))
    return out


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("baseline_report", type=Path)
    parser.add_argument("fixed_prompt_report", type=Path)
    parser.add_argument("--repeats", type=int, default=5)
    args = parser.parse_args()

    settings = get_settings()
    if not settings.anthropic_api_key:
        print("ERROR: ANTHROPIC_API_KEY not set.", file=sys.stderr)
        return 1
    judge_backend = ClaudeBackend(settings, model=settings.anthropic_judge_model)

    baseline_cases = _load_cases_and_results(args.baseline_report)
    fixed_cases = _load_cases_and_results(args.fixed_prompt_report)

    results = {"baseline": [], "fixed_prompt": []}
    for label, cases_and_results in [("baseline", baseline_cases), ("fixed_prompt", fixed_cases)]:
        print(f"=== Re-judging '{label}' output {args.repeats}x (judge: {settings.anthropic_judge_model}) ===")
        for i in range(args.repeats):
            pass_result = await _judge_pass(cases_and_results, judge_backend)
            print(f"  pass {i + 1}/{args.repeats}: unsupported_rate={pass_result['unsupported_rate']} "
                  f"({pass_result['unsupported_claims']}/{pass_result['scored_claims']})")
            results[label].append(pass_result)

    print("\n=== Summary ===")
    for label in ("baseline", "fixed_prompt"):
        rates = [r["unsupported_rate"] for r in results[label] if r["unsupported_rate"] is not None]
        print(f"{label}: rates={rates}")
        if rates:
            print(f"  min={min(rates):.3f} max={max(rates):.3f} mean={sum(rates) / len(rates):.3f} "
                  f"range={max(rates) - min(rates):.3f}")

    out_path = RESULTS_DIR / "judge_noise_check.json"
    out_path.write_text(json.dumps(results, indent=2))
    print(f"\nWrote {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
