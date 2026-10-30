"""Tests for free-text date parsing and ordering (src/utils/dates.py)."""

from datetime import date

import pytest

from src.utils.dates import parse_date_flexible, sort_by_date


@pytest.mark.parametrize("raw,expected", [
    ("2026-01-05", date(2026, 1, 5)),
    ("01/05/2026", date(2026, 1, 5)),
    ("01-05-2026", date(2026, 1, 5)),
    ("January 5, 2026", date(2026, 1, 5)),
    ("Jan 5, 2026", date(2026, 1, 5)),
    ("January 5 2026", date(2026, 1, 5)),
    ("  01/05/2026,  ", date(2026, 1, 5)),
])
def test_parses_every_stored_format(raw, expected):
    assert parse_date_flexible(raw) == expected


@pytest.mark.parametrize("raw", [None, "", "   ", "not a date", "13/45/2026", "2026"])
def test_unparseable_returns_none(raw):
    assert parse_date_flexible(raw) is None


def test_orders_chronologically_across_a_year_boundary():
    # Lexicographic order would put "01/05/2026" before "12/03/2025".
    rows = ["01/05/2026", "12/03/2025", "06/15/2025"]
    assert sort_by_date(rows, lambda r: r) == ["06/15/2025", "12/03/2025", "01/05/2026"]
    assert sort_by_date(rows, lambda r: r, reverse=True) == ["01/05/2026", "12/03/2025", "06/15/2025"]


def test_mixed_formats_sort_together():
    rows = ["2026-02-01", "01/15/2026", "March 3, 2025"]
    assert sort_by_date(rows, lambda r: r) == ["March 3, 2025", "01/15/2026", "2026-02-01"]


def test_undated_rows_go_last_in_either_direction():
    rows = ["01/05/2026", None, "garbage", "12/03/2025"]
    assert sort_by_date(rows, lambda r: r) == ["12/03/2025", "01/05/2026", None, "garbage"]
    assert sort_by_date(rows, lambda r: r, reverse=True) == ["01/05/2026", "12/03/2025", None, "garbage"]


def test_drop_undated_omits_them():
    rows = ["01/05/2026", None, "garbage", "12/03/2025"]
    assert sort_by_date(rows, lambda r: r, drop_undated=True) == ["12/03/2025", "01/05/2026"]


def test_equal_dates_keep_incoming_order():
    rows = [("a", "01/05/2026"), ("b", "01/05/2026"), ("c", "01/05/2026")]
    assert [k for k, _ in sort_by_date(rows, lambda r: r[1])] == ["a", "b", "c"]
    assert [k for k, _ in sort_by_date(rows, lambda r: r[1], reverse=True)] == ["a", "b", "c"]
