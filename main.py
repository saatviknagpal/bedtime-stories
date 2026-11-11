import argparse

from story.pipeline import CHECKS, Draft, tell_story

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
    print(f"  engagement {v.engagement}/5 · soothing {v.soothing}/5")
    for f in draft.code_failures:
        print(f"  ❌ {f}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--age", choices=["5-7", "8-10"], default="5-7")
    args = parser.parse_args()
    user_input = input("What kind of story do you want to hear? ") or example_requests
    result = tell_story(user_input, args.age, on_draft=show)
    print("\n" + result.best.story)


if __name__ == "__main__":
    main()
