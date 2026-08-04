"""API routes for runtime diagnostics — currently the visit-prep fallback rate (issue #30).

DEC-013's agentic tool-use loop is fallback-not-hard-failure by design: if it
can't converge within `agent_max_turns`, or the backend emits a malformed tool
call, `prepare_visit()` quietly downgrades to a single-shot call. That's the
right behavior for the user, but it also means a backend degrading at tool use
(an Ollama or Claude version change breaking tool-calling reliability) produces
no user-visible symptom and no error — the app just gets quietly worse.

This module is the read side of that: every `prepare_visit()` run records how it
was actually produced in `ConversationLog.extra_data["run_diagnostics"]`
(DEC-026), and this endpoint aggregates the last N of them.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.data.database import get_db
from src.data.models import ConversationLog
from src.models.schemas import VisitPrepFallbackRateResponse

router = APIRouter(prefix="/api/diagnostics", tags=["Diagnostics"])


@router.get("/visit-prep-fallback", response_model=VisitPrepFallbackRateResponse)
async def get_visit_prep_fallback_rate(
    limit: int = Query(
        50,
        ge=1,
        le=1000,
        description="How many of the most recent visit-prep runs to aggregate.",
    ),
    db: AsyncSession = Depends(get_db),
) -> VisitPrepFallbackRateResponse:
    """Report how often recent visit-prep runs fell back off the agentic loop.

    Rolling window over the most recent runs rather than an all-time rate: the
    question worth answering is "is tool use working *now*", and an all-time
    average would take a long time to move after a backend started failing.
    """
    # Imported here rather than at module scope for the same reason
    # src/api/visits.py defers its VisitPrepAgent import — the agents package
    # pulls in the LLM SDKs, which this module otherwise has no need for.
    from src.agents.visit_prep import FALLBACK_BACKEND_UNAVAILABLE

    # Only rows carrying run_diagnostics are visit-prep runs — assistant rows
    # written before this landed (and any future non-visit-prep agent) have no
    # such key and are skipped rather than counted as successes. Filtered in SQL
    # via json_extract so `limit` means "the last N visit-prep runs" rather than
    # "whatever survives filtering the last N assistant rows." json_extract is
    # SQLite/MySQL syntax, not portable to Postgres — fine here, since SQLite is
    # the project's database, but it is the line to change if that ever moves.
    result = await db.execute(
        select(ConversationLog)
        .where(
            ConversationLog.role == "assistant",
            func.json_extract(ConversationLog.extra_data, "$.run_diagnostics").is_not(None),
        )
        .order_by(ConversationLog.timestamp.desc(), ConversationLog.id.desc())
        .limit(limit)
    )
    rows = list(result.scalars().all())

    agentic_runs = 0
    fallback_runs = 0
    hard_failure_runs = 0
    reasons: dict[str, int] = {}

    for row in rows:
        diagnostics = (row.extra_data or {}).get("run_diagnostics") or {}
        if diagnostics.get("agentic_path"):
            agentic_runs += 1
            continue

        fallback_runs += 1
        reason = diagnostics.get("fallback_reason") or "unspecified"
        reasons[reason] = reasons.get(reason, 0) + 1

        # A hard failure is counted as a fallback too — it is one, just the
        # worst kind — so agentic_runs + fallback_runs always equals
        # runs_considered and the rate stays a straight proportion.
        if reason == FALLBACK_BACKEND_UNAVAILABLE:
            hard_failure_runs += 1

        # The agentic failure that preceded a hard failure still counts toward
        # its own reason, otherwise a backend that breaks tool use on its way
        # down would look like a plain outage.
        prior = diagnostics.get("prior_agentic_failure")
        if prior:
            reasons[prior] = reasons.get(prior, 0) + 1

    runs_considered = len(rows)
    timestamps = [row.timestamp for row in rows]

    return VisitPrepFallbackRateResponse(
        runs_considered=runs_considered,
        agentic_runs=agentic_runs,
        fallback_runs=fallback_runs,
        hard_failure_runs=hard_failure_runs,
        fallback_rate=(fallback_runs / runs_considered) if runs_considered else 0.0,
        reasons=reasons,
        oldest_run_at=min(timestamps) if timestamps else None,
        newest_run_at=max(timestamps) if timestamps else None,
    )
