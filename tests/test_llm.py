import unittest
from types import SimpleNamespace
from unittest.mock import patch

from story import llm


def response(stop_reason, text="A story."):
    return SimpleNamespace(stop_reason=stop_reason, content=[SimpleNamespace(type="text", text=text)], _request_id="req_test",
                           usage=SimpleNamespace(input_tokens=10, output_tokens=5))


class TestCallModel(unittest.TestCase):
    def call(self, resp):
        with patch.object(llm.client.messages, "create", return_value=resp):
            return llm.call_model("hi", system="s")

    def test_end_turn_returns_text(self):
        self.assertEqual(self.call(response("end_turn")), "A story.")

    def test_incomplete_or_unexpected_stop_raises(self):
        for reason in ("max_tokens", "refusal", "pause_turn", "something_new"):
            with self.assertRaises(llm.LLMError, msg=reason):
                self.call(response(reason))

    def test_blank_text_raises(self):
        with self.assertRaises(llm.LLMError):
            self.call(response("end_turn", text="   "))


if __name__ == "__main__":
    unittest.main()
