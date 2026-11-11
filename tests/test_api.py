import json
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

import api
from story.pipeline import Intake
from tests.test_pipeline import GOOD_STORY, verdict

INTAKE = Intake(age_band="5-7", category="animals", brief="A cat naps.")


def events(resp) -> list[dict]:
    return [json.loads(line[6:]) for line in resp.text.splitlines() if line.startswith("data: ")]


def fake_model(prompt, system, on_text=None):
    for word in GOOD_STORY.split(" ")[:3]:
        on_text and on_text(word + " ")
    return GOOD_STORY


class TestApi(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(api.app)

    def test_story_streams_intake_text_draft_done(self):
        verdicts = [verdict()]

        def fake_structured(prompt, schema, system):
            return INTAKE if schema is Intake else verdicts.pop(0)

        with patch("story.pipeline.call_structured", fake_structured), patch("story.pipeline.call_model", fake_model):
            ev = events(self.client.post("/api/story", json={"request": "a cat"}))
        self.assertEqual([e["type"] for e in ev], ["intake", "text", "text", "text", "draft", "done"])
        self.assertEqual(ev[-1]["status"], "passed")
        self.assertTrue(ev[4]["draft"]["passed"])

    def test_rejected_change_reports_not_applied(self):
        failing = [verdict(fail=["calm_ending"])] * 3
        with patch("story.pipeline.call_structured", lambda p, s, system: failing.pop(0)), \
                patch("story.pipeline.call_model", fake_model):
            ev = events(self.client.post("/api/change", json={
                "request": "a cat", "intake": INTAKE.model_dump(), "story": GOOD_STORY, "change": "add a dragon"}))
        self.assertFalse(ev[-1]["applied"])
        self.assertEqual(ev[-1]["request"], "a cat")  # unchanged request comes back

    def test_pipeline_error_is_streamed_not_hung(self):
        def boom(*a, **k):
            raise RuntimeError("down")

        with patch("story.pipeline.call_structured", boom):
            ev = events(self.client.post("/api/story", json={"request": "a cat"}))
        self.assertEqual(ev, [{"type": "error", "message": "down"}])

    def test_input_limits(self):
        self.assertEqual(self.client.post("/api/story", json={"request": ""}).status_code, 422)
        self.assertEqual(self.client.post("/api/story", json={"request": "x" * 501}).status_code, 422)
        self.assertEqual(self.client.post("/api/story", json={"request": "cat", "age_band": "3-4"}).status_code, 422)

    def test_evals_endpoint(self):
        body = self.client.get("/api/evals").json()
        self.assertIn("rows", body)


if __name__ == "__main__":
    unittest.main()
