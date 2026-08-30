"""Builds the 3-round, 9-reviewer assignment for the human-vs-LLM-judge
review study (30 cases: eval/fixtures.py's 5 adversarial GENERATION_CASES +
eval/fixtures_review_study.py's 25 REVIEW_STUDY_CASES).

Design (see docs/notes/... review-study discussion for the full reasoning):
- 30 cases, 3 raters/case target -> 90 example-ratings needed.
- 9 reviewers x 10 cases each = 90 -> exact match, uniform packet size
  (no per-reviewer fatigue-confound from unequal workloads).
- Built as 3 disjoint "rounds" of 10 cases each; each round is independently
  assigned to 3 different reviewers, so every case gets exactly 3 raters,
  no reviewer ever sees the same case twice, and no case is over- or
  under-covered.
- The case list has authoring-order structure (Tier A/B/C in
  fixtures_review_study.py, adversarial-only in fixtures.py) that would
  bias a naive first-10/next-10/last-10 split toward handing one round
  almost entirely one case type. This does a STRATIFIED shuffle instead:
  shuffle within each tier, then interleave with a running (not
  per-tier-reset) counter so every round lands at exactly 10 cases with a
  proportional mix of tiers.

Usage:
    python -m eval.build_review_assignments [--seed N]

Prints the 3 rounds (10 case ids each) and a reviewer-to-round mapping for
9 reviewers (3 per round). The seed is fixed and disclosed by default so
the split is reproducible — re-running with the same seed reproduces the
same assignment; only change it if you deliberately want a new split
(record the new seed in the paper's Methods section if so).
"""

import argparse
import random

from eval.fixtures import GENERATION_CASES
from eval.fixtures_review_study import REVIEW_STUDY_CASES

# Fixed and disclosed for reproducibility — see module docstring. Not a
# secret; report this value in the paper's Methods section alongside the
# stratification method so the split is independently reproducible.
DEFAULT_SEED = 20260829


def _tier_of_all_cases() -> dict[str, str]:
    """Maps case id -> tier label, matching REVIEW_STUDY_CASES' internal
    tier boundaries (12 routine / 8 edge-probe / 5 stress) plus the 5
    existing adversarial GENERATION_CASES as their own tier."""
    tier_of: dict[str, str] = {}
    for c in GENERATION_CASES:
        tier_of[c.id] = "existing-adversarial"
    for c in REVIEW_STUDY_CASES[:12]:
        tier_of[c.id] = "A-routine"
    for c in REVIEW_STUDY_CASES[12:20]:
        tier_of[c.id] = "B-edge"
    for c in REVIEW_STUDY_CASES[20:25]:
        tier_of[c.id] = "C-stress"
    return tier_of


def build_rounds(seed: int = DEFAULT_SEED) -> list[list[str]]:
    """Returns 3 rounds of 10 case ids each, stratified-shuffled so every
    round gets a proportional mix of tiers and every case appears in
    exactly one round."""
    all_cases = GENERATION_CASES + REVIEW_STUDY_CASES
    tier_of = _tier_of_all_cases()

    rng = random.Random(seed)
    by_tier: dict[str, list[str]] = {}
    for c in all_cases:
        by_tier.setdefault(tier_of[c.id], []).append(c.id)
    for ids in by_tier.values():
        rng.shuffle(ids)

    rounds: list[list[str]] = [[], [], []]
    idx = 0
    # sorted() for a deterministic tier iteration order given a fixed seed
    # (dict insertion order already matches this, but sorted() makes the
    # dependency explicit rather than incidental).
    for tier in sorted(by_tier):
        for case_id in by_tier[tier]:
            rounds[idx % 3].append(case_id)
            idx += 1

    assert all(len(r) == 10 for r in rounds), "expected exactly 10 cases per round"
    assert len({cid for r in rounds for cid in r}) == 30, "expected 30 distinct cases across rounds"
    return rounds


def build_reviewer_assignments(seed: int = DEFAULT_SEED, reviewers_per_round: int = 3) -> dict[str, list[str]]:
    """Returns {reviewer_label: [10 case ids]} for reviewers_per_round x 3
    reviewers total, each reviewer assigned one full round (all reviewers
    in the same round see the identical 10 cases, independently)."""
    rounds = build_rounds(seed)
    assignments: dict[str, list[str]] = {}
    for round_num, case_ids in enumerate(rounds, start=1):
        for slot in range(1, reviewers_per_round + 1):
            label = f"round{round_num}_reviewer{slot}"
            assignments[label] = case_ids
    return assignments


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--reviewers-per-round", type=int, default=3)
    args = parser.parse_args()

    rounds = build_rounds(args.seed)
    tier_of = _tier_of_all_cases()

    print(f"=== Review assignment (seed={args.seed}) ===\n")
    for i, r in enumerate(rounds, start=1):
        print(f"--- Round {i} ({len(r)} cases) ---")
        for cid in r:
            print(f"  {cid}  [{tier_of[cid]}]")
        print()

    assignments = build_reviewer_assignments(args.seed, args.reviewers_per_round)
    total_reviewers = len(assignments)
    total_ratings = sum(len(v) for v in assignments.values())
    print(f"=== {total_reviewers} reviewers, {total_ratings} total example-ratings "
          f"({total_ratings // 30}x coverage across 30 cases) ===")
    for label in assignments:
        print(f"  {label}: round {label.split('_')[0][-1]}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
