import re

WORD_RANGE = (400, 800)  # ~5-10 min read-aloud
MAX_GRADE = {"5-7": 3.0, "8-10": 5.0}  # Flesch-Kincaid grade caps per age band
META_OPENERS = re.compile(r"^\W*(i can't|i cannot|i won't|i'm sorry|sorry|sure|of course|certainly|here's|here is)\b", re.I)


def _syllables(word: str) -> int:
    groups = re.findall(r"[aeiouy]+", word.lower())
    n = len(groups) - (word.lower().endswith("e") and len(groups) > 1)
    return max(1, n)


def fk_grade(text: str) -> float:
    words = re.findall(r"[A-Za-z']+", text)
    sentences = max(1, len(re.findall(r"[.!?]+", text)))
    if not words:
        return 0.0
    syllables = sum(_syllables(w) for w in words)
    return 0.39 * len(words) / sentences + 11.8 * syllables / len(words) - 15.59


def run_checks(story: str, age_band: str) -> list[str]:
    """Deterministic checks. Returns failure notes; empty list means pass."""
    failures = []
    n = len(story.split())
    lo, hi = WORD_RANGE
    if not lo <= n <= hi:
        failures.append(f"Length is {n} words; must be {lo}-{hi}.")
    grade = fk_grade(story)
    if grade > MAX_GRADE[age_band]:
        failures.append(f"Reading level is grade {grade:.1f}; must be <= {MAX_GRADE[age_band]} for ages {age_band}. Use shorter sentences and simpler words.")
    if META_OPENERS.match(story):
        failures.append("Starts by talking to the adult instead of telling the story. Output only the title and story.")
    return failures
