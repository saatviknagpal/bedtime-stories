import unittest

from story.checks import fk_grade, run_checks

SIMPLE = "The cat sat on the mat. The cat was warm. The cat went to sleep. " * 40  # 600 words


class TestChecks(unittest.TestCase):
    def test_simple_text_passes(self):
        self.assertLess(fk_grade(SIMPLE), 3.0)
        self.assertEqual(run_checks(SIMPLE, "5-7"), [])

    def test_too_short(self):
        self.assertTrue(any("Length" in f for f in run_checks("The cat slept.", "5-7")))

    def test_complex_text_fails_reading_level(self):
        hard = "Notwithstanding considerable environmental uncertainties, the extraordinarily meticulous investigators systematically documented unprecedented observations. " * 40
        self.assertTrue(any("Reading level" in f for f in run_checks(hard, "8-10")))

    def test_meta_opener_detected(self):
        story = "I can't write that, but here is a cozy story. " + SIMPLE
        self.assertTrue(any("talking to the adult" in f for f in run_checks(story, "5-7")))

    def test_title_opener_allowed(self):
        self.assertEqual(run_checks("**Sleepy Cat**\n\n" + SIMPLE, "5-7"), [])


if __name__ == "__main__":
    unittest.main()
