"""Run every eval case through the full pipeline and save results.

Usage: python -m evals.run [--only id1,id2] [--workers 5]
Writes evals/results/run-<timestamp>.json and prints a summary table.
"""
import argparse
import json
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

from evals.cases import CASES
from story import llm
from story.checks import fk_grade, split_title
from story.pipeline import tell_story

RESULTS = Path(__file__).parent / "results"


def run_case(case):
    cid, kind, request = case
    start = time.time()
    try:
        r = tell_story(request)
    except Exception as e:  # one failed case must not stop the run
        return {"id": cid, "kind": kind, "request": request, "status": "error", "error": str(e), "secs": time.time() - start}
    best = r.best
    body = split_title(best.story)[1] if best else ""
    return {
        "id": cid, "kind": kind, "request": request, "status": r.status, "error": r.error,
        "intake": r.intake.model_dump(),
        "rounds": len(r.drafts),
        "first_passed": r.drafts[0].passed,
        "failed_checks": best.failed_checks if best else [],
        "code_failures": best.code_failures if best else [],
        "scores": best.scores if best else {},
        "words": len(body.split()), "grade": round(fk_grade(body), 1),
        "drafts": [d.story for d in r.drafts],
        "best": r.drafts.index(best) if best else None,
        "secs": round(time.time() - start, 1),
    }


def summarize(rows, cost):
    print(f"\n{'id':14} {'kind':9} {'status':8} rnd 1st  words grade  secs  failed")
    for x in rows:
        if x["status"] == "error":
            print(f"{x['id']:14} {x['kind']:9} ERROR  {x['error'][:60]}")
            continue
        failed = ",".join(x["failed_checks"] + [f[:12] for f in x["code_failures"]])
        print(f"{x['id']:14} {x['kind']:9} {x['status']:8} {x['rounds']:3} {'Y' if x['first_passed'] else '-':3} {x['words']:6} {x['grade']:5} {x['secs']:5}  {failed}")
    by_kind = defaultdict(list)
    for x in rows:
        by_kind[x["kind"]].append(x)
    print("\nkind       passed  flagged blocked error  first-draft-pass")
    for kind, xs in [("ALL", rows), *by_kind.items()]:
        n = len(xs)
        count = lambda s: sum(x["status"] == s for x in xs)
        first = sum(x.get("first_passed", False) for x in xs)
        print(f"{kind:10} {count('passed'):3}/{n:<3} {count('flagged'):5} {count('blocked'):7} {count('error'):5}  {first}/{n}")
    secs = [x["secs"] for x in rows]
    print(f"\nlatency avg {sum(secs) / len(secs):.0f}s, max {max(secs):.0f}s · {llm.usage['calls']} calls · "
          f"{llm.usage['input']:,} in / {llm.usage['output']:,} out tokens · ${cost:.3f} total, ${cost / len(rows):.4f}/story")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="comma-separated case ids")
    ap.add_argument("--workers", type=int, default=5)
    args = ap.parse_args()
    cases = [c for c in CASES if not args.only or c[0] in args.only.split(",")]
    with ThreadPoolExecutor(args.workers) as ex:
        rows = list(ex.map(run_case, cases))
    RESULTS.mkdir(exist_ok=True)
    out = RESULTS / f"run-{datetime.now():%Y%m%d-%H%M%S}.json"
    out.write_text(json.dumps({"cost_usd": llm.cost_usd(), "usage": dict(llm.usage), "rows": rows}, indent=2), encoding="utf-8")
    summarize(rows, llm.cost_usd())
    print(f"\nsaved {out}")


if __name__ == "__main__":
    main()
