import argparse
import sys

from story.pipeline import CHECKS, RECOVERABLE, Draft, request_change, tell_story

"""
Before submitting the assignment, describe here in a few sentences what you would have built next if you spent 2 more hours on this project:

"""

example_requests = "A story about a girl named Alice and her best friend Bob, who happens to be a cat."


def show(draft: Draft) -> None:
    v = draft.verdict
    print(f"\n--- Judge: {'PASS' if draft.passed else 'needs revision'} ---")
    for c in CHECKS:
        check = getattr(v, c)
        print(f"  {'✅' if check.passed else '❌'} {c}: {check.reason}")
    print("  " + " · ".join(f"{k} {s}/5" for k, s in draft.scores.items()))
    for f in draft.code_failures:
        print(f"  ❌ {f}")


def main():
    sys.stdout.reconfigure(encoding="utf-8")  # emoji output on Windows consoles and pipes
    parser = argparse.ArgumentParser()
    parser.add_argument("--age", choices=["5-7", "8-10"], help="override the age band inferred from the request")
    args = parser.parse_args()

    request = ask("What kind of story do you want to hear? (Enter for an example) ")
    if not request:
        request = example_requests
        print(f"Using example: {request}")

    try:
        result = tell_story(request, args.age, on_draft=show)
    except RECOVERABLE as e:
        sys.exit(f"Could not create a story: {e}")
    print(f"\n[{result.intake.category}, ages {result.intake.age_band}] {result.intake.brief}")
    if result.error:
        print(f"(stopped early: {result.error})")

    shown = present(result)
    while shown and (change := ask("\nWant any changes? (describe them, or press Enter to finish) ")):
        try:
            result, applied = request_change(result, change, on_draft=show)
            if not applied:
                print("\nI couldn't make that change and keep the story bedtime-ready, so here's the version you had:")
        except RECOVERABLE as e:
            print(f"\nCouldn't apply that change ({e}). Here's the story you had:")
        present(result)


def ask(prompt: str) -> str:
    try:
        return input(prompt).strip()
    except EOFError:
        return ""


def present(result) -> bool:
    """Print the story, or a gentle refusal if nothing safe was produced. Returns whether a story was shown."""
    if result.status == "blocked":
        print("\nI couldn't make a story for that one that's gentle enough for bedtime. Try another idea?")
        return False
    if result.status == "flagged":
        print("\n(Note: this story didn't fully pass review.)")
    print("\n" + result.best.story)
    return True


if __name__ == "__main__":
    main()
