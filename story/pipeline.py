from dataclasses import dataclass, field

from pydantic import BaseModel

from story.checks import run_checks
from story.llm import call_model, call_structured
from story.prompts import JUDGE_PROMPT, JUDGE_SYSTEM, REVISER_PROMPT, STORY_PROMPT, STORYTELLER_SYSTEM

MAX_REVISIONS = 2
MIN_SCORE = 4
CHECKS = ("safe", "follows_request", "clear_arc", "single_thread", "calm_ending", "story_only")


class Check(BaseModel):
    reason: str
    passed: bool


class Verdict(BaseModel):
    safe: Check
    follows_request: Check
    clear_arc: Check
    single_thread: Check
    calm_ending: Check
    story_only: Check
    engagement: int
    soothing: int
    revision_notes: list[str]


@dataclass
class Draft:
    story: str
    verdict: Verdict
    code_failures: list[str]

    @property
    def failed_checks(self) -> list[str]:
        return [c for c in CHECKS if not getattr(self.verdict, c).passed]

    @property
    def passed(self) -> bool:
        v = self.verdict
        return not self.failed_checks and not self.code_failures and min(v.engagement, v.soothing) >= MIN_SCORE

    @property
    def notes(self) -> list[str]:
        return self.code_failures + self.verdict.revision_notes


@dataclass
class Result:
    drafts: list[Draft] = field(default_factory=list)

    @property
    def best(self) -> Draft:
        # Last passing draft, else the one with fewest problems.
        passing = [d for d in self.drafts if d.passed]
        return passing[-1] if passing else min(self.drafts, key=lambda d: len(d.failed_checks) + len(d.code_failures))


def judge(request: str, story: str, age_band: str) -> Draft:
    verdict = call_structured(
        JUDGE_PROMPT.format(request=request, story=story),
        Verdict,
        system=JUDGE_SYSTEM.format(age_band=age_band),
    )
    return Draft(story, verdict, run_checks(story, age_band))


def tell_story(request: str, age_band: str = "5-7", on_draft=lambda d: None) -> Result:
    system = STORYTELLER_SYSTEM.format(age_band=age_band)
    result = Result()
    story = call_model(STORY_PROMPT.format(request=request), system=system)
    for round_ in range(MAX_REVISIONS + 1):
        draft = judge(request, story, age_band)
        result.drafts.append(draft)
        on_draft(draft)
        if draft.passed or round_ == MAX_REVISIONS:
            break
        notes = "\n".join(f"- {n}" for n in draft.notes) or "- Raise engagement and soothing scores."
        story = call_model(REVISER_PROMPT.format(request=request, story=story, notes=notes), system=system)
    return result
