"use client";

/**
 * The munshi's voice: its sentences, in Sarvam's own voice (bulbul:v3, shreya),
 * from the API. It can name a customer when the shopkeeper asked it to read names
 * out. If Sarvam can't say it, the browser's own Hindi voice says it instead.
 * Nothing here turns a number into words: the API does.
 */

let playing: HTMLAudioElement | null = null;
/** Bumped by every hush(): whatever was being said before it no longer counts,
 *  so it can't finish and open the mic in the middle of something newer. */
let turn = 0;
/** Tells the sentence being said that it was cut off. */
let cutOff: (() => void) | null = null;

/** Stops whatever is being said, before the mic opens. */
export function hush(): void {
  if (typeof window === "undefined") return;
  turn += 1;
  const cut = cutOff;
  cutOff = null;
  cut?.();
  playing?.pause();
  playing = null;
  if ("speechSynthesis" in window) window.speechSynthesis.cancel();
}

/** The API says a long sentence in pieces within ten seconds, or answers 503.
 *  Past this, the sentence isn't coming. */
const START_MS = 15000;
/** Once it plays, it ends when its own length says; this is the slack before
 *  we stop waiting for the audio to report it. */
const GRACE_MS = 1500;
/** The browser's voice reports its end unreliably; no sentence takes longer
 *  than this a character. */
const BROWSER_MS_PER_CHAR = 120;

function browserVoice(text: string, current: () => boolean, done: () => void): void {
  if (!("speechSynthesis" in window)) return done();
  const finish = (): void => {
    if (current()) done();
  };
  // A sentence at a time: Chrome stops a long utterance part way through.
  const parts = text.split(/(?<=[।.?!;])\s+/).filter((p) => p.trim());
  const hindi = window.speechSynthesis.getVoices().find((v) => v.lang.startsWith("hi"));
  parts.forEach((part, i) => {
    const u = new SpeechSynthesisUtterance(part);
    u.lang = "hi-IN";
    if (hindi) u.voice = hindi;
    if (i === parts.length - 1) u.onend = finish;
    u.onerror = finish;
    window.speechSynthesis.speak(u);
  });
  setTimeout(finish, 3000 + text.length * BROWSER_MS_PER_CHAR);
}

/**
 * Says it, and resolves true when it has finished: the mic opens after, so it
 * never hears the counter's own voice, and never opens while the munshi is still
 * talking. Cut off by something newer (hush), it resolves false at once, and the
 * caller leaves the mic to whatever cut it off. If the audio never starts or never
 * reports its end (a blocked speaker), it resolves after START_MS, or the
 * sentence's own length, so the conversation never waits forever.
 */
function play(url: string, words: string): Promise<boolean> {
  if (typeof window === "undefined") return Promise.resolve(true);
  hush();
  const mine = turn;
  const current = (): boolean => turn === mine;
  return new Promise((resolve) => {
    const audio = new Audio(url);
    playing = audio;
    let over = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const settle = (finished: boolean): void => {
      if (over) return;
      over = true;
      clearTimeout(timer);
      if (cutOff === cut) cutOff = null;
      resolve(finished);
    };
    const cut = (): void => settle(false);
    cutOff = cut;
    const done = (): void => {
      if (current()) settle(true);
    };
    const waitFor = (ms: number): void => {
      clearTimeout(timer);
      timer = setTimeout(done, ms);
    };
    const instead = (): void => {
      if (over || !current()) return;
      clearTimeout(timer);
      playing = null;
      browserVoice(words, current, done);
    };
    waitFor(START_MS);
    audio.onplaying = () => {
      const left = Number.isFinite(audio.duration)
        ? (audio.duration - audio.currentTime) * 1000
        : START_MS;
      waitFor(left + GRACE_MS);
    };
    audio.onended = done;
    audio.onerror = instead;
    audio.play().catch(instead);
  });
}

/**
 * The munshi's own sentence, in Sarvam's voice. It may name a customer: the
 * munshi reads names only when the shopkeeper asked it to. `path` is the API's
 * say_url; `words` is the fallback's text. False: he cut it off.
 */
export function sayLine(path: string, words: string): Promise<boolean> {
  return play(`/api${path}`, words);
}
