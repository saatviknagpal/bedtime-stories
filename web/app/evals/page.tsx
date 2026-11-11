"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowLeft, MoonStars } from "@phosphor-icons/react";
import { CHECK_LABELS } from "@/lib/api";

type Row = {
  id: string; kind: string; request: string; status: string; rounds: number; first_passed: boolean;
  failed_checks: string[]; scores: Record<string, number>; words: number; grade: number; secs: number;
};
type Golden = { case: string; flaw: string; caught_each: boolean[] };
type Pair = { case: string; outcome: "win" | "tie" | "loss" };
type Evals = { run: string; cost_usd: number; rows: Row[]; golden: Golden[] | null; pairwise: Pair[] | null };

const FLAW_LABELS: Record<string, string> = {
  scary: "Scary scene (monster, blood)",
  cliffhanger: "Cliffhanger ending",
  refusal_opener: "“I can’t write that…” opener",
  subplot: "Unrelated subplot",
  hard_words: "Paragraph of hard words",
  wrong_story: "Story for a different request",
  control: "Untouched good story (should pass)",
};

const pct = (n: number, d: number) => (d ? `${Math.round((100 * n) / d)}%` : "–");

export default function EvalsPage() {
  const [data, setData] = useState<Evals | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    fetch("/api/evals").then((r) => r.json()).then(setData).catch(() => setError("Couldn’t load results."));
  }, []);

  const rows = data?.rows ?? [];
  const passed = rows.filter((r) => r.status === "passed").length;
  const firstPassed = rows.filter((r) => r.first_passed).length;
  const blocked = rows.filter((r) => r.status === "blocked").length;
  const wins = data?.pairwise?.filter((p) => p.outcome === "win").length ?? 0;
  const flaws = Object.keys(FLAW_LABELS).map((flaw) => {
    const xs = data?.golden?.filter((g) => g.flaw === flaw) ?? [];
    return { flaw, caught: xs.filter((x) => x.caught_each[0]).length, total: xs.length };
  });

  return (
    <main className="mx-auto max-w-6xl px-4 sm:px-6 pb-20">
      <header className="flex items-center justify-between py-6">
        <Link href="/" className="flex items-center gap-2.5 text-lg font-semibold tracking-wide text-slate-100">
          <MoonStars size={28} weight="duotone" className="text-moon" aria-hidden="true" />
          Bedtime Stories
        </Link>
        <Link href="/" className="inline-flex items-center gap-2 rounded-full px-4 py-2 text-sm text-muted hover:text-slate-100 hover:bg-white/5 transition-colors min-h-11">
          <ArrowLeft size={18} aria-hidden="true" /> Back to stories
        </Link>
      </header>

      <section className="pt-4 pb-8">
        <h1 className="font-story text-3xl sm:text-4xl font-semibold text-slate-50">How the stories are tested</h1>
        <p className="mt-3 max-w-3xl text-slate-300">
          Every story goes through a writer, an AI reviewer, and automatic checks. These are the results of running the
          whole system on 20 test requests, plus a test of whether the reviewer catches problems we planted on purpose.
        </p>
        {data?.run && <p className="mt-2 text-xs text-muted">Run {data.run} · total cost ${data.cost_usd.toFixed(3)}</p>}
      </section>

      {error && <p className="text-block" role="alert">{error}</p>}
      {!data && !error && <p className="text-muted animate-pulse">Loading results…</p>}

      {data && (
        <div className="space-y-10">
          <div className="grid gap-4 grid-cols-2 lg:grid-cols-4">
            <Stat label="Passed review" value={`${passed}/${rows.length}`} note="after up to 2 rewrites" />
            <Stat label="Passed on first draft" value={`${firstPassed}/${rows.length}`} note="before any rewrite" />
            <Stat label="Stories blocked" value={`${blocked}`} note="withheld as not safe; scary and trick requests were softened instead" />
            <Stat label="Rewrite beat first draft" value={data.pairwise ? `${wins}/${data.pairwise.length}` : "–"} note="judged side by side, both orders" />
          </div>

          {data.golden && (
            <Card title="Does the reviewer catch real problems?" subtitle="We took stories that passed, planted one problem in each, and asked the reviewer again.">
              <table className="w-full text-sm">
                <thead className="text-left text-muted">
                  <tr><th className="py-2 font-medium">Planted problem</th><th className="py-2 font-medium text-right">Caught</th></tr>
                </thead>
                <tbody>
                  {flaws.map((f) => (
                    <tr key={f.flaw} className="border-t border-night-line">
                      <td className="py-2.5 text-slate-200">{FLAW_LABELS[f.flaw]}</td>
                      <td className="py-2.5 text-right tabular-nums text-slate-100">{f.caught}/{f.total} <span className="text-muted">({pct(f.caught, f.total)})</span></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Card>
          )}

          <Card title="Every test request" subtitle="Normal, tricky, unsafe, rule-breaking, and sensitive requests.">
            <div className="overflow-x-auto -mx-2">
              <table className="w-full min-w-[720px] text-sm">
                <thead className="text-left text-muted">
                  <tr>
                    {["Request", "Type", "Result", "Drafts", "Words", "Grade", "Time"].map((h) => (
                      <th key={h} className="px-2 py-2 font-medium">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r) => (
                    <tr key={r.id} className="border-t border-night-line align-top">
                      <td className="px-2 py-2.5 text-slate-200 max-w-[320px]">{r.request}</td>
                      <td className="px-2 py-2.5 text-muted capitalize">{r.kind}</td>
                      <td className="px-2 py-2.5">
                        <span className={r.status === "passed" ? "text-pass" : r.status === "blocked" ? "text-block" : "text-fail"}>{r.status}</span>
                        {r.failed_checks.length > 0 && (
                          <span className="block text-xs text-muted">{r.failed_checks.map((c) => CHECK_LABELS[c] ?? c).join(", ")}</span>
                        )}
                      </td>
                      <td className="px-2 py-2.5 tabular-nums text-slate-300">{r.rounds}</td>
                      <td className="px-2 py-2.5 tabular-nums text-slate-300">{r.words}</td>
                      <td className="px-2 py-2.5 tabular-nums text-slate-300">{r.grade}</td>
                      <td className="px-2 py-2.5 tabular-nums text-slate-300">{Math.round(r.secs)}s</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        </div>
      )}
    </main>
  );
}

function Stat({ label, value, note }: { label: string; value: string; note: string }) {
  return (
    <div className="rounded-2xl border border-night-line bg-night-card/80 p-5">
      <p className="text-sm text-muted">{label}</p>
      <p className="mt-1 font-story text-3xl font-semibold tabular-nums text-slate-50">{value}</p>
      <p className="mt-1 text-xs text-muted">{note}</p>
    </div>
  );
}

function Card({ title, subtitle, children }: { title: string; subtitle: string; children: React.ReactNode }) {
  return (
    <section className="rounded-2xl border border-night-line bg-night-card/80 p-5 sm:p-6">
      <h2 className="text-lg font-semibold text-slate-100">{title}</h2>
      <p className="mt-1 mb-4 text-sm text-muted">{subtitle}</p>
      {children}
    </section>
  );
}
