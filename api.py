"""HTTP API for the bedtime story pipeline, plus the built web UI.

Run locally: uvicorn api:app --reload
Story and change endpoints stream Server-Sent Events (SSE): one JSON object per `data:` line.
The server keeps no state between requests; the browser sends back what it needs for a change.
"""
import json
import queue
import threading
from pathlib import Path
from typing import Literal

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from story.pipeline import CHECKS, Draft, Intake, change_story, read_request, tell_story

ROOT = Path(__file__).parent
app = FastAPI(title="Bedtime Stories")


class StoryRequest(BaseModel):
    request: str = Field(min_length=1, max_length=500)
    age_band: Literal["5-7", "8-10"] | None = None


class ChangeRequest(BaseModel):
    request: str = Field(min_length=1, max_length=3000)  # grows with each accepted change
    intake: Intake
    story: str = Field(min_length=1, max_length=12000)
    change: str = Field(min_length=1, max_length=300)


def draft_json(d: Draft) -> dict:
    v = d.verdict
    return {
        "story": d.story,
        "passed": d.passed,
        "blocked": d.blocked,
        "checks": [{"name": c, "passed": getattr(v, c).passed, "reason": getattr(v, c).reason} for c in CHECKS],
        "scores": d.scores,
        "code_failures": d.code_failures,
        "notes": d.notes,
    }


def sse(work) -> StreamingResponse:
    """Run `work(emit)` in a thread and stream every emitted event to the browser as it happens."""
    events: queue.Queue = queue.Queue()

    def run():
        try:
            work(events.put)
        except Exception as e:  # report, don't hang the stream
            events.put({"type": "error", "message": str(e)})
        finally:
            events.put(None)

    threading.Thread(target=run, daemon=True).start()

    def stream():
        while (event := events.get()) is not None:
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})


@app.post("/api/story")
def story(body: StoryRequest):
    def work(emit):
        intake = read_request(body.request, body.age_band)
        emit({"type": "intake", "intake": intake.model_dump()})
        result = tell_story(body.request, intake=intake,
                            on_draft=lambda d: emit({"type": "draft", "draft": draft_json(d)}),
                            on_text=lambda t: emit({"type": "text", "text": t}))
        best = result.drafts.index(result.best) if result.best else None
        emit({"type": "done", "status": result.status, "best": best, "error": result.error, "request": result.request})

    return sse(work)


@app.post("/api/change")
def change(body: ChangeRequest):
    def work(emit):
        result = change_story(body.request, body.intake, body.story, body.change,
                              on_draft=lambda d: emit({"type": "draft", "draft": draft_json(d)}),
                              on_text=lambda t: emit({"type": "text", "text": t}))
        emit({"type": "done", "applied": result is not None, "status": result.status if result else None,
              "best": result.drafts.index(result.best) if result else None,
              "request": result.request if result else body.request})

    return sse(work)


@app.get("/api/evals")
def evals():
    """Latest eval run plus its planted-flaw and pairwise results, if present."""
    runs = sorted((ROOT / "evals" / "results").glob("run-*[0-9].json"))
    if not runs:
        return {}
    latest = runs[-1]
    load = lambda p: json.loads(p.read_text(encoding="utf-8")) if p.exists() else None
    run = load(latest)
    rows = [{k: r.get(k) for k in ("id", "kind", "request", "status", "rounds", "first_passed", "failed_checks",
                                   "scores", "words", "grade", "secs")} for r in run["rows"]]
    golden = next(iter(sorted(latest.parent.glob(f"{latest.stem}-golden-v*.json"))), None)
    return {"run": latest.name, "cost_usd": run["cost_usd"], "rows": rows,
            "golden": load(golden) if golden else None,
            "pairwise": load(latest.with_name(latest.stem + "-pairwise.json"))}


web = ROOT / "web" / "out"
if web.exists():  # built Next.js static export
    app.mount("/", StaticFiles(directory=web, html=True), name="web")
