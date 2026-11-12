import { CheckCircle, CircleNotch, Prohibit, WarningCircle } from "@phosphor-icons/react";
import type { Draft, Stage } from "@/lib/api";

export type Step = { stage: Stage; draft?: Draft };

const LABELS: Record<Stage, string> = {
  reading: "Understanding the request",
  writing: "Writing the first draft",
  reviewing: "Reviewer checking the draft",
  revising: "Rewriting with the reviewer’s notes",
  gentle_retry: "Trying an extra-gentle version",
};

/** Live list of pipeline steps. Story text stays hidden until a draft passes review. */
export function Progress({ steps, title }: { steps: Step[]; title: string }) {
  return (
    <aside className="rounded-2xl border border-night-line bg-night-card/80 p-5 sm:p-6" aria-label="Progress">
      <h3 className="text-xs font-semibold uppercase tracking-[0.14em] text-muted mb-4">{title}</h3>
      <ol className="space-y-3">
        {steps.map((s, i) => {
          const last = i === steps.length - 1;
          const d = s.draft;
          const Icon = !d ? (last ? CircleNotch : CheckCircle) : d.passed ? CheckCircle : d.blocked ? Prohibit : WarningCircle;
          const color = !d ? (last ? "text-moon" : "text-pass") : d.passed ? "text-pass" : d.blocked ? "text-block" : "text-fail";
          const failed = d?.checks.filter((c) => !c.passed).map((c) => c.name.replace(/_/g, " "));
          return (
            <li key={i} className="rise flex gap-3">
              <Icon size={20} weight={!d && last ? "bold" : "fill"} className={`${color} shrink-0 mt-0.5 ${!d && last ? "animate-spin" : ""}`} aria-hidden="true" />
              <div className="min-w-0 text-sm">
                <p className="text-slate-100">{LABELS[s.stage]}</p>
                {d && (
                  <p className="text-[0.8rem] text-muted">
                    {d.passed ? "Passed every check" : d.blocked ? "Not right for bedtime, so it won’t be shown"
                      : `Needs work: ${[...(failed ?? []), ...Object.entries(d.scores).filter(([, v]) => v < 4).map(([k]) => `${k} score`), ...(d.code_failures.length ? ["automatic checks"] : [])].join(", ")}`}
                  </p>
                )}
              </div>
            </li>
          );
        })}
      </ol>
    </aside>
  );
}
