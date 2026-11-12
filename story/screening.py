"""Free, code-only checks on what someone types, run before any model call.

Junk (no letters, one repeated letter, keyboard mashing) and common personal details (emails, US-style phone
numbers, street addresses, named schools) are turned away with a friendly message. First names are welcome:
"a story about Maya and her cat" is the point of the app. Anything subtler is left to the intake model.
"""
import re

JUNK_MESSAGE = "Tell me who or what the story should be about, like “a sleepy owl who can’t find her hat.”"
PERSONAL_MESSAGE = ("Please leave out phone numbers, emails, home addresses and school names. "
                    "A first name is perfect!")
NOT_A_STORY_MESSAGE = ("That doesn’t sound like a story idea yet. Tell me who or what the story should be about, "
                       "like “a dragon who is afraid of the dark.”")

_KEYBOARD_ROWS = ("qwertyuiop", "asdfghjkl", "zxcvbnm")
_MASH_RUN = 5  # 5+ keys in a row along one keyboard row; 4 would flag real words like "liberty"

_STREET = r"(?:street|st|avenue|ave|road|rd|lane|ln|boulevard|blvd)"  # never everyday words
_STREET_CAPITALIZED = r"(?:Drive|Dr|Way|Court|Ct|Place|Pl|Terrace|Circle)"  # also verbs/nouns ("10 cars drive")
_SCHOOL = r"(?:[Ee]lementary|[Mm]iddle [Ss]chool|[Hh]igh [Ss]chool|[Pp]rimary [Ss]chool)"  # not "Academy": wizard schools

_PERSONAL = [
    re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"),  # email
    re.compile(r"\(?\b\d{3}\)?[\s.-]\d{3}[\s.-]\d{4}\b"),  # US phone shape 3-3-4; counting "1, 2, 3..." doesn't fit
    re.compile(r"\b(?:call|phone|number|text|cell|mobile|whatsapp)\b\D{0,20}\b\d{10,11}\b", re.I),  # bare digits near a phone word
    re.compile(rf"\b\d{{1,5}}\s+(?:[A-Za-z]+\s+){{1,3}}{_STREET}\b", re.I),
    re.compile(rf"\b\d{{1,5}}\s+(?:[A-Za-z]+\s+){{1,3}}{_STREET_CAPITALIZED}\b"),
    re.compile(rf"\b(?:St\.?\s+)?[A-Z][\w'.]*(?:\s+[A-Z][\w'.]*)*\s+{_SCHOOL}\b"),  # "Lincoln Elementary", "St. Mary's Elementary"
]


class RequestRejected(ValueError):
    """The request can't become a story; str(e) is a friendly message to show the person."""


def _is_mash(word: str) -> bool:
    return any(row[i : i + _MASH_RUN] in word for row in _KEYBOARD_ROWS for i in range(len(row) - _MASH_RUN + 1))


def screen(text: str) -> None:
    """Check what a person typed. Raise RequestRejected if it is junk or contains personal details."""
    words = re.findall(r"[^\W\d_]+", text.lower())  # runs of letters, in any alphabet
    letters = "".join(words)
    too_short = len(letters) < 2 and letters.isascii()  # one Latin letter is junk; one ideograph (龙) can be a subject
    if not letters or too_short or (len(letters) >= 4 and len(set(letters)) == 1) or all(map(_is_mash, words)):
        raise RequestRejected(JUNK_MESSAGE)
    if any(p.search(text) for p in _PERSONAL):
        raise RequestRejected(PERSONAL_MESSAGE)

