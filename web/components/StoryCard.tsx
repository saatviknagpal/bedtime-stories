"use client";

import { useEffect, useState } from "react";
import { SpeakerHigh, Stop } from "@phosphor-icons/react";
import { splitStory } from "@/lib/api";

const TOKENS_PER_TICK = 4; // 2 words + their spaces every 40ms (~50 words/s)

/** Reveal reviewed text word by word; instant with reduced motion; can be skipped. */
function useTypewriter(text: string, animate: boolean) {
  const total = text.split(/(\s+)/).length;
  const [shown, setShown] = useState(animate ? 0 : total);

  useEffect(() => {
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    setShown(animate && !reduce ? 0 : total);
  }, [text, animate, total]);

  useEffect(() => {
    if (shown >= total) return; // stop ticking once everything is visible
    const id = setTimeout(() => setShown((n) => Math.min(n + TOKENS_PER_TICK, total)), 40);
    return () => clearTimeout(id);
  }, [shown, total]);

  return { visible: text.split(/(\s+)/).slice(0, shown).join(""), done: shown >= total, finish: () => setShown(total) };
}

export function StoryCard({ text, animate }: { text: string; animate: boolean }) {
  const { visible, done, finish } = useTypewriter(text, animate);
  const { title, paragraphs } = splitStory(visible);
  const full = splitStory(text);
  return (
    <article
      onClick={finish}
      className="relative rounded-2xl bg-paper text-ink shadow-[0_20px_60px_-20px_rgb(0_0_0/0.6)] px-6 py-7 sm:px-10 sm:py-9"
    >
      {/* Screen readers get the whole story at once instead of a stream of partial updates. */}
      <div className="sr-only">{[full.title, ...full.paragraphs].join("\n\n")}</div>
      <div aria-hidden="true">
        {title && <h2 className="font-story text-2xl sm:text-3xl font-semibold leading-tight mb-5 text-balance">{title}</h2>}
        <div className="font-story text-[1.075rem] sm:text-lg leading-[1.8] space-y-4 max-w-[65ch]">
          {paragraphs.map((p, i) => (
            <p key={i}>{p}</p>
          ))}
        </div>
      </div>
      {!done && (
        <button type="button" onClick={finish}
          className="mt-6 rounded-full border border-ink/20 px-3 py-1.5 text-xs text-ink/70 hover:bg-ink/5 cursor-pointer">
          Show the whole story
        </button>
      )}
    </article>
  );
}

export function ReadAloud({ text }: { text: string }) {
  const [speaking, setSpeaking] = useState(false);
  useEffect(() => () => window.speechSynthesis?.cancel(), []);
  if (typeof window !== "undefined" && !("speechSynthesis" in window)) return null;

  const toggle = () => {
    const synth = window.speechSynthesis;
    if (speaking) {
      synth.cancel();
      setSpeaking(false);
      return;
    }
    const { title, paragraphs } = splitStory(text);
    const u = new SpeechSynthesisUtterance([title, ...paragraphs].join(". "));
    u.rate = 0.88; // a slower, bedtime pace
    u.onend = u.onerror = () => setSpeaking(false);
    synth.speak(u);
    setSpeaking(true);
  };

  return (
    <button
      type="button"
      onClick={toggle}
      aria-pressed={speaking}
      className="inline-flex items-center gap-2 rounded-full border border-white/15 px-4 py-2 text-sm font-medium text-slate-100 hover:bg-white/10 cursor-pointer transition-colors min-h-11"
    >
      {speaking ? <Stop size={18} weight="fill" aria-hidden="true" /> : <SpeakerHigh size={18} aria-hidden="true" />}
      {speaking ? "Stop reading" : "Read aloud"}
    </button>
  );
}
