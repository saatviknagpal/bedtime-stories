import re

WORD_RANGE = (400, 800)  # accepted range (~5-10 min read-aloud); the prompt targets 450-650
MAX_GRADE = {"5-7": 3.0, "8-10": 5.0}  # Flesch-Kincaid grade caps per age band
MAX_LONG_WORD_SHARE = 0.25  # per paragraph: share of 3+ syllable words
# Only unambiguous refusals: a match blocks the story. Softer cases ("Sure, here you go") are left to the judge's story_only check.
META_OPENER = re.compile(
    r"^\W*(i can't|i cannot|i won't|i'm (sorry|not able|unable)|i am (sorry|not able|unable)"
    r"|here's (a|your) (\w+ )?(story|version)|here is (a|your) (\w+ )?(story|version))",
    re.I,
)


def _normalize(text: str) -> str:
    return text.replace("’", "'").replace("‘", "'")


META_FAILURE = "Starts by talking to the adult instead of telling the story. Output only the title and story."


def split_title(story: str) -> tuple[str, str]:
    """The storyteller puts the title on the first line; grade and count only the body."""
    lines = _normalize(story).strip().splitlines()
    first = lines[0] if lines else ""
    ends_like_sentence = re.search(r"[.:,]\W*$", first)  # titles rarely end with a period; "!" and "?" titles are fine
    if len(lines) > 1 and len(first.split()) <= 12 and not ends_like_sentence:
        return lines[0], "\n".join(lines[1:]).strip()
    return "", "\n".join(lines)


def syllables(word: str) -> int:
    w = word.lower().strip("'")
    if w.endswith("ed") and len(w) > 3 and w[-3] not in "td":
        w = w[:-2]  # jumped, played: silent -ed
    groups = len(re.findall(r"[aeiouy]+", w))
    if w.endswith("e") and not re.search(r"[^aeiouy]le$", w) and groups > 1:
        groups -= 1  # silent e (cake), but not consonant+le (little, table)
    return max(1, groups)


def fk_grade(text: str) -> float:
    words = re.findall(r"[A-Za-z']+", _normalize(text))
    sentences = max(1, len(re.findall(r"[.!?]+", text)))
    if not words:
        return 0.0
    return 0.39 * len(words) / sentences + 11.8 * sum(map(syllables, words)) / len(words) - 15.59


def run_checks(story: str, age_band: str) -> list[str]:
    """Deterministic checks on the story body. Returns failure notes; empty list means pass."""
    _, body = split_title(story)
    failures = []
    n = len(body.split())
    lo, hi = WORD_RANGE
    if not lo <= n <= hi:
        failures.append(f"Length is {n} words; must be {lo}-{hi}.")
    grade = fk_grade(body)
    if grade > MAX_GRADE[age_band]:
        failures.append(f"Reading level is grade {grade:.1f}; must be <= {MAX_GRADE[age_band]} for ages {age_band}. Use shorter sentences and simpler words.")
    # One dense paragraph barely moves the whole-story average, so also check each paragraph's share of long words.
    # (Per-paragraph grade is too noisy: one long, simple sentence scores grade 9+.)
    for p in body.split("\n\n"):
        words = re.findall(r"[A-Za-z']+", p)
        if len(words) >= 12 and (share := sum(syllables(w) >= 3 for w in words) / len(words)) > MAX_LONG_WORD_SHARE:
            failures.append(f"The paragraph starting \"{p[:40]}...\" uses too many long words ({share:.0%}); use simpler words.")
    if META_OPENER.match(body):
        failures.append(META_FAILURE)
    return failures
