"use client";

/**
 * The shop's mic: it stops by itself when he stops speaking.
 *
 * While it records, the loudness of the mic is read twenty times a second. Once
 * he has spoken (a tenth of a second above the room's own noise), a second of
 * quiet ends the recording. If he says nothing for six seconds it stops and
 * sends nothing. A tap stops it too, and ten seconds is the most it runs.
 *
 * The room's noise is the quietest the mic has been lately, so a shop that is
 * loud to begin with still works, and so does someone who starts talking the
 * moment it opens. Where the browser won't measure (no Web Audio), it falls back
 * to stopping after six seconds.
 *
 * MediaRecorder gives WebM/Opus in Chrome and MP4 in Safari; Sarvam takes both.
 * The mic only works on https or localhost, which is where the shopkeeper's
 * screen runs.
 */

import { useCallback, useEffect, useRef, useState } from "react";

export type MicState = "idle" | "recording" | "blocked" | "unsupported";

const TICK_MS = 50;
/** Loud this long counts as speaking, not a bang or a cough. */
const SPEECH_MS = 100;
/** Quiet this long after speaking ends the recording. */
const SILENCE_MS = 1000;
/** Nothing said this long: stop, send nothing. */
const NO_SPEECH_MS = 6000;
const MAX_MS = 10000;
/** Where Web Audio isn't there to listen with. */
const BLIND_MS = 6000;
/** Speech is this many times the room's noise. */
const OVER_NOISE = 3.5;
const MIN_LEVEL = 0.012;

export function useRecorder(
  onDone: (audio: Blob) => void,
  onNothing: () => void,
): {
  state: MicState;
  start: () => Promise<void>;
  stop: () => void;
  /** Stops and throws the recording away. */
  cancel: () => void;
} {
  const [state, setState] = useState<MicState>("idle");
  const recorder = useRef<MediaRecorder | null>(null);
  const cleanup = useRef<(() => void) | null>(null);
  const discard = useRef(false);

  const stop = useCallback(() => {
    cleanup.current?.();
    cleanup.current = null;
    if (recorder.current?.state === "recording") recorder.current.stop();
  }, []);

  const cancel = useCallback(() => {
    discard.current = true;
    stop();
  }, [stop]);

  // Leaving the screen closes the mic, and sends nothing.
  useEffect(() => cancel, [cancel]);

  const start = useCallback(async () => {
    if (recorder.current?.state === "recording") return;
    if (typeof MediaRecorder === "undefined" || !navigator.mediaDevices?.getUserMedia) {
      setState("unsupported");
      return;
    }
    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch {
      setState("blocked");
      return;
    }

    const rec = new MediaRecorder(stream);
    const chunks: Blob[] = [];
    let spoke = true; // unless the listener below says otherwise
    discard.current = false;
    rec.ondataavailable = (e) => chunks.push(e.data);
    rec.onstop = () => {
      stream.getTracks().forEach((t) => t.stop());
      setState("idle");
      const audio = new Blob(chunks, { type: rec.mimeType || "audio/webm" });
      if (discard.current) return;
      if (!spoke) onNothing();
      else if (audio.size > 0) onDone(audio);
    };
    recorder.current = rec;
    rec.start();
    setState("recording");

    const listener = await listen(stream, () => stop());
    if (listener) {
      spoke = false;
      listener.onSpeech = () => {
        spoke = true;
      };
      cleanup.current = listener.close;
    } else {
      const timer = setTimeout(stop, BLIND_MS);
      cleanup.current = () => clearTimeout(timer);
    }
  }, [onDone, onNothing, stop]);

  return { state, start, stop, cancel };
}

type Listener = { close: () => void; onSpeech: () => void };

/** Watches the mic's loudness and calls `end` when he has finished speaking. */
async function listen(stream: MediaStream, end: () => void): Promise<Listener | null> {
  let ctx: AudioContext;
  try {
    ctx = new AudioContext();
    await ctx.resume();
  } catch {
    return null;
  }
  if (ctx.state !== "running") {
    void ctx.close();
    return null;
  }
  const analyser = ctx.createAnalyser();
  analyser.fftSize = 1024;
  ctx.createMediaStreamSource(stream).connect(analyser);
  const samples = new Float32Array(analyser.fftSize);

  const began = performance.now();
  let noise = Infinity;
  let loudFor = 0;
  let spoke = false;
  let lastLoud = began;

  const listener: Listener = {
    onSpeech: () => undefined,
    close: () => {
      clearInterval(tick);
      void ctx.close();
    },
  };

  const tick = setInterval(() => {
    analyser.getFloatTimeDomainData(samples);
    let sum = 0;
    for (const v of samples) sum += v * v;
    const level = Math.sqrt(sum / samples.length);
    // The room's noise: the quietest lately, creeping up slowly if the room gets louder.
    noise = Math.min(level, noise * 1.015);
    const now = performance.now();
    if (level > Math.max(MIN_LEVEL, noise * OVER_NOISE)) {
      loudFor += TICK_MS;
      lastLoud = now;
      if (!spoke && loudFor >= SPEECH_MS) {
        spoke = true;
        listener.onSpeech();
      }
    } else {
      loudFor = 0;
    }
    const done =
      (spoke && now - lastLoud >= SILENCE_MS) ||
      (!spoke && now - began >= NO_SPEECH_MS) ||
      now - began >= MAX_MS;
    if (done) end();
  }, TICK_MS);

  return listener;
}
