"""HTTP API for the bedtime story pipeline, plus the built web UI.

Run locally: cd web && npm run build && cd .. && uvicorn api:app   (one origin serves the site and API)
Story and change endpoints stream Server-Sent Events (SSE): one JSON object per `data:` line.
Only reviewed text leaves the server: progress arrives as `stage` events, and a draft that fails a safety
check is sent without its text. The server keeps no state between requests.
"""
import json
import os
import queue
import threading
import time
from collections import defaultdict, deque
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from story.pipeline import CHECKS, Draft, Intake, change_story, read_request, tell_story

ROOT = Path(__file__).parent
MAX_CONCURRENT = int(os.getenv("MAX_CONCURRENT_STORIES", "4"))
PER_IP_LIMIT = int(os.getenv("STORIES_PER_IP_PER_HOUR", "20"))
app = FastAPI(title="Bedtime Stories")

# shortcut: limits live in this process's memory; with more than one server instance, move them to Redis.
_slots = threading.BoundedSemaphore(MAX_CONCURRENT)
_recent: dict[str, deque] = defaultdict(deque)
_recent_lock = threading.Lock()


class Cancelled(Exception):
    """The browser disconnected; stop spending on this request."""


class StoryRequest(BaseModel):
    request: str = Field(min_length=1, max_length=500)
    age_band: Literal["5-7", "8-10"] | None = None


class ChangeRequest(BaseModel):
    request: str = Field(min_length=1, max_length=2000)  # grows with each accepted change
    intake: Intake
    story: str = Field(min_length=1, max_length=8000)
    change: str = Field(min_length=1, max_length=300)


HIDDEN = "Hidden: this draft was not safe for bedtime."


def draft_json(d: Draft) -> dict:
    v = d.verdict
    if d.blocked:  # judge reasons, notes and code messages can quote the story, so send none of them
        return {"story": None, "passed": False, "blocked": True, "scores": d.scores, "code_failures": [], "notes": [],
                "checks": [{"name": c, "passed": getattr(v, c).passed, "reason": HIDDEN} for c in CHECKS]}
    return {
        "story": d.story,
        "passed": d.passed,
        "blocked": False,
        "checks": [{"name": c, "passed": getattr(v, c).passed, "reason": getattr(v, c).reason} for c in CHECKS],
        "scores": d.scores,
        "code_failures": d.code_failures,
        "notes": d.notes,
    }


TRUST_PROXY = os.getenv("TRUST_PROXY") == "1"  # set on the host (Render), whose proxy appends the real client IP
MAX_TRACKED_IPS = 10_000


def _client_ip(req: Request) -> str:
    forwarded = req.headers.get("x-forwarded-for", "")
    if TRUST_PROXY and forwarded:
        return forwarded.split(",")[-1].strip()  # the proxy's own entry; earlier ones are client-supplied
    return req.client.host if req.client else "unknown"


def _over_limit(ip: str) -> bool:
    now = time.time()
    with _recent_lock:
        if ip not in _recent and len(_recent) >= MAX_TRACKED_IPS:  # hard cap: drop idle IPs, else the least recent
            for key in [k for k, hits in _recent.items() if not hits or now - hits[-1] > 3600]:
                del _recent[key]
            if len(_recent) >= MAX_TRACKED_IPS:
                del _recent[min(_recent, key=lambda k: _recent[k][-1])]
        hits = _recent[ip]
        while hits and now - hits[0] > 3600:
            hits.popleft()
        if len(hits) >= PER_IP_LIMIT:
            return True
        hits.append(now)
        return False


def sse(req: Request, work):
    """Run `work(emit)` in a thread and stream each event; stop the work if the browser goes away."""
    if not _slots.acquire(blocking=False):  # check capacity first so a busy reply doesn't use up the quota
        return JSONResponse({"detail": "The storyteller is busy. Please try again in a minute."}, status_code=503)
    if _over_limit(_client_ip(req)):
        _slots.release()
        return JSONResponse({"detail": "That's a lot of stories for one night. Please try again later."}, status_code=429)

    events: queue.Queue = queue.Queue(maxsize=100)
    cancelled = threading.Event()

    def emit(event: dict):
        if cancelled.is_set():
            raise Cancelled
        events.put(event, timeout=60)

    def run():
        try:
            work(emit)
        except Cancelled:
            return
        except Exception as e:  # report, don't hang the stream
            if not cancelled.is_set():
                events.put({"type": "error", "message": str(e)})
        finally:
            _slots.release()
            try:
                events.put_nowait(None)
            except queue.Full:  # only when nobody is reading anymore
                pass

    threading.Thread(target=run, daemon=True).start()

    def stream():
        try:
            while (event := events.get()) is not None:
                yield f"data: {json.dumps(event)}\n\n"
        finally:  # runs when the client disconnects, too
            cancelled.set()

    return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})


def _hooks(emit):
    return dict(on_draft=lambda d: emit({"type": "draft", "draft": draft_json(d)}),
                on_stage=lambda s: emit({"type": "stage", "stage": s}))


@app.post("/api/story")
def story(body: StoryRequest, req: Request):
    def work(emit):
        emit({"type": "stage", "stage": "reading"})
        intake = read_request(body.request, body.age_band)
        emit({"type": "intake", "intake": intake.model_dump()})
        result = tell_story(body.request, intake=intake, **_hooks(emit))
        best = result.drafts.index(result.best) if result.best else None
        emit({"type": "done", "status": result.status, "best": best, "error": result.error, "request": result.request})

    return sse(req, work)


@app.post("/api/change")
def change(body: ChangeRequest, req: Request):
    def work(emit):
        result = change_story(body.request, body.intake, body.story, body.change, **_hooks(emit))
        emit({"type": "done", "applied": result is not None, "status": result.status if result else None,
              "best": result.drafts.index(result.best) if result else None,
              "request": result.request if result else body.request})

    return sse(req, work)


@app.get("/api/evals")
def evals():
    """Latest eval run plus its planted-flaw and pairwise results, if present."""
    empty = {"run": None, "cost_usd": 0, "rows": [], "golden": None, "pairwise": None}
    runs = sorted((ROOT / "evals" / "results").glob("run-*[0-9].json"))
    if not runs:
        return empty
    latest = runs[-1]
    load = lambda p: json.loads(p.read_text(encoding="utf-8")) if p and p.exists() else None
    run = load(latest)
    rows = [{k: r.get(k) for k in ("id", "kind", "request", "status", "rounds", "first_passed", "failed_checks",
                                   "scores", "words", "grade", "secs")} for r in run["rows"]]
    golden = max(latest.parent.glob(f"{latest.stem}-golden-v*.json"), default=None, key=lambda p: p.stat().st_mtime)
    return {**empty, "run": latest.name, "cost_usd": run["cost_usd"], "rows": rows,
            "golden": load(golden), "pairwise": load(latest.with_name(latest.stem + "-pairwise.json"))}


web = ROOT / "web" / "out"
if web.exists():  # built Next.js static export
    app.mount("/", StaticFiles(directory=web, html=True), name="web")
