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


def fake_model(prompt, system, **_):
    return GOOD_STORY


def structured(verdicts):
    def fake(prompt, schema, system):
        return INTAKE if schema is Intake else verdicts.pop(0)
    return fake


class TestApi(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(api.app)
        api._recent.clear()

    def post_story(self, verdicts, request="a cat"):
        with patch("story.pipeline.call_structured", structured(verdicts)), patch("story.pipeline.call_model", fake_model):
            return events(self.client.post("/api/story", json={"request": request}))

    def test_story_streams_stages_then_reviewed_draft(self):
        ev = self.post_story([verdict()])
        self.assertEqual([e.get("stage", e["type"]) for e in ev], ["reading", "intake", "writing", "reviewing", "draft", "done"])
        self.assertEqual(ev[-1]["status"], "passed")
        self.assertEqual(ev[4]["draft"]["story"], GOOD_STORY)
        self.assertFalse(any(e["type"] == "text" for e in ev))  # no unreviewed text is streamed

    def test_unsafe_draft_text_never_sent(self):
        ev = self.post_story([verdict(fail=["safe"])] * 4)
        drafts = [e["draft"] for e in ev if e["type"] == "draft"]
        self.assertEqual(len(drafts), 4)
        self.assertTrue(all(d["story"] is None and d["blocked"] for d in drafts))
        self.assertEqual(ev[-1]["status"], "blocked")
        self.assertNotIn(GOOD_STORY[:40], json.dumps(ev))

    def test_rejected_change_reports_not_applied(self):
        failing = [verdict(fail=["calm_ending"])] * 3
        with patch("story.pipeline.call_structured", lambda p, s, system: failing.pop(0)), \
                patch("story.pipeline.call_model", fake_model):
            ev = events(self.client.post("/api/change", json={
                "request": "a cat", "intake": INTAKE.model_dump(), "story": GOOD_STORY, "change": "add a dragon"}))
        self.assertFalse(ev[-1]["applied"])
        self.assertEqual(ev[-1]["request"], "a cat")

    def test_pipeline_error_is_streamed_not_hung(self):
        def boom(*a, **k):
            raise RuntimeError("down")

        with patch("story.pipeline.call_structured", boom):
            ev = events(self.client.post("/api/story", json={"request": "a cat"}))
        self.assertEqual(ev[-1], {"type": "error", "message": "down"})

    def test_blocked_metadata_does_not_leak_story_text(self):
        unsafe = verdict(fail=["safe"])
        unsafe.safe.reason = "The story says 'blood on the bed'."
        unsafe.revision_notes = ["Remove 'blood on the bed'."]
        ev = self.post_story([unsafe] * 4)
        self.assertNotIn("blood on the bed", json.dumps(ev))

    def test_forged_forwarded_header_ignored_without_trusted_proxy(self):
        with patch.object(api, "PER_IP_LIMIT", 1):
            self.post_story([verdict()])
            resp = self.client.post("/api/story", json={"request": "a cat"}, headers={"X-Forwarded-For": "1.2.3.4"})
        self.assertEqual(resp.status_code, 429)

    def test_busy_reply_does_not_use_quota(self):
        with patch.object(api, "PER_IP_LIMIT", 1), patch.object(api, "_slots", api.threading.BoundedSemaphore(1)) as slots:
            slots.acquire()
            self.assertEqual(self.client.post("/api/story", json={"request": "a cat"}).status_code, 503)
            slots.release()
            ev = self.post_story([verdict()])
        self.assertEqual(ev[-1]["status"], "passed")

    def test_ip_table_has_hard_cap(self):
        with patch.object(api, "MAX_TRACKED_IPS", 2):
            for ip in ("1.1.1.1", "2.2.2.2", "3.3.3.3", "4.4.4.4"):
                api._over_limit(ip)
        self.assertEqual(len(api._recent), 2)
        self.assertIn("4.4.4.4", api._recent)

    def test_per_ip_limit(self):
        with patch.object(api, "PER_IP_LIMIT", 2):
            for _ in range(2):
                self.post_story([verdict()])
            self.assertEqual(self.client.post("/api/story", json={"request": "a cat"}).status_code, 429)

    def test_busy_when_all_slots_taken(self):
        with patch.object(api, "_slots", api.threading.BoundedSemaphore(1)) as slots:
            slots.acquire()
            self.assertEqual(self.client.post("/api/story", json={"request": "a cat"}).status_code, 503)

    def test_input_limits(self):
        self.assertEqual(self.client.post("/api/story", json={"request": ""}).status_code, 422)
        self.assertEqual(self.client.post("/api/story", json={"request": "x" * 501}).status_code, 422)
        self.assertEqual(self.client.post("/api/story", json={"request": "cat", "age_band": "3-4"}).status_code, 422)

    def test_evals_endpoint_has_stable_shape(self):
        body = self.client.get("/api/evals").json()
        self.assertEqual(set(body), {"run", "cost_usd", "rows", "golden", "pairwise"})


if __name__ == "__main__":
    unittest.main()
