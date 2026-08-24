"""CLI entrypoint for the v1 visit-prep eval harness (issue #29).

Deterministic-only, run on-demand — no CI integration, per the eval plan
in docs/tdd.html. Runs the real pipeline (real DB rows, real VisitPrepAgent,
real ContextSelector) against whichever LLM backend is configured via
Settings, at temperature=0.0 so repeated runs are comparable.

Usage:
    python -m eval.run
    python -m eval.run --trials 5   # repeat each case N times for a more
                                     # statistically meaningful tool-call
                                     # convergence rate (see score_tool_call_
                                     # convergence in eval/scorers.py)

Writes a timestamped JSON report to eval/results/ and prints a summary,
diffed against the most recent prior result file if one exists.
"""

import argparse
import asyncio
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from eval import retrieval_stage1, scorers
from eval.db import build_case
from eval.fixtures import GENERATION_CASES
from eval.judge import score_factual_groundedness
from src.agents.llm_backend import ClaudeBackend
from src.agents.visit_prep import VisitPrepAgent, _infer_specialty_from_clinic
from src.config import get_settings
from src.data.models import Base

RESULTS_DIR = Path(__file__).parent / "results"
EVAL_TEMPERATURE = 0.0  # fixed sampling temperature — see eval/__init__.py
# Per-case wall-clock guard, independent of the backend's own total-call
# timeout (llm_backend._TOTAL_CALL_TIMEOUT_SECONDS). Belt-and-suspenders:
# the agentic loop can make up to agent_max_turns calls, so even with that
# per-call fix in place, a case that repeatedly hits (but doesn't exceed)
# the per-call ceiling across several turns could still run a long time.
# A case timing out here is itself a valid, reportable result — not
# swallowed, surfaced as case_reports' "timed_out" field.
CASE_TIMEOUT_SECONDS = 900.0


def _git_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=Path(__file__).parent.parent,
            stderr=subprocess.DEVNULL,
        ).decode().strip()
    except Exception:
        return "unknown"


async def _make_session() -> tuple[AsyncSession, AsyncEngine]:
    """Returns (session, engine) — the caller must dispose the engine when
    done, not just close the session. An undisposed AsyncEngine holds
    aiosqlite's connection pool open, which previously left the process
    hanging for minutes in asyncio shutdown/cleanup after main() had
    already finished and written its results — the actual work was done,
    nothing was still running, it was purely leaked-connection teardown.
    """
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False, future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async_session = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    return async_session(), engine


async def run_generation_case(db: AsyncSession, case, judge_backend: ClaudeBackend | None = None) -> dict:
    appointment = await build_case(db, case)
    await db.commit()

    agent = VisitPrepAgent(db)
    start = time.perf_counter()
    result = await agent.prepare_visit(appointment, temperature=EVAL_TEMPERATURE)
    duration_s = time.perf_counter() - start

    target_specialty = appointment.doctor.specialty or _infer_specialty_from_clinic(appointment.doctor.clinic)
    med_specialty_map = agent._build_med_specialty_map(appointment.profile)
    off_scope = scorers.off_scope_medications(med_specialty_map, target_specialty)
    entities = scorers.known_entities(case)
    tool_calls = agent.last_tool_calls or []
    context_result = agent.last_context_selection
    phase1_dates = [v.scheduled_date for v in (context_result.selected_visits if context_result else [])]
    min_questions = scorers.expected_min_questions(case)

    report = {
        "case_id": case.id,
        "description": case.description,
        "duration_s": duration_s,
        "raw_result": result,
        "format": scorers.score_format(result, min_questions=min_questions),
        "groundedness": scorers.score_groundedness(result, entities),
        "scope": scorers.score_scope(result, off_scope),
        "tool_result_scope": scorers.score_tool_result_scope(tool_calls, off_scope),
        "tool_call_necessity": scorers.score_tool_call_necessity(case, tool_calls),
        "retrieval_redundancy": scorers.score_retrieval_redundancy(phase1_dates, tool_calls),
        "tool_calls_made": [c["name"] for c in tool_calls],
        "convergence": scorers.score_tool_call_convergence(result),
    }

    if judge_backend is not None:
        try:
            report["factual_groundedness"] = await score_factual_groundedness(case, result, judge_backend)
        except ValueError as e:
            # A judge call failing (including after score_factual_groundedness's
            # own retries) shouldn't abort the whole multi-minute run over one
            # case — recorded as a valid, reportable failure for this case's
            # judge score, same posture as CASE_TIMEOUT_SECONDS's timeout
            # handling above: surfaced, not swallowed, but not fatal either.
            print(f"    [judge] FAILED for {case.id}: {e}")
            report["factual_groundedness_error"] = str(e)

    return report


def _model_name_for_provider(settings) -> str:
    """Mirrors VisitPrepAgent._model_name_for_provider — duplicated here (not
    imported) because that method is an instance method requiring a live
    agent/db session, and the report header needs this before any case runs.
    """
    if settings.llm_provider == "ollama":
        return settings.ollama_model
    if settings.llm_provider == "custom":
        return settings.custom_llm_model or "custom"
    return settings.anthropic_model


def _summarize_convergence(case_reports: list[dict]) -> dict[str, Any]:
    """Aggregate per-run convergence results into a rate + failure-reason
    breakdown, for item #1 of the tool-calling reliability workstream:
    is small-model tool-calling actually reliable, not just gracefully
    degraded. `runs` excludes timed-out attempts — a timeout is a harness-
    level failure (CASE_TIMEOUT_SECONDS), not a tool-calling result.
    """
    runs = [r["convergence"] for r in case_reports if not r.get("timed_out") and "convergence" in r]
    converged = sum(1 for c in runs if c["converged"])
    reasons: dict[str, int] = {}
    for c in runs:
        if not c["converged"]:
            reason = c["fallback_reason"] or "unknown"
            reasons[reason] = reasons.get(reason, 0) + 1
    return {
        "total_runs": len(runs),
        "converged": converged,
        "convergence_rate": (converged / len(runs)) if runs else None,
        "fallback_reason_counts": reasons,
    }


def _summarize_latency(case_reports: list[dict]) -> dict[str, Any]:
    """Wall-clock latency for successful (non-timed-out) generation runs.
    Timed-out cases are excluded — CASE_TIMEOUT_SECONDS caps them at a fixed
    ceiling that isn't a meaningful latency sample.
    """
    durations = sorted(r["duration_s"] for r in case_reports if not r.get("timed_out") and "duration_s" in r)
    n = len(durations)
    if n == 0:
        return {"n": 0, "mean_s": None, "median_s": None, "p95_s": None, "min_s": None, "max_s": None}
    return {
        "n": n,
        "mean_s": sum(durations) / n,
        "median_s": durations[n // 2],
        "p95_s": durations[min(n - 1, int(0.95 * n))],
        "min_s": durations[0],
        "max_s": durations[-1],
    }


def _summarize_judge(case_reports: list[dict]) -> dict[str, Any]:
    """Aggregate LLM-judge factual-groundedness results across cases, plus
    total judge cost/latency for the run (cheapest-version tracking per
    DEC-042 — no dashboard, just the raw numbers in the report JSON)."""
    fg_reports = [r["factual_groundedness"] for r in case_reports if "factual_groundedness" in r]
    n_failed = sum(1 for r in case_reports if "factual_groundedness_error" in r)
    if not fg_reports:
        return {"n_cases": 0, "n_failed": n_failed}

    all_claims = [c for fg in fg_reports for c in fg["claims"]]
    scored = [c for c in all_claims if c.get("verdict") in ("grounded", "unsupported")]
    unsupported = [c for c in scored if c["verdict"] == "unsupported"]

    return {
        "n_cases": len(fg_reports),
        "n_failed": n_failed,
        "total_claims": len(all_claims),
        "scored_claims": len(scored),
        "unsupported_claims": len(unsupported),
        "unsupported_rate": (len(unsupported) / len(scored)) if scored else None,
        "total_input_tokens": sum(fg["input_tokens"] or 0 for fg in fg_reports),
        "total_output_tokens": sum(fg["output_tokens"] or 0 for fg in fg_reports),
        "total_duration_s": sum(fg["duration_s"] for fg in fg_reports),
    }


def _find_previous_result() -> Path | None:
    if not RESULTS_DIR.exists():
        return None
    files = sorted(RESULTS_DIR.glob("*.json"))
    return files[-1] if files else None


def _diff_summary(previous: dict, current: dict) -> list[str]:
    lines = []
    prev_by_id = {c["case_id"]: c for c in previous.get("cases", [])}
    for c in current["cases"]:
        prev = prev_by_id.get(c["case_id"])
        if not prev:
            lines.append(f"  {c['case_id']}: new case, no prior result")
            continue
        prev_valid = prev["format"]["valid"]
        cur_valid = c["format"]["valid"]
        if prev_valid != cur_valid:
            lines.append(f"  {c['case_id']}: format valid {prev_valid} -> {cur_valid}")
        prev_grounded = prev["groundedness"]["grounded_rate"]
        cur_grounded = c["groundedness"]["grounded_rate"]
        if prev_grounded != cur_grounded:
            lines.append(f"  {c['case_id']}: grounded_rate {prev_grounded} -> {cur_grounded}")
        prev_violations = prev["scope"]["violation_count"]
        cur_violations = c["scope"]["violation_count"]
        if prev_violations != cur_violations:
            lines.append(f"  {c['case_id']}: scope violations {prev_violations} -> {cur_violations}")
    return lines


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--trials", type=int, default=1,
        help="Repeat each generation case this many times (default 1). Tool-call "
             "convergence is a reliability signal, not a per-case correctness check "
             "(EVAL_TEMPERATURE=0.0 means repeats of the same case are not guaranteed "
             "identical on a real backend) — more trials narrows the convergence_rate "
             "confidence interval at the cost of wall-clock time.",
    )
    parser.add_argument(
        "--judge", action="store_true",
        help="Also run the LLM-judge factual-groundedness check (eval/judge.py) on each "
             "generation case, using settings.anthropic_judge_model. Off by default — it "
             "adds a real Claude API call (cost + latency) per case, on top of whatever "
             "backend generation itself uses. Requires ANTHROPIC_API_KEY to be set "
             "regardless of the configured llm_provider.",
    )
    args = parser.parse_args()

    print("=== Stage 1 retrieval checks (no LLM) ===")
    stage1_results = retrieval_stage1.run_all()
    stage1_failures = 0
    for r in stage1_results:
        status = "PASS" if r.passed else "FAIL"
        print(f"  [{status}] {r.name}: {r.detail}")
        if not r.passed:
            stage1_failures += 1
    print(f"Stage 1: {len(stage1_results) - stage1_failures}/{len(stage1_results)} passed\n")

    settings = get_settings()
    model_name = _model_name_for_provider(settings)

    judge_backend = None
    if args.judge:
        if not settings.anthropic_api_key:
            print("ERROR: --judge requires ANTHROPIC_API_KEY to be set.", file=sys.stderr)
            return 1
        judge_backend = ClaudeBackend(settings, model=settings.anthropic_judge_model)
        print(f"=== LLM judge enabled: {settings.anthropic_judge_model} ===")

    print(
        f"=== Generation cases (LLM provider: {settings.llm_provider}, model: {model_name}, "
        f"temperature={EVAL_TEMPERATURE}, trials={args.trials}) ==="
    )
    db, engine = await _make_session()
    try:
        case_reports = []
        for case in GENERATION_CASES:
            for trial in range(args.trials):
                trial_label = f"{case.id}" if args.trials == 1 else f"{case.id} (trial {trial + 1}/{args.trials})"
                print(f"  running {trial_label}...")
                try:
                    report = await asyncio.wait_for(
                        run_generation_case(db, case, judge_backend=judge_backend), timeout=CASE_TIMEOUT_SECONDS
                    )
                    report["timed_out"] = False
                except asyncio.TimeoutError:
                    print(f"    TIMED OUT after {CASE_TIMEOUT_SECONDS}s — recorded as a failure, continuing")
                    await db.rollback()  # reset session state before the next case's build_case
                    report = {
                        "case_id": case.id,
                        "description": case.description,
                        "timed_out": True,
                        "format": {"valid": False, "question_count": 0, "issues": ["case timed out"]},
                    }
                report["trial"] = trial
                case_reports.append(report)
                if not report["timed_out"]:
                    fmt = report["format"]
                    scope = report["scope"]
                    grounded = report["groundedness"]["grounded_rate"]
                    conv = report["convergence"]
                    print(
                        f"    format_valid={fmt['valid']} questions={fmt['question_count']} "
                        f"grounded_rate={grounded} scope_violations={scope['violation_count']} "
                        f"tools_called={report['tool_calls_made']} "
                        f"converged={conv['converged']} fallback_reason={conv['fallback_reason']} "
                        f"duration_s={report['duration_s']:.2f}"
                    )
                    if "factual_groundedness" in report:
                        fg = report["factual_groundedness"]
                        print(
                            f"    [judge] unsupported_rate={fg['unsupported_rate']} "
                            f"claims={len(fg['claims'])} judge_duration_s={fg['duration_s']:.2f} "
                            f"judge_tokens_in={fg['input_tokens']} judge_tokens_out={fg['output_tokens']}"
                        )
    finally:
        await db.close()
        await engine.dispose()

    convergence_summary = _summarize_convergence(case_reports)
    print(
        f"\n=== Tool-call convergence: {convergence_summary['converged']}/{convergence_summary['total_runs']} "
        f"({convergence_summary['convergence_rate']}) ==="
    )
    if convergence_summary["fallback_reason_counts"]:
        for reason, count in sorted(convergence_summary["fallback_reason_counts"].items()):
            print(f"  {reason}: {count}")

    latency_summary = _summarize_latency(case_reports)
    if latency_summary["n"]:
        print(
            f"\n=== Latency (n={latency_summary['n']}): "
            f"mean={latency_summary['mean_s']:.2f}s median={latency_summary['median_s']:.2f}s "
            f"p95={latency_summary['p95_s']:.2f}s min={latency_summary['min_s']:.2f}s "
            f"max={latency_summary['max_s']:.2f}s ==="
        )

    judge_summary = _summarize_judge(case_reports)
    if judge_summary["n_cases"]:
        print(
            f"\n=== LLM-judge factual groundedness (n={judge_summary['scored_claims']} scored claims "
            f"across {judge_summary['n_cases']} cases): unsupported_rate={judge_summary['unsupported_rate']} "
            f"({judge_summary['unsupported_claims']}/{judge_summary['scored_claims']}) ==="
        )
        if judge_summary["n_failed"]:
            print(f"  WARNING: {judge_summary['n_failed']} case(s) had a judge failure — excluded from the rate above")
        print(
            f"  judge cost/latency: {judge_summary['total_input_tokens']} input tokens, "
            f"{judge_summary['total_output_tokens']} output tokens, "
            f"{judge_summary['total_duration_s']:.2f}s total ==="
        )

    current = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "git_sha": _git_sha(),
        "llm_provider": settings.llm_provider,
        "model": model_name,
        "judge_model": settings.anthropic_judge_model if args.judge else None,
        "temperature": EVAL_TEMPERATURE,
        "trials": args.trials,
        "stage1": [{"name": r.name, "passed": r.passed, "detail": r.detail} for r in stage1_results],
        "cases": case_reports,
        "convergence_summary": convergence_summary,
        "latency_summary": latency_summary,
        "judge_summary": judge_summary,
    }

    RESULTS_DIR.mkdir(exist_ok=True)
    previous_path = _find_previous_result()
    out_path = RESULTS_DIR / f"{current['git_sha']}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    out_path.write_text(json.dumps(current, indent=2, default=str))
    print(f"\nWrote {out_path}")

    if previous_path:
        previous = json.loads(previous_path.read_text())
        diff_lines = _diff_summary(previous, current)
        print(f"\n=== Diff vs {previous_path.name} ===")
        if diff_lines:
            for line in diff_lines:
                print(line)
        else:
            print("  no change in tracked metrics")
    else:
        print("\nNo prior result to diff against — this is the baseline run.")

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
