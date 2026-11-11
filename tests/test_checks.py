import unittest

from story.checks import fk_grade, run_checks, split_title, syllables

SIMPLE = "The cat sat on the mat. The cat was warm. The cat went to sleep. " * 40  # 600 words


class TestSyllables(unittest.TestCase):
    def test_known_counts(self):
        expected = {"the": 1, "cake": 1, "little": 2, "table": 2, "people": 2, "gentle": 2,
                    "jumped": 1, "played": 1, "wanted": 2, "landed": 2, "butterfly": 3, "don't": 1}
        for word, n in expected.items():
            self.assertEqual(syllables(word), n, word)


class TestChecks(unittest.TestCase):
    def test_simple_text_passes(self):
        self.assertLess(fk_grade(SIMPLE), 3.0)
        self.assertEqual(run_checks(SIMPLE, "5-7"), [])

    def test_length_boundaries(self):
        word = "Cat. "
        self.assertTrue(any("Length" in f for f in run_checks(word * 399, "5-7")))
        self.assertFalse(any("Length" in f for f in run_checks(word * 400, "5-7")))
        self.assertFalse(any("Length" in f for f in run_checks(word * 800, "5-7")))
        self.assertTrue(any("Length" in f for f in run_checks(word * 801, "5-7")))

    def test_complex_text_fails_reading_level(self):
        hard = "Notwithstanding considerable environmental uncertainties, the extraordinarily meticulous investigators systematically documented unprecedented observations. " * 40
        self.assertTrue(any("Reading level" in f for f in run_checks(hard, "8-10")))

    def test_meta_opener_detected(self):
        self.assertTrue(any("talking to the adult" in f for f in run_checks("I can't write that, but here is a cozy story. " + SIMPLE, "5-7")))

    def test_meta_opener_after_title_detected(self):
        story = "**Sleepy Cat**\n\nI cannot write that. " + SIMPLE
        self.assertTrue(any("talking to the adult" in f for f in run_checks(story, "5-7")))

    def test_short_refusal_line_not_mistaken_for_title(self):
        story = "I can't write that.\n\n" + SIMPLE
        self.assertTrue(any("talking to the adult" in f for f in run_checks(story, "5-7")))

    def test_curly_apostrophe_refusal_detected(self):
        self.assertTrue(any("talking to the adult" in f for f in run_checks("I can’t do that. " + SIMPLE, "5-7")))

    def test_titles_that_look_like_openers_allowed(self):
        for title in ("**Sleepy Cat**", "Sorry Bear's Day", "Here Is the Moon", "Sure-Footed Goat"):
            self.assertEqual(run_checks(f"{title}\n\n{SIMPLE}", "5-7"), [], title)

    def test_title_excluded_from_word_count(self):
        title, body = split_title("**A Very Long Title For A Story**\n\n" + SIMPLE)
        self.assertEqual(title, "**A Very Long Title For A Story**")
        self.assertEqual(len(body.split()), 600)


if __name__ == "__main__":
    unittest.main()
