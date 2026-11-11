import unittest
from unittest.mock import patch

from pydantic import ValidationError

from story.llm import LLMError
from story.pipeline import CHECKS, Intake, Verdict, request_change, tell_story

GOOD_STORY = "Sleepy Cat\n\n" + "The cat sat on the mat. The cat was warm. The cat went to sleep. " * 40


def verdict(fail=(), score=5, notes=()):
    checks = {c: {"reason": f"{c} reason", "passed": c not in fail} for c in CHECKS}
    return Verdict(**checks, engagement=score, soothing=5, care=5, revision_notes=list(notes))


def run(verdicts, category="animals", story=GOOD_STORY, model_error_at=None):
    """Run tell_story with fake model calls. `verdicts` is consumed one per judge call."""
    verdicts = list(verdicts)
    calls = {"model": 0, "prompts": []}

    def fake_structured(prompt, schema, system):
        if schema is Intake:
            return Intake(age_band="5-7", category=category, brief="A cat naps.")
        item = verdicts.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    def fake_model(prompt, system):
        calls["model"] += 1
        calls["prompts"].append(prompt)
        if calls["model"] == model_error_at:
            raise LLMError("boom")
        return story

    with patch("story.pipeline.call_structured", fake_structured), patch("story.pipeline.call_model", fake_model):
        return tell_story("a cat"), calls


class TestPipeline(unittest.TestCase):
    def test_passes_first_round(self):
        result, calls = run([verdict()])
        self.assertEqual(result.status, "passed")
        self.assertEqual(len(result.drafts), 1)
        self.assertEqual(calls["model"], 1)

    def test_quality_failure_is_flagged_not_blocked(self):
        result, _ = run([verdict(fail=["calm_ending"])] * 3)
        self.assertEqual(result.status, "flagged")
        self.assertEqual(len(result.drafts), 3)

    def test_unsafe_everywhere_is_blocked_after_gentle_retry(self):
        result, calls = run([verdict(fail=["safe"])] * 4)
        self.assertEqual(result.status, "blocked")
        self.assertEqual(calls["model"], 4)  # draft + 2 revisions + 1 extra-gentle retry

    def test_safe_retry_rescues(self):
        result, _ = run([verdict(fail=["safe"])] * 3 + [verdict()])
        self.assertEqual(result.status, "passed")

    def test_best_prefers_safe_draft_over_fewer_failures(self):
        drafts = [verdict(fail=["safe"]), verdict(fail=["calm_ending", "clear_arc"]), verdict(fail=["safe"])]
        result, _ = run(drafts)
        self.assertFalse(result.best.blocked)
        self.assertEqual(result.status, "flagged")

    def test_failed_check_reason_reaches_reviser_without_judge_notes(self):
        _, calls = run([verdict(fail=["calm_ending"], notes=[]), verdict()])
        self.assertIn("calm_ending reason", calls["prompts"][1])

    def test_low_score_triggers_revision(self):
        result, calls = run([verdict(score=3), verdict()])
        self.assertEqual(calls["model"], 2)
        self.assertIn("engagement scored 3/5", calls["prompts"][1])
        self.assertEqual(result.status, "passed")

    def test_comfort_uses_care_not_engagement(self):
        result, _ = run([verdict(score=2)], category="comfort")
        self.assertEqual(result.status, "passed")
        self.assertNotIn("engagement", result.best.scores)

    def test_api_error_mid_loop_keeps_earlier_draft(self):
        result, _ = run([verdict(fail=["calm_ending"])], model_error_at=2)
        self.assertEqual(len(result.drafts), 1)
        self.assertEqual(result.error, "boom")
        self.assertEqual(result.status, "flagged")

    def test_error_before_any_draft_raises(self):
        with self.assertRaises(LLMError):
            run([], model_error_at=1)

    def test_change_request_reaches_reviser_and_is_judged(self):
        first, _ = run([verdict()])
        verdicts = [verdict()]
        prompts = []

        def fake_model(prompt, system):
            prompts.append(prompt)
            return GOOD_STORY

        with patch("story.pipeline.call_structured", lambda p, s, system: verdicts.pop(0)), patch("story.pipeline.call_model", fake_model):
            changed = request_change(first, "add a dog named Rex")
        self.assertIn("add a dog named Rex", prompts[0])
        self.assertEqual(changed.status, "passed")
        self.assertEqual(changed.request, first.request)

    def test_out_of_range_score_rejected(self):
        with self.assertRaises(ValidationError):
            verdict(score=9)


if __name__ == "__main__":
    unittest.main()
