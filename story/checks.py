import re

WORD_RANGE = (400, 800)  # accepted range (~5-10 min read-aloud); the prompt targets 450-650
MAX_GRADE = {"5-7": 3.0, "8-10": 5.0}  # Flesch-Kincaid grade caps per age band
META_OPENER = re.compile(
    r"^\W*(i can't|i cannot|i won't|i'm (sorry|not able|unable)|sorry,|unfortunately|sure[,!]|of course[,!]|certainly[,!]"
    r"|here's (a|your|the)|here is (a|your|the))",
    re.I,
)


def _normalize(text: str) -> str:
    return text.replace("’", "'").replace("‘", "'")


def split_title(story: str) -> tuple[str, str]:
    """The storyteller puts the title on the first line; grade and count only the body."""
    lines = _normalize(story).strip().splitlines()
    if len(lines) > 1 and len(lines[0].split()) <= 12:
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
    if META_OPENER.match(body):
        failures.append("Starts by talking to the adult instead of telling the story. Output only the title and story.")
    return failures
