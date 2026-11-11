from dataclasses import dataclass, field
from typing import Literal

import anthropic
from pydantic import BaseModel, Field, ValidationError

from story.checks import META_FAILURE, run_checks
from story.llm import LLMError, call_model, call_structured
from story.prompts import (
    CATEGORY_GUIDES,
    EXTRA_GENTLE,
    FALLBACK_PROMPT,
    INTAKE_PROMPT,
    INTAKE_SYSTEM,
    JUDGE_PROMPT,
    JUDGE_SYSTEM,
    REVISER_PROMPT,
    STORY_PROMPT,
    STORYTELLER_SYSTEM,
)

MAX_REVISIONS = 2
MIN_SCORE = 4
CHECKS = ("safe", "follows_request", "clear_arc", "single_thread", "calm_ending", "story_only")
BLOCKING = ("safe", "story_only")  # never shown to a child if these fail
RECOVERABLE = (LLMError, anthropic.APIError, ValidationError)

Score = Field(ge=1, le=5)


class Intake(BaseModel):
    age_band: Literal["5-7", "8-10"]
    category: Literal["adventure", "friendship", "animals", "funny", "fantasy", "comfort", "everyday"]
    brief: str


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
    engagement: int = Score
    soothing: int = Score
    care: int = Score
    revision_notes: list[str]


@dataclass
class Draft:
    story: str
    verdict: Verdict
    code_failures: list[str]
    category: str

    @property
    def scores(self) -> dict[str, int]:
        # Comfort stories are judged on care, not excitement (see README: rubric).
        first = "care" if self.category == "comfort" else "engagement"
        return {first: getattr(self.verdict, first), "soothing": self.verdict.soothing}

    @property
    def failed_checks(self) -> list[str]:
        return [c for c in CHECKS if not getattr(self.verdict, c).passed]

    @property
    def low_scores(self) -> list[str]:
        return [k for k, v in self.scores.items() if v < MIN_SCORE]

    @property
    def blocked(self) -> bool:
        return any(c in BLOCKING for c in self.failed_checks) or META_FAILURE in self.code_failures

    @property
    def passed(self) -> bool:
        return not (self.failed_checks or self.low_scores or self.code_failures)

    @property
    def notes(self) -> list[str]:
        failed = [f"{c}: {getattr(self.verdict, c).reason}" for c in self.failed_checks]
        low = [f"{k} scored {self.scores[k]}/5; raise it to at least {MIN_SCORE}." for k in self.low_scores]
        return failed + low + self.code_failures + self.verdict.revision_notes

    def rank(self) -> tuple:
        return (self.blocked, len(self.failed_checks) + len(self.low_scores) + len(self.code_failures))


@dataclass
class Result:
    request: str
    intake: Intake
    system: str
    drafts: list[Draft] = field(default_factory=list)
    error: str | None = None
    on_text: object = None  # optional streaming callback for story text

    @property
    def best(self) -> Draft | None:
        passing = [d for d in self.drafts if d.passed]
        if passing:
            return passing[-1]
        return min(self.drafts, key=Draft.rank) if self.drafts else None

    @property
    def status(self) -> Literal["passed", "flagged", "blocked"]:
        best = self.best
        if best is None or best.blocked:
            return "blocked"
        return "passed" if best.passed else "flagged"


def esc(text: str) -> str:
    """Keep untrusted text from closing or opening prompt tags."""
    return text.replace("<", "&lt;").replace(">", "&gt;")


def judge(request: str, story: str, intake: Intake) -> Draft:
    verdict = call_structured(
        JUDGE_PROMPT.format(request=esc(request), story=esc(story)),
        Verdict,
        system=JUDGE_SYSTEM.format(age_band=intake.age_band),
    )
    return Draft(story, verdict, run_checks(story, intake.age_band), intake.category)


def _revise(result: Result, story: str, notes: list[str]) -> str:
    bullets = "\n".join(f"- {n}" for n in notes)
    prompt = REVISER_PROMPT.format(request=esc(result.request), story=esc(story), notes=esc(bullets))
    return call_model(prompt, system=result.system, on_text=result.on_text)


def _write_fresh(result: Result) -> str:
    prompt = STORY_PROMPT.format(request=esc(result.request), brief=esc(result.intake.brief))
    return call_model(prompt, system=result.system, on_text=result.on_text)


def _write_safe_fallback(result: Result) -> str:
    # Only the softened brief: the raw request may be what made earlier drafts unsafe.
    prompt = FALLBACK_PROMPT.format(brief=esc(result.intake.brief))
    return call_model(prompt, system=result.system + EXTRA_GENTLE, on_text=result.on_text)


def _refine(result: Result, write_first, on_draft, fallback: bool = True) -> Result:
    """Judge a first draft, revise until it passes (bounded), then apply the safety fallback."""

    def add(story: str) -> Draft:
        draft = judge(result.request, story, result.intake)
        result.drafts.append(draft)
        on_draft(draft)
        return draft

    try:
        draft = add(write_first())
        for _ in range(MAX_REVISIONS):
            if draft.passed:
                break
            draft = add(_revise(result, draft.story, draft.notes))
    except RECOVERABLE as e:
        if not result.drafts:
            raise
        result.error = str(e)  # keep earlier drafts; best/status still work
    if fallback and result.best.blocked:
        # Safety fallback: one fresh, extra-gentle attempt from the softened brief.
        try:
            add(_write_safe_fallback(result))
        except RECOVERABLE as e:
            result.error = str(e)
    return result


def system_for(intake: Intake) -> str:
    return STORYTELLER_SYSTEM.format(age_band=intake.age_band) + "\n\nGenre guidance: " + CATEGORY_GUIDES[intake.category]


def read_request(request: str, age_band: str | None = None) -> Intake:
    intake = call_structured(INTAKE_PROMPT.format(request=esc(request)), Intake, system=INTAKE_SYSTEM)
    if age_band:
        intake.age_band = age_band
    return intake


def tell_story(request: str, age_band: str | None = None, on_draft=lambda d: None, on_text=None,
               intake: Intake | None = None) -> Result:
    """Full pipeline. `on_text` streams story words as they are written; a new draft starts after each on_draft."""
    intake = intake or read_request(request, age_band)
    result = Result(request, intake, system_for(intake), on_text=on_text)
    return _refine(result, lambda: _write_fresh(result), on_draft)


def change_story(request: str, intake: Intake, story: str, change: str, on_draft=lambda d: None, on_text=None) -> Result | None:
    """Apply a listener's change to `story` and judge it against the request plus the change.

    Returns the new result only if it fully passes; None means keep the story you have, so a story that passed
    is never swapped for a worse one. No safety fallback: regenerating from the brief would drop the change.
    Takes plain values so a stateless API can call it.
    """
    result = Result(f"{request}\n\nRequested change: {change}", intake, system_for(intake), on_text=on_text)
    note = f"The listener asked for this change: {change}"
    _refine(result, lambda: _revise(result, story, [note]), on_draft, fallback=False)
    return result if result.status == "passed" else None


def request_change(previous: Result, change: str, on_draft=lambda d: None) -> tuple[Result, bool]:
    """CLI helper: returns (result, applied), keeping `previous` when the change did not pass."""
    new = change_story(previous.request, previous.intake, previous.best.story, change, on_draft)
    return (new, True) if new else (previous, False)
