"use client";

/**
 * The laptop standing in for the Soundbox: it says the amount back, and asks
 * "kiske liye?". Never a name: the customer's name is shown, never spoken aloud.
 *
 * The browser's own Hindi voice, so it works with the wifi off. The words come
 * from the API (`readback.devanagari`); nothing here turns a number into speech.
 */

import type { Heard } from "@/lib/api/types";

export function sayAloud(text: string): void {
  if (typeof window === "undefined" || !("speechSynthesis" in window)) return;
  const u = new SpeechSynthesisUtterance(text);
  u.lang = "hi-IN";
  const hindi = window.speechSynthesis.getVoices().find((v) => v.lang.startsWith("hi"));
  if (hindi) u.voice = hindi;
  window.speechSynthesis.cancel();
  window.speechSynthesis.speak(u);
}

export const KISKE_LIYE = "किसके लिए?";

/** Where the words came from, said plainly. A demo clip is never passed off as live. */
export const SOURCE_LABEL: Record<Heard["source"], string> = {
  typed: "Typed",
  sarvam: "Heard by Sarvam",
  sarvam_cached: "Demo clip · Sarvam's transcript, from the offline cache",
  clip_script: "Demo clip · its script (not yet run through Sarvam)",
};

type How = Extract<Heard["who"], { kind: "picked" }>["how"];

/** Why this person, in the words the shopkeeper would use. */
export const HOW_LABEL: Record<How, string> = {
  only_one: "the only one at the counter",
  at_counter: "at the counter",
  in_book: "from your book",
};

/** "from voice" or "typed": which way the words came in. */
export function via(source: Heard["source"]): string {
  return source === "typed" ? "typed" : "from voice";
}
