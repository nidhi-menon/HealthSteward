"""Ordering for free-text date columns.

Some date columns (e.g. `Vitals.measured_date`) hold whatever string the AVS
parser matched, such as "12/03/2025". SQL `ORDER BY` on those is lexicographic,
so "01/05/2026" sorts before "12/03/2025". Parse before ordering.
"""

from datetime import date, datetime
from typing import Callable, Optional, Sequence, TypeVar

T = TypeVar("T")

_FORMATS = ("%Y-%m-%d", "%m/%d/%Y", "%m-%d-%Y", "%B %d, %Y", "%b %d, %Y", "%B %d %Y")


def parse_date_flexible(value: Optional[str]) -> Optional[date]:
    """Parse a date string in any of the formats the app stores, else None."""
    if not value:
        return None
    text = value.strip().rstrip(",")
    for fmt in _FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def sort_by_date(
    rows: Sequence[T],
    get_date: Callable[[T], Optional[str]],
    *,
    reverse: bool = False,
    drop_undated: bool = False,
) -> list[T]:
    """Sort rows by a free-text date field, oldest first (newest first if `reverse`).

    Rows whose date is missing or unparseable can't be placed in time. They go
    last by default; with `drop_undated` they are omitted. Rows with equal
    dates keep their incoming order.
    """
    dated = [(d, r) for r in rows if (d := parse_date_flexible(get_date(r))) is not None]
    undated = [r for r in rows if parse_date_flexible(get_date(r)) is None]
    dated.sort(key=lambda pair: pair[0], reverse=reverse)
    ordered = [r for _, r in dated]
    return ordered if drop_undated else ordered + undated
