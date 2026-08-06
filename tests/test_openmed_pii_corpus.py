"""Drift guard for eval/prototypes/openmed_pii_cases.py (issue #124).

The corpus is transcribed from tests/test_anonymization.py rather than
imported from it (see PR #124 discussion) so nothing here enforces
case-for-case parity. This just pins the known counts so an editor who adds
or removes a PII test case in test_anonymization.py without touching the
corpus gets a loud, cheap signal instead of a silent drift.

If this test starts failing because you intentionally changed
test_anonymization.py's PII cases, update eval/prototypes/openmed_pii_cases.py
to match and bump the counts below.
"""

from eval.prototypes.openmed_pii_cases import NEGATIVE_CASES, POSITIVE_CASES


def test_positive_case_count_pinned():
    assert len(POSITIVE_CASES) == 67


def test_negative_case_count_pinned():
    assert len(NEGATIVE_CASES) == 24
