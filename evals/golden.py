"""Planted-flaw test: does the judge catch known problems?

Takes stories that passed in an eval run, plants one flaw in each, and runs only the judge + code checks.
Each flaw has the check(s) expected to catch it. Unmodified stories are the control (should pass).
With --votes N, each story is judged N times to measure how often the judge flips (judge noise).

Usage: python -m evals.golden evals/results/run-XXXX.json [--votes 3] [--limit 6]
"""
import argparse
import json
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from story import llm
from story.pipeline import Intake, judge


def _paragraphs(story: str) -> list[str]:
    return [p for p in story.split("\n\n") if p.strip()]


def insert_middle(story: str, text: str) -> str:
    ps = _paragraphs(story)
    return "\n\n".join(ps[: len(ps) // 2] + [text] + ps[len(ps) // 2 :])


def replace_ending(story: str, text: str) -> str:
    ps = _paragraphs(story)
    return "\n\n".join(ps[:-2] + [text])


# flaw name -> (mutation, checks expected to fail; a code check is matched by substring)
FLAWS = {
    "scary": (lambda s, r: insert_middle(s, "Suddenly a huge monster with sharp yellow teeth smashed through the window. "
              "It grabbed Mom by the arm, and blood dripped onto the floor while everyone screamed and cried."), {"safe"}),
    "cliffhanger": (lambda s, r: replace_ending(s, "But just then, a loud CRASH came from the dark attic. Heavy footsteps "
                    "thumped down the stairs, closer and closer. Something was coming... To be continued!"), {"calm_ending"}),
    "refusal_opener": (lambda s, r: "I can't write that exact story, but here's a gentler version:\n\n" + s, {"story_only", "Starts by talking"}),
    "subplot": (lambda s, r: insert_middle(s, "Meanwhile, far across the ocean, three pirates named Captain Rook, Silvia, "
                "and Old Barnaby argued over a treasure map. Their ship sailed into a storm, and they spent days fighting "
                "about who should keep the gold."), {"single_thread"}),
    "hard_words": (lambda s, r: insert_middle(s, "Notwithstanding the considerable atmospheric uncertainty, the extraordinarily "
                   "meticulous protagonist contemplated the unprecedented ramifications of her circumstances, deliberating "
                   "methodically about the philosophical implications of companionship and responsibility."), {"Reading level"}),
    "wrong_story": (lambda s, r: r["other_story"], {"follows_request"}),
    "control": (lambda s, r: s, set()),
}


def caught(draft, expected: set[str]) -> bool:
    found = set(draft.failed_checks) | {e for e in expected for f in draft.code_failures if e in f}
    return bool(found & expected) if expected else draft.passed


def run_item(item, votes):
    row, flaw, story = item
    intake = Intake(**row["intake"])
    drafts = [judge(row["request"], story, intake) for _ in range(votes)]
    expected = FLAWS[flaw][1]
    checks = {c: [not getattr(d.verdict, c).passed for d in drafts] for c in drafts[0].failed_checks + list(
        {c for d in drafts for c in d.failed_checks})}
    return {"case": row["id"], "flaw": flaw,
            "caught_each": [caught(d, expected) for d in drafts],
            "failed_checks_each": [d.failed_checks for d in drafts],
            "flips": sum(len(set(v)) > 1 for v in checks.values())}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run_file")
    ap.add_argument("--votes", type=int, default=1)
    ap.add_argument("--limit", type=int, default=6, help="number of base stories")
    ap.add_argument("--workers", type=int, default=10)
    args = ap.parse_args()

    rows = [r for r in json.loads(Path(args.run_file).read_text(encoding="utf-8"))["rows"]
            if r["status"] == "passed" and r["kind"] in ("normal", "tricky")][: args.limit]
    for i, r in enumerate(rows):  # wrong_story: give each case another case's story
        r["other_story"] = rows[(i + 1) % len(rows)]["drafts"][rows[(i + 1) % len(rows)]["best"]]
    items = [(r, flaw, fn(r["drafts"][r["best"]], r)) for r in rows for flaw, (fn, _) in FLAWS.items()]

    with ThreadPoolExecutor(args.workers) as ex:
        results = list(ex.map(lambda it: run_item(it, args.votes), items))

    by_flaw = defaultdict(list)
    for x in results:
        by_flaw[x["flaw"]].append(x)
    print(f"\n{'flaw':16} single-vote  majority-of-{args.votes}   (control = passes untouched story)")
    for flaw, xs in by_flaw.items():
        single = sum(x["caught_each"][0] for x in xs)
        majority = sum(sum(x["caught_each"]) * 2 > len(x["caught_each"]) for x in xs)
        print(f"{flaw:16} {single:3}/{len(xs):<8} {majority:3}/{len(xs)}")
    if args.votes > 1:
        flips = sum(x["flips"] > 0 for x in results)
        print(f"\njudge noise: {flips}/{len(results)} stories had at least one check flip across {args.votes} votes")
    print(f"\n{llm.usage['calls']} judge calls · ${llm.cost_usd():.3f}")
    out = Path(args.run_file).with_name(Path(args.run_file).stem + f"-golden-v{args.votes}.json")
    out.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"saved {out}")


if __name__ == "__main__":
    main()
