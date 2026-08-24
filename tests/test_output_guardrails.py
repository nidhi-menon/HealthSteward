"""Tests for src/agents/output_guardrails.py (DEC-042).

Pins the real failure strings the LLM judge found in eval/judge.py's first
live runs (eval/results/9f22c89-*.json, eval/results/065d5e7-*.json) as
permanent regression cases, not just synthetic examples — same discipline
DEC-040/DEC-041 applied to their own found-bug regression tests.
"""

from src.agents.output_guardrails import (
    _presupposes_missing_referral,
    _presupposes_missing_test,
    apply_output_guardrails,
)


class TestPresupposesMissingTest:
    def test_flags_real_found_case_blood_sugar_test(self):
        q = "What are the results of my most recent blood sugar test, and are there any concerns or adjustments needed?"
        assert _presupposes_missing_test(q, known_lab_names=set()) is True

    def test_flags_real_found_case_allergy_testing(self):
        q = "What are the results of my recent allergy testing, and are there any changes to my treatment plan based on those results?"
        assert _presupposes_missing_test(q, known_lab_names=set()) is True

    def test_flags_real_found_case_recent_lab_trends(self):
        q = "What are the current thyroid-stimulating hormone (TSH) levels, and how do they compare to previous results?"
        assert _presupposes_missing_test(q, known_lab_names=set()) is True

    def test_does_not_flag_when_real_lab_named(self):
        q = "What were the results of the TSH test ordered on 2026-07-15, and are they available?"
        assert _presupposes_missing_test(q, known_lab_names={"tsh"}) is False

    def test_does_not_flag_open_question(self):
        q = "Are there any tests or labs I should be getting related to my condition?"
        assert _presupposes_missing_test(q, known_lab_names=set()) is False

    def test_does_not_flag_unrelated_question(self):
        q = "What lifestyle changes can I make to better manage my Type 2 Diabetes Mellitus?"
        assert _presupposes_missing_test(q, known_lab_names=set()) is False


class TestPresupposesMissingReferral:
    def test_flags_real_found_case_endocrinology_followup(self):
        q = "Is there a need for a follow-up appointment with Endocrinology in the near future?"
        specialty = _presupposes_missing_referral(
            q, known_specialty_names={"Endocrinology", "Dermatology"}, referred_specialties=set()
        )
        assert specialty == "Endocrinology"

    def test_does_not_flag_when_referral_on_file(self):
        q = "Is there a need for a follow-up appointment with Endocrinology in the near future?"
        specialty = _presupposes_missing_referral(
            q, known_specialty_names={"Endocrinology"}, referred_specialties={"endocrinology"}
        )
        assert specialty is None

    def test_does_not_flag_cross_specialty_interaction_question(self):
        """The permitted case score_scope was fixed to allow — no relationship
        keyword (specialist/referral/follow-up with) appears in an interaction
        question, so this should never trigger regardless of referral state."""
        q = "Are there any potential interactions between Metformin and Clobetasol Cream that I should be aware of?"
        specialty = _presupposes_missing_referral(
            q, known_specialty_names={"Dermatology"}, referred_specialties=set()
        )
        assert specialty is None

    def test_does_not_flag_question_with_no_specialty_mention(self):
        q = "Are there any pending referrals or tests that need to be scheduled?"
        specialty = _presupposes_missing_referral(
            q, known_specialty_names={"Dermatology"}, referred_specialties=set()
        )
        assert specialty is None


class TestApplyOutputGuardrails:
    def test_strips_flagged_questions_and_keeps_others(self):
        questions = {
            "Lab Results & Monitoring": [
                "What are the results of my most recent blood sugar test?",
                "What were the results of the TSH test ordered on 2026-07-15?",
            ],
            "Follow-up Planning": [
                "Is there a need for a follow-up appointment with Endocrinology in the near future?",
            ],
        }
        filtered, events = apply_output_guardrails(
            questions,
            known_lab_names={"tsh"},
            known_specialty_names={"Endocrinology"},
            referred_specialties=set(),
        )
        assert filtered == {
            "Lab Results & Monitoring": ["What were the results of the TSH test ordered on 2026-07-15?"],
        }
        assert len(events) == 2
        assert {e["reason"] for e in events} == {"presupposed_test", "presupposed_referral"}

    def test_drops_category_that_becomes_fully_empty(self):
        questions = {"Follow-up Planning": ["Is there a need for a follow-up appointment with Endocrinology?"]}
        filtered, events = apply_output_guardrails(
            questions, known_lab_names=set(), known_specialty_names={"Endocrinology"}, referred_specialties=set()
        )
        assert filtered == {}
        assert len(events) == 1

    def test_leaves_clean_output_untouched(self):
        questions = {
            "Condition Management": ["What are the current blood sugar targets for my Type 2 Diabetes Mellitus?"],
        }
        filtered, events = apply_output_guardrails(
            questions, known_lab_names=set(), known_specialty_names=set(), referred_specialties=set()
        )
        assert filtered == questions
        assert events == []
