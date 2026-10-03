"use client";

/**
 * The Soundbox: what the counter hears. Short tones for "someone scanned",
 * "he said yes", "he says it's wrong" and "a message", and the amount said
 * aloud when money arrives, the way Paytm's Soundbox says "₹200 received".
 *
 * Rule 4: it never says a name. Who it was is on the screen, for the
 * shopkeeper's eyes only.
 *
 * A browser plays sound only after someone has touched the page, so the tones
 * start with the first tap anywhere; until then the screen still shows the news.
 */

export type Tone = "chime" | "question" | "done" | "message";

/** Each tone as notes: [frequency Hz, start s, length s]. */
const NOTES: Record<Tone, [number, number, number][]> = {
  chime: [
    [880, 0, 0.18],
    [1318.5, 0.14, 0.28],
  ],
  question: [
    [659.3, 0, 0.16],
    [880, 0.16, 0.26],
  ],
  done: [
    [784, 0, 0.14],
    [987.8, 0.12, 0.14],
    [1318.5, 0.24, 0.32],
  ],
  message: [[1046.5, 0, 0.16]],
};

let ctx: AudioContext | null = null;

function context(): AudioContext | null {
  if (typeof window === "undefined" || !("AudioContext" in window)) return null;
  ctx ??= new AudioContext();
  return ctx;
}

/** Called once from a tap: the browser now lets the page make sound. */
export function unlock(): void {
  void context()?.resume();
}

export function tone(kind: Tone): void {
  const c = context();
  if (!c || c.state !== "running") return;
  const start = c.currentTime + 0.02;
  for (const [hz, at, length] of NOTES[kind]) {
    const osc = c.createOscillator();
    const gain = c.createGain();
    osc.type = "sine";
    osc.frequency.value = hz;
    gain.gain.setValueAtTime(0, start + at);
    gain.gain.linearRampToValueAtTime(0.22, start + at + 0.015);
    gain.gain.exponentialRampToValueAtTime(0.0001, start + at + length);
    osc.connect(gain).connect(c.destination);
    osc.start(start + at);
    osc.stop(start + at + length + 0.05);
  }
}

/** "दो सौ रुपये", in Sarvam's voice from the API; a chime if it can't be said. */
export function sayAmount(paise: number): void {
  if (!ctx || ctx.state !== "running") return;
  const audio = new Audio(`/api/voice/say/${paise}.wav`);
  audio.play().catch(() => tone("done"));
}
