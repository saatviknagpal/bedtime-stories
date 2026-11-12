import unittest

from story.screening import JUNK_MESSAGE, PERSONAL_MESSAGE, RequestRejected, screen


def rejected(text: str) -> str | None:
    try:
        screen(text)
    except RequestRejected as e:
        return str(e)
    return None


class TestScreening(unittest.TestCase):
    def test_allows_real_requests(self):
        for ok in ("socks", "dragons", "A story about Maya and her cat Bob",
                   "My dog Max went to the moon", "a story about liberty and property",
                   "Explain black holes as a bedtime story for a 9 year old",
                   "a story about a school of fish", "a dragon who lives at 3 in the morning",
                   "una historia sobre un gato", "龙", "Qwerty the robot learns to sleep",
                   "Max counts 1, 2, 3, 4, 5, 6, 7, 8, 9, 10 sheep", "a story about 1234567890 stars",
                   "a dragon who goes to the Magic Academy", "10 cars drive to the beach",
                   "3 bears find their way home", "a story set in 1999"):
            self.assertIsNone(rejected(ok), ok)

    def test_rejects_junk(self):
        for junk in ("", "!!!!", "1234 5678", "a", "aaaaaaa", "asdfghjkl", "qwerty", "zxcvbnm asdfghj"):  # mash mixed with real words is left to intake
            self.assertEqual(rejected(junk), JUNK_MESSAGE, junk)

    def test_rejects_personal_details(self):
        for pii in ("a story for maya@example.com",
                    "call me at 555-123-4567 and tell a story",
                    "my phone is (415) 555 0123",
                    "we live at 42 Maple Street, a story about our house",
                    "Maya goes to Lincoln Elementary, make a story",
                    "my child goes to Lincoln elementary", "she goes to St. Mary's Elementary",
                    "we live at 12 Oak Drive", "call me at 4155550123 for a story"):
            self.assertEqual(rejected(pii), PERSONAL_MESSAGE, pii)


if __name__ == "__main__":
    unittest.main()
