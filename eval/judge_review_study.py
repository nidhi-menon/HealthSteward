"""LLM-judge + deterministic scoring for the 30-case human review study, at
the SAME granularity the human packets use (eval/build_review_packets.py):
category-level Accuracy (4-way), example-level Relevance/Clarity/Usefulness
(3-way), and a deterministic missing-category completeness check — so the
judge's output and the human ratings can be directly compared once the
human packets come back.

Three independent pieces, each documented separately because they trust
different things:

1. Category-level Accuracy rollup: NO NEW LLM CALL. Reuses
   eval.judge.score_factual_groundedness's existing claim-level
   grounded/unsupported/not_applicable verdicts (already validated,
   noise-isolated — see docs/notes/PROMPT_CHANGELOG.md) and rolls them up
   per category with a FIXED, DISCLOSED rule (not a second LLM judgment),
   so the rollup is deterministic and auditable against the claim data.

2. Relevance/Clarity/Usefulness: a NEW judge call, using the identical
   rubric wording the human packet shows reviewers, so a human's pick and
   the judge's pick are answering the literal same question. This is an
   unvalidated instrument as of this writing — no noise-isolation pass has
   been run on it yet (see docs/notes/PROMPT_CHANGELOG.md's own convention
   that a new/changed judge prompt should be validated before being
   trusted) — treat these verdicts as provisional until that's done.

3. Missing-category completeness: NO LLM CALL AT ALL. Deterministic check
   of the case's structured fixture data (does the patient have data that
   would make a category eligible per visit_prep.py's own generation
   rules) against which categories the output actually included.
"""

import argparse
import asyncio
import json
import re
import time
from pathlib import Path
from typing import Any

from eval.fixtures import GENERATION_CASES, EvalCase
from eval.fixtures_review_study import REVIEW_STUDY_CASES
from eval.judge import score_factual_groundedness
from src.agents.llm_backend import ClaudeBackend
from src.config import get_settings

RESULTS_DIR = Path(__file__).parent / "results"

KNOWN_CATEGORIES = [
    "Condition Management", "Medication Review", "Lab Results & Monitoring",
    "Lifestyle & Prevention", "Follow-up Planning",
]
CONTEXT_SUMMARY_LABEL = "Context Summary"

# ── 1. Category-level Accuracy rollup (deterministic, no LLM call) ─────────

QUALITY_JUDGE_PROMPT_VERSION = "v1-2026-08-29"

_QUALITY_JUDGE_SYSTEM_PROMPT = """You are an independent reviewer for an AI health-coordination tool. \
You will be shown a patient's actual medical record data and the "visit \
preparation" output (categorized questions and a short context summary) \
the tool generated for that patient's upcoming appointment.

Rate the output on exactly the same three questions a human reviewer is \
asked, using exactly the same wording and options they see. Answer each \
independently — do not let one dimension's rating influence another.

1. Relevance — "Are the questions relevant to this patient's actual \
conditions, medications, and appointment purpose?" Options: "Relevant", \
"Partially Relevant", "Not Relevant".
2. Clarity — "Are the questions clearly phrased and understandable to a \
patient, not overly clinical or confusing?" Options: "Clear", "Partially \
Clear", "Confusing".
3. Usefulness — "Would bringing these questions to the appointment \
genuinely help the conversation with the doctor?" Options: "Useful", \
"Partially Useful", "Not Useful".

For each, give a one-to-two sentence reasoning.

Respond with ONLY a JSON object (no markdown fences, no other text) matching \
this shape:
{
  "relevance": "Relevant" | "Partially Relevant" | "Not Relevant",
  "relevance_reasoning": "<why>",
  "clarity": "Clear" | "Partially Clear" | "Confusing",
  "clarity_reasoning": "<why>",
  "usefulness": "Useful" | "Partially Useful" | "Not Useful",
  "usefulness_reasoning": "<why>"
}"""


def _claim_category_key(claim: dict[str, Any]) -> str:
    """Maps a judge claim's free-text `category` field onto our fixed set —
    the judge is prompted with category names drawn from the generated
    output's own keys, but a context-summary claim doesn't have a real
    category, so anything not in KNOWN_CATEGORIES is treated as belonging
    to the context summary bucket."""
    cat = claim.get("category", "")
    return cat if cat in KNOWN_CATEGORIES else CONTEXT_SUMMARY_LABEL


def rollup_category_accuracy(claims: list[dict[str, Any]], categories_present: list[str]) -> dict[str, str]:
    """Fixed, disclosed rollup rule (not a second LLM judgment) — see module
    docstring point 1. For each category actually present in the output
    (plus the context summary), bucket its scored claims and apply:
      - N/A: zero grounded/unsupported claims (only not_applicable, or none)
      - Fully Supported: zero unsupported among scored claims
      - Unsupported: unsupported claims are >= half of scored claims,
        OR any unsupported claim is a named-authority/specialty-management
        claim (the two claim types eval/judge.py's own rubric always
        treats as unsupported, never a borderline case) — treated as
        "severe" per the human rubric's definition, detected here via the
        judge's own reasoning text since the schema doesn't carry a
        separate severity flag.
      - Partially Supported: otherwise (some, but a minority, unsupported,
        and none flagged severe)
    """
    rows = categories_present + [CONTEXT_SUMMARY_LABEL]
    by_cat: dict[str, list[dict]] = {r: [] for r in rows}
    for c in claims:
        key = _claim_category_key(c)
        if key in by_cat:
            by_cat[key].append(c)

    _SEVERE_MARKERS = ("named authority", "guideline", "specialty-management", "typically managed by")

    result: dict[str, str] = {}
    for row, row_claims in by_cat.items():
        scored = [c for c in row_claims if c.get("verdict") in ("grounded", "unsupported")]
        if not scored:
            result[row] = "N/A"
            continue
        unsupported = [c for c in scored if c["verdict"] == "unsupported"]
        if not unsupported:
            result[row] = "Fully Supported"
            continue
        is_severe = any(
            any(marker in (u.get("reasoning", "") + u.get("claim_text", "")).lower() for marker in _SEVERE_MARKERS)
            for u in unsupported
        )
        if is_severe or len(unsupported) / len(scored) >= 0.5:
            result[row] = "Unsupported"
        else:
            result[row] = "Partially Supported"
    return result


# ── 2. Relevance/Clarity/Usefulness (new LLM call) ──────────────────────────

def _parse_json_response(text: str) -> dict[str, Any]:
    stripped = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    return json.loads(stripped)


async def score_quality(case: EvalCase, raw_result: dict[str, Any], judge_backend: ClaudeBackend) -> dict[str, Any]:
    from eval.judge import _case_context_text, _questions_text  # reuse existing renderers

    user_message = (
        f"Patient's actual record:\n{_case_context_text(case)}\n\n"
        f"Generated visit-prep questions:\n{_questions_text(raw_result)}"
    )

    # Same bounded-retry posture as eval.judge.score_factual_groundedness —
    # the judge backend occasionally returns an empty/non-JSON response
    # unrelated to prompt content (observed in practice on this same judge
    # model/endpoint), so retry the API call itself before giving up.
    _MAX_ATTEMPTS = 3
    start = time.perf_counter()
    last_error: Exception | None = None
    turn = None
    for _ in range(_MAX_ATTEMPTS):
        turn = await judge_backend.call(
            messages=[{"role": "user", "content": user_message}],
            system=_QUALITY_JUDGE_SYSTEM_PROMPT,
            temperature=0.0,
        )
        try:
            parsed = _parse_json_response(turn.text or "")
            last_error = None
            break
        except json.JSONDecodeError as e:
            last_error = e
    if last_error is not None:
        raise ValueError(f"Quality judge response was not valid JSON: {last_error}\n\nRaw response:\n{turn.text}") from last_error

    duration_s = time.perf_counter() - start
    return {
        "prompt_version": QUALITY_JUDGE_PROMPT_VERSION,
        **parsed,
        "input_tokens": turn.input_tokens,
        "output_tokens": turn.output_tokens,
        "duration_s": duration_s,
    }


# ── 3. Missing-category completeness (deterministic, no LLM call) ──────────

def missing_categories(case: EvalCase, categories_present: list[str]) -> list[str]:
    """Category eligibility per visit_prep.py's own generation rules — a
    category "needs real patient data behind it": Condition Management
    needs an active condition, Medication Review needs a medication, Lab
    Results & Monitoring needs a lab order. Lifestyle & Prevention is
    explicitly the exception (fine with just a condition, per the prompt),
    so it's folded into the condition check. Follow-up Planning is
    deliberately excluded — the prompt allows a generic follow-up question
    "either way" even with no specific referral/follow-up data, so its
    absence is never flagged as a completeness gap by this deterministic
    check.
    """
    missing = []
    has_active_condition = any(c.status == "active" for c in case.conditions)
    if has_active_condition and "Condition Management" not in categories_present:
        missing.append("Condition Management")
    if case.medications and "Medication Review" not in categories_present:
        missing.append("Medication Review")
    if case.lab_orders and "Lab Results & Monitoring" not in categories_present:
        missing.append("Lab Results & Monitoring")
    if has_active_condition and "Lifestyle & Prevention" not in categories_present:
        missing.append("Lifestyle & Prevention")
    return missing


# ── Driver ───────────────────────────────────────────────────────────────

def categories_present_in(raw_result: dict) -> list[str]:
    questions = raw_result.get("questions") or {}
    return [c for c in KNOWN_CATEGORIES if questions.get(c)]


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--in", dest="in_path", type=Path, default=RESULTS_DIR / "review_study_outputs.json")
    parser.add_argument("--out", type=Path, default=RESULTS_DIR / "judge_review_study_results.json")
    args = parser.parse_args()

    settings = get_settings()
    if not settings.anthropic_api_key:
        print("ERROR: ANTHROPIC_API_KEY not set.")
        return 1
    judge_backend = ClaudeBackend(settings, model=settings.anthropic_judge_model)

    cases_by_id = {c.id: c for c in GENERATION_CASES + REVIEW_STUDY_CASES}
    data = json.loads(args.in_path.read_text())
    examples = data["examples"]
    assert len(examples) == 30

    def _save(results: list[dict]) -> None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps({"seed": data.get("seed"), "results": results}, indent=2))

    results = []
    failures = []
    for ex in examples:
        case = cases_by_id[ex["case_id"]]
        raw_result = ex["raw_result"]
        n = ex["example_number"]
        print(f"  [{n}/30] judging {ex['case_id']}...")

        try:
            groundedness = await score_factual_groundedness(case, raw_result, judge_backend)
            cats_present = categories_present_in(raw_result)
            accuracy_rollup = rollup_category_accuracy(groundedness["claims"], cats_present)
            quality = await score_quality(case, raw_result, judge_backend)
            missing = missing_categories(case, cats_present)

            results.append({
                "example_number": n,
                "case_id": ex["case_id"],
                "categories_present": cats_present,
                "accuracy_rollup": accuracy_rollup,
                "quality": quality,
                "missing_categories": missing,
                "groundedness_unsupported_rate": groundedness["unsupported_rate"],
                "groundedness_claims": groundedness["claims"],
            })
        except ValueError as e:
            # A judge failure on one case (after its own internal retries)
            # shouldn't abort the whole 30-case, ~30-call run and lose
            # every case already scored — same posture as eval/run.py's
            # --judge path. Recorded as a real, reportable gap, not
            # silently skipped: surfaced in the summary and left for a
            # manual re-run of just this case (`--case-id`, not yet
            # implemented — re-run the whole script to retry it for now).
            print(f"    [FAILED] {ex['case_id']}: {e}")
            failures.append({"example_number": n, "case_id": ex["case_id"], "error": str(e)})

        # Incremental save after every case — a later failure shouldn't
        # cost the judge calls already made for earlier cases.
        _save(results)

    _save(results)
    print(f"\nWrote {args.out} ({len(results)}/30 succeeded, {len(failures)} failed)")
    if failures:
        print("Failed cases (re-run the script to retry — it will redo ALL 30 "
              "since there's no per-case skip yet, not just the failures):")
        for f in failures:
            print(f"  #{f['example_number']} {f['case_id']}: {f['error'][:200]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
