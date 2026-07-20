"""Stage 1 (rules-based filter) unit-style checks — issue #29 build-order item #3.

Pure assertions against src.utils.context_selection.ContextSelector.stage1_rules_filter,
no LLM involved, no DB needed — SimpleNamespace stand-ins are enough since
stage1_rules_filter only reads a handful of attributes off its inputs.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from types import SimpleNamespace

from src.utils.context_selection import ContextSelector


@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str = ""


def _doctor(id: str, specialty=None, clinic=None, exclude=False):
    return SimpleNamespace(id=id, specialty=specialty, clinic=clinic, exclude_from_prep_context=exclude)


def _appt(id: str, doctor, days_ago: int, purpose: str = ""):
    return SimpleNamespace(
        id=id, doctor=doctor, purpose=purpose,
        scheduled_date=datetime(2026, 1, 1) - timedelta(days=days_ago),
    )


def _filter():
    return ContextSelector().stage1_rules_filter


def check_same_doctor_visit_included() -> CheckResult:
    target_doctor = _doctor("d1", specialty="Endocrinology")
    target = SimpleNamespace(doctor=target_doctor)
    same_doctor_visit = _appt("a1", target_doctor, days_ago=30)
    result = _filter()(target, [same_doctor_visit])
    passed = same_doctor_visit in result
    return CheckResult("same_doctor_visit_included", passed, f"result ids: {[a.id for a in result]}")


def check_same_doctor_only_most_recent_kept() -> CheckResult:
    target_doctor = _doctor("d1", specialty="Endocrinology")
    target = SimpleNamespace(doctor=target_doctor)
    recent = _appt("recent", target_doctor, days_ago=10)
    older = _appt("older", target_doctor, days_ago=100)
    result = _filter()(target, [older, recent])
    passed = recent in result and older not in result
    return CheckResult("same_doctor_only_most_recent_kept", passed, f"result ids: {[a.id for a in result]}")


def check_pcp_included_regardless_of_specialty() -> CheckResult:
    target_doctor = _doctor("d1", specialty="Dermatology")
    target = SimpleNamespace(doctor=target_doctor)
    pcp_doctor = _doctor("d2", specialty="Primary Care")
    pcp_visit = _appt("a2", pcp_doctor, days_ago=30)
    result = _filter()(target, [pcp_visit])
    passed = pcp_visit in result
    return CheckResult("pcp_included_regardless_of_specialty", passed, f"result ids: {[a.id for a in result]}")


def check_unrelated_specialty_excluded() -> CheckResult:
    target_doctor = _doctor("d1", specialty="Dermatology")
    target = SimpleNamespace(doctor=target_doctor)
    unrelated_doctor = _doctor("d3", specialty="Cardiology")
    unrelated_visit = _appt("a3", unrelated_doctor, days_ago=30)
    result = _filter()(target, [unrelated_visit])
    passed = unrelated_visit not in result
    return CheckResult("unrelated_specialty_excluded", passed, f"result ids: {[a.id for a in result]}")


def check_related_specialty_included() -> CheckResult:
    target_doctor = _doctor("d1", specialty="Endocrinology")
    target = SimpleNamespace(doctor=target_doctor)
    related_doctor = _doctor("d4", specialty="Cardiology")  # related per SPECIALTY_MAPPING
    related_visit = _appt("a4", related_doctor, days_ago=30)
    result = _filter()(target, [related_visit])
    passed = related_visit in result
    return CheckResult("related_specialty_included", passed, f"result ids: {[a.id for a in result]}")


def check_excluded_doctor_flag_respected() -> CheckResult:
    target_doctor = _doctor("d1", specialty="Endocrinology")
    target = SimpleNamespace(doctor=target_doctor)
    excluded_doctor = _doctor("d5", specialty="Cardiology", exclude=True)
    excluded_visit = _appt("a5", excluded_doctor, days_ago=30)
    result = _filter()(target, [excluded_visit])
    passed = excluded_visit not in result
    return CheckResult("excluded_doctor_flag_respected", passed, f"result ids: {[a.id for a in result]}")


def check_blank_specialty_clinic_fallback_gap() -> CheckResult:
    """Documents issue #72's finding: Stage 1 uses target_doctor.specialty raw,
    with no clinic-name-inference fallback (unlike generation's prompt/tagging
    path, which does infer from clinic name). A target doctor with a blank
    specialty field but a clinic name implying one silently loses related-
    specialty visits from Phase 1, even though generation "knows" the true
    specialty via _infer_specialty_from_clinic.

    This check currently asserts the CURRENT (buggy) behavior — it documents
    the gap rather than papering over it. Flip `passed`'s expected value
    once #72 fixes Stage 1 to use the same specialty-inference fallback.
    """
    # Blank specialty field, clinic name implies Endocrinology (matches
    # visit_prep.py's _infer_specialty_from_clinic keyword list).
    target_doctor = _doctor("d1", specialty=None, clinic="Sutter Endocrinology - San Francisco")
    target = SimpleNamespace(doctor=target_doctor)
    related_doctor = _doctor("d6", specialty="Cardiology")  # related to Endocrinology per SPECIALTY_MAPPING
    related_visit = _appt("a6", related_doctor, days_ago=30)
    result = _filter()(target, [related_visit])

    # Current, buggy behavior: the related visit is dropped, because Stage 1
    # never resolves target_doctor's specialty via clinic-name inference.
    currently_dropped = related_visit not in result
    return CheckResult(
        "blank_specialty_clinic_fallback_gap (documents #72, expected to fail once fixed)",
        currently_dropped,
        f"related visit currently {'dropped' if currently_dropped else 'kept'} — "
        f"result ids: {[a.id for a in result]}",
    )


ALL_CHECKS = [
    check_same_doctor_visit_included,
    check_same_doctor_only_most_recent_kept,
    check_pcp_included_regardless_of_specialty,
    check_unrelated_specialty_excluded,
    check_related_specialty_included,
    check_excluded_doctor_flag_respected,
    check_blank_specialty_clinic_fallback_gap,
]


def run_all() -> list[CheckResult]:
    return [check() for check in ALL_CHECKS]
