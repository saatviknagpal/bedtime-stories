"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { ArrowRight, ChartBar, MoonStars, Sparkle } from "@phosphor-icons/react";
import { JudgePanel } from "@/components/JudgePanel";
import { Progress, type Step } from "@/components/Progress";
import { ReadAloud, StoryCard } from "@/components/StoryCard";
import { stream, type AgeBand, type Draft, type Intake, type Status, type StoryEvent } from "@/lib/api";

type Run = { drafts: Draft[]; status: Status; best: number; request: string; token: string }; // token: server signature, required to change it
type Done = Extract<StoryEvent, { type: "done" }>;

const EXAMPLES = [
  "A girl named Alice and her best friend Bob, who is a cat",
  "A dragon who is afraid of the dark",
  "My dog Max goes to the moon",
  "A story about my grandma who died last month",
];
const CATEGORY_LABELS: Record<string, string> = {
  adventure: "Adventure", friendship: "Friendship", animals: "Animals", funny: "Funny",
  fantasy: "Fantasy", comfort: "Comfort", everyday: "Everyday",
};

export default function Home() {
  const [request, setRequest] = useState("");
  const [age, setAge] = useState<AgeBand | "auto">("auto");
  const [running, setRunning] = useState<"story" | "change" | null>(null);
  const [steps, setSteps] = useState<Step[]>([]);
  const [intake, setIntake] = useState<Intake | null>(null);
  const [run, setRun] = useState<Run | null>(null); // the accepted story; only reviewed text ever lands here
  const [selected, setSelected] = useState(0);
  const [animate, setAnimate] = useState(false);
  const [message, setMessage] = useState("");
  const [change, setChange] = useState("");
  const runId = useRef(0);
  const abort = useRef<AbortController | null>(null);

  // Leaving the page cancels the request, which also stops the server's work.
  useEffect(() => () => {
    runId.current++;
    abort.current?.abort();
  }, []);

  /** Stream one request. Events from a superseded run are ignored, so overlapping runs can't clobber state. */
  async function go(kind: "story" | "change", path: string, body: unknown, onDone: (e: Done, drafts: Draft[]) => void) {
    abort.current?.abort();
    abort.current = new AbortController();
    const id = ++runId.current;
    const mine = () => id === runId.current;
    setRunning(kind);
    setMessage("");
    setSteps([]);
    const drafts: Draft[] = [];
    try {
      await stream(path, body, (e) => {
        if (!mine()) return;
        if (e.type === "stage") setSteps((s) => [...s, { stage: e.stage }]);
        else if (e.type === "intake") setIntake(e.intake);
        else if (e.type === "draft") {
          drafts.push(e.draft);
          setSteps((s) => s.map((step, i) => (i === s.length - 1 ? { ...step, draft: e.draft } : step)));
        } else if (e.type === "done") onDone(e, drafts);
        else if (e.type === "error") {
          setMessage(e.message);
          setSteps([]); // no step is still running
        }
      }, abort.current.signal);
    } catch (err) {
      if (mine() && (err as Error).name !== "AbortError") setMessage("Couldn’t reach the storyteller. Please try again.");
    } finally {
      if (mine()) setRunning(null);
    }
  }

  function tellStory(text: string) {
    const trimmed = text.trim();
    if (!trimmed || running) return;
    setRequest(trimmed);
    setRun(null);
    setIntake(null);
    go("story", "/api/story", { request: trimmed, age_band: age === "auto" ? null : age }, (e, drafts) => {
      if (e.status === "blocked" || e.best === null || e.status === null || !e.token) {
        setMessage("I couldn’t make a story for that one that’s gentle enough for bedtime. Try another idea?");
        return;
      }
      setRun({ drafts, status: e.status, best: e.best, request: e.request, token: e.token });
      setSelected(e.best);
      setAnimate(true);
    });
  }

  function requestChange() {
    if (!run || !intake || !change.trim() || running) return;
    go("change", "/api/change", { request: run.request, intake, story: run.drafts[run.best].story, change: change.trim(), token: run.token }, (e, drafts) => {
      if (e.applied && e.best !== null && e.status && e.token) {
        setRun({ drafts, status: e.status, best: e.best, request: e.request, token: e.token });
        setSelected(e.best);
        setAnimate(true);
        setChange("");
      } else {
        setMessage("I couldn’t make that change and keep the story bedtime-ready, so here’s the version you had.");
      }
    });
  }

  const shownDraft = run?.drafts[selected];
  const isFinal = run !== null && selected === run.best;
  const busy = running !== null;

  return (
    <main className="mx-auto max-w-6xl px-4 sm:px-6 pb-20">
      <header className="flex items-center justify-between py-6">
        <a href="#" className="flex items-center gap-2.5 text-lg font-semibold tracking-wide text-slate-100">
          <MoonStars size={28} weight="duotone" className="text-moon" aria-hidden="true" />
          Bedtime Stories
        </a>
        <Link href="/evals/" className="inline-flex items-center gap-2 rounded-full px-4 py-2 text-sm text-muted hover:text-slate-100 hover:bg-white/5 transition-colors min-h-11">
          <ChartBar size={18} aria-hidden="true" /> How it’s tested
        </Link>
      </header>

      <section className="pt-6 pb-10 text-center">
        <h1 className="font-story text-4xl sm:text-5xl font-semibold text-slate-50 text-balance">A gentle story, written and checked for bedtime</h1>
        <p className="mx-auto mt-4 max-w-2xl text-base sm:text-lg text-slate-300">
          Tell me what tonight’s story should be about. A writer drafts it, a reviewer checks it for ages 5-10, and nothing reaches you until it passes the safety check.
        </p>
      </section>

      <form
        className="mx-auto max-w-3xl rounded-2xl border border-night-line bg-night-card/80 p-4 sm:p-5"
        onSubmit={(e) => {
          e.preventDefault();
          tellStory(request);
        }}
      >
        <label htmlFor="request" className="block text-sm font-medium text-slate-200 mb-2">What should the story be about?</label>
        <textarea
          id="request"
          value={request}
          onChange={(e) => setRequest(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              tellStory(request);
            }
          }}
          maxLength={500}
          rows={2}
          placeholder="A shy octopus who learns to make friends…"
          className="w-full resize-none rounded-xl bg-night/70 border border-white/10 px-4 py-3 text-base text-slate-100 placeholder:text-slate-500 focus:border-moon/60"
        />
        <div className="mt-3 flex flex-col-reverse sm:flex-row sm:items-center justify-between gap-3">
          <fieldset className="flex items-center gap-2">
            <legend className="sr-only">Age</legend>
            <span className="text-sm text-muted mr-1" aria-hidden="true">Age</span>
            {(["auto", "5-7", "8-10"] as const).map((a) => (
              <label key={a} className={`cursor-pointer rounded-full px-3.5 py-1.5 text-sm border transition-colors min-h-9 inline-flex items-center has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-moon ${age === a ? "border-moon/70 bg-moon/10 text-moon" : "border-white/10 text-slate-300 hover:bg-white/5"}`}>
                <input type="radio" name="age" value={a} checked={age === a} onChange={() => setAge(a)} className="sr-only" />
                {a === "auto" ? "Auto" : a}
              </label>
            ))}
          </fieldset>
          <button
            type="submit"
            disabled={busy || !request.trim()}
            className="inline-flex items-center justify-center gap-2 rounded-full bg-moon px-6 py-2.5 font-semibold text-night hover:bg-amber disabled:opacity-45 disabled:cursor-not-allowed cursor-pointer transition-colors min-h-11"
          >
            <Sparkle size={18} weight="fill" aria-hidden="true" />
            {running === "story" ? "Writing…" : "Tell me a story"}
          </button>
        </div>
        {!run && !busy && (
          <div className="mt-4 flex flex-wrap gap-2">
            {EXAMPLES.map((ex) => (
              <button key={ex} type="button" onClick={() => tellStory(ex)}
                className="rounded-full border border-white/10 px-3 py-1.5 text-xs text-slate-300 hover:bg-white/5 cursor-pointer transition-colors min-h-8">
                {ex}
              </button>
            ))}
          </div>
        )}
      </form>

      <p className="sr-only" aria-live="polite">{busy ? "Working on your story." : message || (run ? "Your story is ready." : "")}</p>

      {(run || busy || message) && (
        <section className="mt-10 grid gap-6 lg:grid-cols-[minmax(0,1fr)_360px]">
          <div className="space-y-4 min-w-0">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex flex-wrap items-center gap-2 text-sm text-muted">
                {intake && (
                  <span className="rounded-full bg-white/5 px-3 py-1">
                    {CATEGORY_LABELS[intake.category] ?? intake.category} · ages {intake.age_band}
                  </span>
                )}
                {busy && <span className="text-moon">{running === "change" ? "Rewriting with your change…" : "Writing and checking…"}</span>}
                {!busy && run?.status === "passed" && <span className="text-pass">Passed review</span>}
              </div>
              {run && !busy && <ReadAloud text={run.drafts[run.best].story ?? ""} />}
            </div>

            {run && run.drafts.length > 1 && (
              <div className="flex flex-wrap items-center gap-2" aria-label="Drafts">
                <span className="text-xs text-muted mr-1">Drafts</span>
                {run.drafts.map((d, i) => (
                  <button key={i} type="button" aria-pressed={selected === i} disabled={!d.story}
                    onClick={() => { setSelected(i); setAnimate(false); }}
                    className={`rounded-full px-3.5 py-1.5 text-sm border cursor-pointer transition-colors min-h-9 disabled:cursor-not-allowed disabled:opacity-50 ${selected === i ? "border-moon/70 bg-moon/10 text-moon" : "border-white/10 text-slate-300 hover:bg-white/5"}`}>
                    {i === run.best ? "Final" : `Draft ${i + 1}`}
                    <span className={`ml-2 inline-block h-1.5 w-1.5 rounded-full align-middle ${d.passed ? "bg-pass" : d.blocked ? "bg-block" : "bg-fail"}`} aria-hidden="true" />
                    <span className="sr-only">{d.passed ? " (passed)" : d.blocked ? " (hidden: not right for bedtime)" : " (needed work)"}</span>
                  </button>
                ))}
              </div>
            )}

            {message && !busy && <p className="rounded-xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-slate-200" role="status">{message}</p>}
            {run && !busy && run.status === "flagged" && isFinal && (
              <p className="rounded-xl border border-fail/30 bg-fail/10 px-4 py-3 text-sm text-fail">
                This story is safe but didn’t fully pass review. The reviewer’s notes show what could be better.
              </p>
            )}
            {run && !isFinal && (
              <p className="text-xs text-muted">This is an earlier draft that the reviewer sent back. The final story is under “Final”.</p>
            )}

            {shownDraft?.story ? (
              <div className={busy ? "opacity-60 transition-opacity" : "transition-opacity"}>
                <StoryCard text={shownDraft.story} animate={animate && isFinal} />
              </div>
            ) : busy ? (
              <div className="rounded-2xl bg-paper/90 h-72 grid place-items-center text-ink/60 font-story" aria-hidden="true">
                <span className="animate-pulse">The story will appear here once it passes review…</span>
              </div>
            ) : null}

            {run && (
              <form className="flex flex-col sm:flex-row gap-3" onSubmit={(e) => { e.preventDefault(); requestChange(); }}>
                <label htmlFor="change" className="sr-only">Ask for a change</label>
                <input id="change" value={change} onChange={(e) => setChange(e.target.value)} maxLength={300} disabled={busy}
                  placeholder="Want a change? e.g. add a puppy named Rex"
                  className="flex-1 rounded-full bg-night-card/80 border border-white/10 px-5 py-2.5 text-base text-slate-100 placeholder:text-slate-500 focus:border-moon/60 min-h-11 disabled:opacity-50" />
                <button type="submit" disabled={busy || !change.trim()}
                  className="inline-flex items-center justify-center gap-2 rounded-full border border-moon/60 px-5 py-2.5 font-semibold text-moon hover:bg-moon/10 disabled:opacity-45 disabled:cursor-not-allowed cursor-pointer transition-colors min-h-11">
                  {running === "change" ? "Rewriting…" : "Rewrite"} <ArrowRight size={18} aria-hidden="true" />
                </button>
              </form>
            )}
          </div>

          <div className="lg:sticky lg:top-6 self-start">
            {busy || (!run && steps.length > 0) ? (
              <Progress steps={steps} title={running === "change" ? "Applying your change" : busy ? "Working on it" : "What happened"} />
            ) : (
              <JudgePanel draft={shownDraft} />
            )}
          </div>
        </section>
      )}
    </main>
  );
}
