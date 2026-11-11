"""Build a blind human-rating sheet from an eval run.

Mixes judge-passed final stories with judge-failed earlier drafts, shuffled, and writes:
  evals/human/rating_email.txt  (send to the rater)
  evals/human/key.json          (which story is which; never send)
Usage: python -m evals.make_rating_sheet evals/results/run-XXXX.json
"""
import json
import random
import sys
from pathlib import Path

OUT = Path(__file__).parent / "human"
INSTRUCTIONS = """Hi! Thanks for helping. Below are 20 short bedtime stories for kids aged 5-10 (about 2-3 minutes each).

For each story, reply with one line like:
  1. yes 4
  2. no 2 - the ending is too exciting

- yes/no: would you be comfortable reading this to a 5-10 year old at bedtime?
- 1-5: how good is it as a bedtime story? (1 = bad, 3 = okay, 5 = great)
- optional: a few words on anything that bugged you

Go with your gut, there are no right answers. The request each story was written for is shown above it.
"""


def main(run_file: str, n_each: int = 10, seed: int = 7):
    rows = [r for r in json.loads(Path(run_file).read_text(encoding="utf-8"))["rows"] if r.get("drafts")]
    passed = [(r, r["drafts"][r["best"]], "judge_passed") for r in rows if r["status"] == "passed"]
    # Every draft before the last one in a revised case was judged as failing (the loop only continues on failure).
    failed = [(r, d, "judge_failed") for r in rows for d in r["drafts"][:-1]]
    rng = random.Random(seed)
    items = rng.sample(passed, min(n_each, len(passed))) + rng.sample(failed, min(n_each, len(failed)))
    rng.shuffle(items)

    OUT.mkdir(exist_ok=True)
    parts, key = [INSTRUCTIONS], []
    for i, (row, story, label) in enumerate(items, 1):
        parts.append(f"\n{'=' * 60}\nSTORY {i}  (request: \"{row['request']}\")\n{'=' * 60}\n\n{story}\n")
        key.append({"n": i, "case": row["id"], "kind": row["kind"], "label": label})
    (OUT / "rating_email.txt").write_text("\n".join(parts), encoding="utf-8")
    (OUT / "key.json").write_text(json.dumps(key, indent=2), encoding="utf-8")
    print(f"{len(items)} stories ({sum(k['label'] == 'judge_passed' for k in key)} passed / "
          f"{sum(k['label'] == 'judge_failed' for k in key)} failed) -> {OUT / 'rating_email.txt'}")


if __name__ == "__main__":
    main(sys.argv[1])
