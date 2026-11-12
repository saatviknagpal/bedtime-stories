export type AgeBand = "5-7" | "8-10";
export type Intake = { age_band: AgeBand; category: string; brief: string };
export type Check = { name: string; passed: boolean; reason: string };
export type Draft = {
  story: string | null; // null when the draft failed a safety check (the server never sends that text)
  passed: boolean;
  blocked: boolean;
  checks: Check[];
  scores: Record<string, number>;
  code_failures: string[];
  notes: string[];
};
export type Status = "passed" | "flagged" | "blocked";

export type Stage = "reading" | "writing" | "reviewing" | "revising" | "gentle_retry";

export type StoryEvent =
  | { type: "stage"; stage: Stage }
  | { type: "intake"; intake: Intake }
  | { type: "draft"; draft: Draft }
  | { type: "done"; status: Status | null; best: number | null; request: string; error?: string | null; applied?: boolean }
  | { type: "error"; message: string };

/** POST to a streaming endpoint and call onEvent for each Server-Sent Event, ending with `done` or `error`. */
export async function stream(path: string, body: unknown, onEvent: (e: StoryEvent) => void, signal?: AbortSignal) {
  const res = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  });
  if (!res.ok || !res.body) {
    const detail =
      res.status === 422 ? "Please check your request (it may be too long)."
      : res.status === 429 || res.status === 503 ? ((await res.json().catch(() => null))?.detail ?? "Please try again later.")
      : `Server error (${res.status}).`;
    onEvent({ type: "error", message: detail });
    return;
  }
  const reader = res.body.pipeThrough(new TextDecoderStream()).getReader();
  let buffer = "";
  let finished = false;
  const handle = (frame: string) => {
    const data = frame.split(/\r?\n/).filter((l) => l.startsWith("data: ")).map((l) => l.slice(6)).join("\n");
    if (!data) return;
    const event = JSON.parse(data) as StoryEvent;
    if (event.type === "done" || event.type === "error") finished = true;
    onEvent(event);
  };
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += value;
    const frames = buffer.split(/\r?\n\r?\n/);
    buffer = frames.pop() ?? "";
    frames.forEach(handle);
  }
  if (buffer.trim()) handle(buffer);
  if (!finished) onEvent({ type: "error", message: "The connection closed before the story was finished. Please try again." });
}

export const CHECK_LABELS: Record<string, string> = {
  safe: "Safe for bedtime",
  follows_request: "Follows the request",
  age_fit: "Right for the age",
  clear_arc: "Beginning, middle, end",
  single_thread: "One simple plot",
  calm_ending: "Calm, sleepy ending",
  story_only: "Just the story",
};

export const SCORE_LABELS: Record<string, string> = {
  engagement: "Engaging",
  soothing: "Soothing",
  care: "Emotional care",
};

/** Split a story into its title (first line) and paragraphs. */
export function splitStory(text: string): { title: string; paragraphs: string[] } {
  const lines = text.trim().split("\n");
  const first = (lines[0] ?? "").replace(/^[#*\s]+|[*\s]+$/g, "");
  const hasTitle = lines.length > 1 && first.split(/\s+/).length <= 12 && !/[.:,]$/.test(first);
  const body = (hasTitle ? lines.slice(1) : lines).join("\n").trim();
  return {
    title: hasTitle ? first : "",
    paragraphs: body.split(/\n\s*\n/).map((p) => p.replace(/\*/g, "").trim()).filter(Boolean),
  };
}
