import { CheckCircle, Prohibit, WarningCircle } from "@phosphor-icons/react";
import { CHECK_LABELS, SCORE_LABELS, type Draft } from "@/lib/api";

const BLOCKING = new Set(["safe", "age_fit", "story_only"]); // mirrors BLOCKING in story/pipeline.py

export function JudgePanel({ draft }: { draft?: Draft }) {
  if (!draft) {
    return (
      <aside className="rounded-2xl border border-night-line bg-night-card/80 p-6 text-sm text-muted">
        <p>Each draft is checked here before you see it: safety, story shape, a calm ending, and how engaging it is.</p>
      </aside>
    );
  }

  return (
    <aside className="rise rounded-2xl border border-night-line bg-night-card/80 p-5 sm:p-6 space-y-6" aria-label="Reviewer results">
      <div className="flex items-center justify-between gap-3">
        <h3 className="text-xs font-semibold uppercase tracking-[0.14em] text-muted">Reviewer</h3>
        <Verdict draft={draft} />
      </div>

      <ul className="space-y-3.5">
        {draft.checks.map((c) => {
          const Icon = c.passed ? CheckCircle : BLOCKING.has(c.name) ? Prohibit : WarningCircle;
          const color = c.passed ? "text-pass" : BLOCKING.has(c.name) ? "text-block" : "text-fail";
          return (
            <li key={c.name} className="flex gap-3">
              <Icon size={20} weight="fill" className={`${color} shrink-0 mt-0.5`} aria-hidden="true" />
              <div className="min-w-0">
                <p className="text-sm font-semibold text-slate-100">
                  {CHECK_LABELS[c.name] ?? c.name}
                  <span className="sr-only">: {c.passed ? "passed" : "failed"}</span>
                </p>
                <p className="text-[0.8rem] leading-relaxed text-muted [overflow-wrap:anywhere]">{c.reason}</p>
              </div>
            </li>
          );
        })}
      </ul>

      <div className="space-y-2.5">
        {Object.entries(draft.scores).map(([name, value]) => (
          <div key={name} className="flex items-center justify-between gap-3">
            <span className="text-sm text-slate-200">{SCORE_LABELS[name] ?? name}</span>
            <span className="flex items-center gap-1" role="img" aria-label={`${value} out of 5`}>
              {[1, 2, 3, 4, 5].map((i) => (
                <span key={i} className={`h-2 w-5 rounded-full ${i <= value ? (value >= 4 ? "bg-pass" : "bg-fail") : "bg-white/10"}`} />
              ))}
              <span className="ml-2 w-7 text-right text-xs tabular-nums text-muted">{value}/5</span>
            </span>
          </div>
        ))}
      </div>

      {draft.code_failures.length > 0 && (
        <div>
          <h4 className="text-xs font-semibold uppercase tracking-[0.14em] text-muted mb-2">Automatic checks</h4>
          <ul className="space-y-1.5 text-[0.8rem] text-fail">
            {draft.code_failures.map((f) => (
              <li key={f} className="[overflow-wrap:anywhere]">{f}</li>
            ))}
          </ul>
        </div>
      )}

      {!draft.passed && draft.notes.length > 0 && (
        <details className="group">
          <summary className="cursor-pointer text-sm font-medium text-moon hover:underline">What the writer was asked to fix</summary>
          <ul className="mt-2 list-disc pl-5 space-y-1.5 text-[0.8rem] text-slate-300">
            {draft.notes.map((n, i) => (
              <li key={i} className="[overflow-wrap:anywhere]">{n}</li>
            ))}
          </ul>
        </details>
      )}
    </aside>
  );
}

function Verdict({ draft }: { draft: Draft }) {
  if (draft.passed) return <Badge className="bg-pass/15 text-pass">Passed</Badge>;
  if (draft.blocked) return <Badge className="bg-block/15 text-block">Held back</Badge>;
  return <Badge className="bg-fail/15 text-fail">Needs another pass</Badge>;
}

function Badge({ children, className }: { children: React.ReactNode; className: string }) {
  return <span className={`rounded-full px-3 py-1 text-xs font-semibold whitespace-nowrap ${className}`}>{children}</span>;
}
