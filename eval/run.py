"""CLI entrypoint for the v1 visit-prep eval harness (issue #29).

Deterministic-only, run on-demand — no CI integration, per the eval plan
in docs/tdd.html. Runs the real pipeline (real DB rows, real VisitPrepAgent,
real ContextSelector) against whichever LLM backend is configured via
Settings, at temperature=0.0 so repeated runs are comparable.

Usage:
    python -m eval.run

Writes a timestamped JSON report to eval/results/ and prints a summary,
diffed against the most recent prior result file if one exists.
"""

import asyncio
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from eval import retrieval_stage1, scorers
from eval.db import build_case
from eval.fixtures import GENERATION_CASES
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


async def run_generation_case(db: AsyncSession, case) -> dict:
    appointment = await build_case(db, case)
    await db.commit()

    agent = VisitPrepAgent(db)
    result = await agent.prepare_visit(appointment, temperature=EVAL_TEMPERATURE)

    target_specialty = appointment.doctor.specialty or _infer_specialty_from_clinic(appointment.doctor.clinic)
    med_specialty_map = agent._build_med_specialty_map(appointment.profile)
    off_scope = scorers.off_scope_medications(med_specialty_map, target_specialty)
    entities = scorers.known_entities(case)
    tool_calls = agent.last_tool_calls or []
    context_result = agent.last_context_selection
    phase1_dates = [v.scheduled_date for v in (context_result.selected_visits if context_result else [])]

    return {
        "case_id": case.id,
        "description": case.description,
        "raw_result": result,
        "format": scorers.score_format(result),
        "groundedness": scorers.score_groundedness(result, entities),
        "scope": scorers.score_scope(result, off_scope),
        "tool_result_scope": scorers.score_tool_result_scope(tool_calls, off_scope),
        "tool_call_necessity": scorers.score_tool_call_necessity(case, tool_calls),
        "retrieval_redundancy": scorers.score_retrieval_redundancy(phase1_dates, tool_calls),
        "tool_calls_made": [c["name"] for c in tool_calls],
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
    print("=== Stage 1 retrieval checks (no LLM) ===")
    stage1_results = retrieval_stage1.run_all()
    stage1_failures = 0
    for r in stage1_results:
        status = "PASS" if r.passed else "FAIL"
        print(f"  [{status}] {r.name}: {r.detail}")
        if not r.passed:
            stage1_failures += 1
    print(f"Stage 1: {len(stage1_results) - stage1_failures}/{len(stage1_results)} passed\n")

    print(f"=== Generation cases (LLM provider: {get_settings().llm_provider}, temperature={EVAL_TEMPERATURE}) ===")
    db, engine = await _make_session()
    try:
        case_reports = []
        for case in GENERATION_CASES:
            print(f"  running {case.id}...")
            try:
                report = await asyncio.wait_for(
                    run_generation_case(db, case), timeout=CASE_TIMEOUT_SECONDS
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
            case_reports.append(report)
            if not report["timed_out"]:
                fmt = report["format"]
                scope = report["scope"]
                grounded = report["groundedness"]["grounded_rate"]
                print(
                    f"    format_valid={fmt['valid']} questions={fmt['question_count']} "
                    f"grounded_rate={grounded} scope_violations={scope['violation_count']} "
                    f"tools_called={report['tool_calls_made']}"
                )
    finally:
        await db.close()
        await engine.dispose()

    current = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "git_sha": _git_sha(),
        "llm_provider": get_settings().llm_provider,
        "temperature": EVAL_TEMPERATURE,
        "stage1": [{"name": r.name, "passed": r.passed, "detail": r.detail} for r in stage1_results],
        "cases": case_reports,
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
