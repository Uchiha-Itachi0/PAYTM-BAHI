"use client";

/**
 * The munshi's voice: its sentences, in Sarvam's own voice (bulbul:v3, shreya),
 * from the API. It can name a customer when the shopkeeper asked it to read names
 * out. If Sarvam can't be asked, the browser's own Hindi voice says it instead.
 * Nothing here turns a number into words: the API does.
 */

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

/** A sentence never takes longer than this to say; past it, the mic opens anyway. */
const LONGEST_MS = 15000;

/**
 * Says it, and resolves when it has finished: the mic opens after, so it never
 * hears the counter's own voice. Cut off by something newer, it never resolves.
 * If neither Sarvam's audio nor the browser's voice reports an end (a blocked
 * speaker, a browser without voices), it resolves after LONGEST_MS, so the
 * conversation never waits on a sentence forever.
 */
function play(url: string, words: string): Promise<void> {
  if (typeof window === "undefined") return Promise.resolve();
  hush();
  return new Promise((resolve) => {
    const audio = new Audio(url);
    playing = audio;
    let over = false;
    const done = (): void => {
      if (over) return;
      over = true;
      clearTimeout(timer);
      resolve();
    };
    const timer = setTimeout(() => {
      if (playing === audio) done();
    }, LONGEST_MS);
    audio.onended = () => done();
    audio.play().catch(() => {
      if (playing === audio) browserVoice(words, done);
    });
  });
}

/**
 * The munshi's own sentence, in Sarvam's voice. It may name a customer: the
 * munshi reads names only when the shopkeeper asked it to. `path` is the API's
 * say_url; `words` is the fallback's text.
 */
export function sayLine(path: string, words: string): Promise<void> {
  return play(`/api${path}`, words);
}
