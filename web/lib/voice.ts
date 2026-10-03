"use client";

/**
 * The laptop standing in for the Soundbox: it says the amount back, and asks
 * "kiske liye?". Never a name: the customer's name is shown, never spoken aloud.
 * The API's two routes can only say an amount or that one question.
 *
 * In Sarvam's own voice (bulbul:v3), from the API. The demo's phrases are on
 * disk there, so they play with the wifi off; anything Sarvam can't be asked
 * for falls back to the browser's own Hindi voice. Nothing here turns a number
 * into words: the API does.
 */

import type { Heard } from "@/lib/api/types";

/** What the counter asks, then listens for the answer. Never a name. */
export const QUESTIONS = {
  who: "किसके लिए?",
  how_much: "कितने रुपये?",
  again: "फिर से बोलिए।",
} as const;
export type Question = keyof typeof QUESTIONS;

let playing: HTMLAudioElement | null = null;

/** Stops whatever is being said, before the mic opens. */
export function hush(): void {
  if (typeof window === "undefined") return;
  playing?.pause();
  playing = null;
  if ("speechSynthesis" in window) window.speechSynthesis.cancel();
}

function browserVoice(text: string, done: () => void): void {
  if (!("speechSynthesis" in window)) return done();
  const u = new SpeechSynthesisUtterance(text);
  u.lang = "hi-IN";
  const hindi = window.speechSynthesis.getVoices().find((v) => v.lang.startsWith("hi"));
  if (hindi) u.voice = hindi;
  u.onend = () => done();
  u.onerror = () => done();
  window.speechSynthesis.speak(u);
}

/**
 * Says it, and resolves when it has finished: the mic opens after, so it never
 * hears the counter's own voice. Cut off by something newer, it never resolves.
 */
function play(url: string, words: string): Promise<void> {
  if (typeof window === "undefined") return Promise.resolve();
  hush();
  return new Promise((done) => {
    const audio = new Audio(url);
    playing = audio;
    audio.onended = () => done();
    audio.play().catch(() => {
      if (playing === audio) browserVoice(words, done);
    });
  });
}

/** "दो सौ बीस रुपये", in Sarvam's voice. `words` is the fallback's text. */
export function sayAmount(paise: number, words: string): Promise<void> {
  return play(`/api/voice/say/${paise}.wav`, words);
}

export function ask(question: Question): Promise<void> {
  return play(`/api/voice/ask/${question}.wav`, QUESTIONS[question]);
}

/** Where the words came from, said plainly. A demo clip is never passed off as live. */
export const SOURCE_LABEL: Record<Heard["source"], string> = {
  typed: "Typed",
  sarvam: "Heard by Sarvam",
  sarvam_cached: "Demo clip · Sarvam's transcript, from the offline cache",
  clip_script: "Demo clip · its script (not yet run through Sarvam)",
};

type Reader = Heard["reader"] | NonNullable<Heard["fallback"]>;

/** Who read the words: Sarvam-105B, or our parser and why. */
export const READER_LABEL: Record<Reader, string> = {
  sarvam: "read by Sarvam-105B, checked by our code",
  rules: "read by our parser",
  offline: "voice offline, read by our parser",
  no_answer: "Sarvam-105B didn't answer, read by our parser",
};

export const INTENT_LABEL: Record<Heard["intent"], string> = {
  udhaar: "udhaar",
  payment: "a payment",
  unclear: "udhaar or payment?",
};

/** Why nothing was sent, said plainly. */
export const PROBLEM_LINE: Record<NonNullable<Heard["problem"]>, string> = {
  no_amount: "No amount in that.",
  unclear_amount: "That is not one clear amount.",
  amount_not_said: "Sarvam read an amount that isn't in the words.",
  amount_mismatch: "Sarvam's amount and our parser's don't match.",
  invented_customer: "Sarvam named someone it wasn't shown.",
};

type How = Extract<Heard["who"], { kind: "picked" }>["how"];

/** Why this person, in the words the shopkeeper would use. */
export const HOW_LABEL: Record<How, string> = {
  only_one: "the only one at the counter",
  at_counter: "at the counter",
  in_book: "from your book",
};
