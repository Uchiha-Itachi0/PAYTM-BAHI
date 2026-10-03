"use client";

/**
 * The shop's mic: tap to start, tap to stop, and at most a few seconds.
 *
 * MediaRecorder gives WebM/Opus in Chrome and MP4 in Safari; Sarvam takes both.
 * The mic only works on https or localhost, which is where the shopkeeper's
 * screen runs.
 */

import { useCallback, useRef, useState } from "react";

export type MicState = "idle" | "recording" | "blocked" | "unsupported";

const MAX_MS = 6000;

export function useRecorder(onDone: (audio: Blob) => void): {
  state: MicState;
  start: () => Promise<void>;
  stop: () => void;
} {
  const [state, setState] = useState<MicState>("idle");
  const recorder = useRef<MediaRecorder | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const stop = useCallback(() => {
    if (timer.current) clearTimeout(timer.current);
    if (recorder.current?.state === "recording") recorder.current.stop();
  }, []);

  const start = useCallback(async () => {
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
    rec.ondataavailable = (e) => chunks.push(e.data);
    rec.onstop = () => {
      stream.getTracks().forEach((t) => t.stop());
      setState("idle");
      const audio = new Blob(chunks, { type: rec.mimeType || "audio/webm" });
      if (audio.size > 0) onDone(audio);
    };
    recorder.current = rec;
    rec.start();
    setState("recording");
    timer.current = setTimeout(stop, MAX_MS);
  }, [onDone, stop]);

  return { state, start, stop };
}
