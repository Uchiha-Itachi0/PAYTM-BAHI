"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { Mic } from "@/components/icons";
import { Card } from "@/components/ui/Card";
import { api, ApiError, apiForm } from "@/lib/api/client";
import type { Answer, Clip, Heard } from "@/lib/api/types";
import { SHOP_ID } from "@/lib/config";
import { useRecorder, type MicState } from "@/lib/useRecorder";
import { hush } from "@/lib/voice";

/**
 * Three ways to say it, all ending in the same reading and checks on the server:
 *
 * - the mic, sent to /voice (Sarvam when online);
 * - typing the words, sent to /heard;
 * - a demo clip: played aloud in the room, then sent to /voice like a recording.
 *   Sarvam's transcript of it is on disk, so this works with the wifi off.
 *
 * Arriving from the book's Add udhaar (`?listen=1`), the mic is already open:
 * the tap that brought him here was the tap on the mic.
 *
 * While the screen is asking "किसके लिए?" (`answering`), what he says or types
 * is his answer: it goes to /answer, among the people offered, and the amount
 * stays the one already heard. The screen opens the mic for the answer by
 * changing `listenSignal`, once its own question has finished playing.
 */

const ANSWER_LINE: Record<MicState | "hearing", [string, string]> = {
  idle: ["Tap, then say who it is for", "The name, the surname, or the room"],
  recording: ["Listening… say who it is for", "Stops by itself when you stop speaking"],
  hearing: ["Hearing…", "Looking for them in your book"],
  blocked: ["The mic is blocked", "Allow it in the browser, or tap who it is for"],
  unsupported: ["This browser can't record", "Tap who it is for"],
};

const MIC_LINE: Record<MicState | "hearing", [string, string]> = {
  idle: ["Tap, then say the amount", "Say the name too if several are waiting"],
  recording: ["Listening… say the amount", "Stops by itself when you stop speaking"],
  hearing: ["Hearing…", "Sarvam reads it, our code checks it"],
  blocked: ["The mic is blocked", "Allow it in the browser, or type below"],
  unsupported: ["This browser can't record", "Type below instead"],
};

export function VoicePanel({
  onHeard,
  onAnswer,
  onProblem,
  answering,
  before,
  listenSignal,
}: {
  onHeard: (h: Heard) => void;
  onAnswer: (a: Answer) => void;
  onProblem: (message: string) => void;
  /** Asking who: the customer ids offered, or [] for anyone. null: not asking. */
  answering: string[] | null;
  /** What he said before this, when the screen asked "कितने रुपये?". */
  before: string | null;
  /** Changes when the screen wants the mic opened. */
  listenSignal: number;
}): React.ReactElement {
  const [hearing, setHearing] = useState(false);
  const [text, setText] = useState("");
  const [clips, setClips] = useState<Clip[]>([]);
  const [playing, setPlaying] = useState<string | null>(null);

  useEffect(() => {
    api<Clip[]>("/voice/clips")
      .then(setClips)
      .catch(() => undefined);
  }, []);

  const hearAudio = useCallback(
    async (audio: Blob, filename: string) => {
      setHearing(true);
      try {
        const form = new FormData();
        form.append("audio", audio, filename);
        if (answering) {
          form.append("among", answering.join(","));
          onAnswer(await apiForm<Answer>(`/shops/${SHOP_ID}/answer/voice`, form));
        } else {
          if (before) form.append("before", before);
          onHeard(await apiForm<Heard>(`/shops/${SHOP_ID}/voice`, form));
        }
      } catch (e) {
        onProblem(e instanceof ApiError ? e.message : "Could not hear that. Type it instead.");
      } finally {
        setHearing(false);
      }
    },
    [answering, before, onAnswer, onHeard, onProblem],
  );

  const mic = useRecorder(
    useCallback(
      (audio: Blob) =>
        void hearAudio(audio, audio.type.includes("mp4") ? "speech.mp4" : "speech.webm"),
      [hearAudio],
    ),
    useCallback(
      () =>
        onProblem(
          answering
            ? "Didn't hear a name. Tap who it is for, or tap the mic."
            : "Didn't hear anything. Tap the mic and say the amount.",
        ),
      [answering, onProblem],
    ),
  );
  const { start: startMic, cancel: cancelMic } = mic;

  const listen = useCallback(() => {
    hush();
    void startMic();
  }, [startMic]);

  useEffect(() => {
    const url = new URL(window.location.href);
    if (url.searchParams.get("listen") !== "1") return;
    url.searchParams.delete("listen");
    window.history.replaceState(window.history.state, "", url.pathname + url.search);
    listen();
  }, [listen]);

  // The screen asked something and has finished saying it: listen for the answer.
  const lastSignal = useRef(listenSignal);
  useEffect(() => {
    if (listenSignal === lastSignal.current) return;
    lastSignal.current = listenSignal;
    listen();
  }, [listenSignal, listen]);

  // The question was answered by a tap: an answer still being recorded is moot.
  const asked = answering !== null;
  useEffect(() => {
    if (!asked) cancelMic();
  }, [asked, cancelMic]);

  async function hearText(): Promise<void> {
    const words = text.trim();
    if (!words) return;
    setHearing(true);
    try {
      if (answering) {
        onAnswer(
          await api<Answer>(`/shops/${SHOP_ID}/answer`, { text: words, among: answering }),
        );
      } else {
        onHeard(await api<Heard>(`/shops/${SHOP_ID}/heard`, { text: words, before }));
      }
      setText("");
    } catch (e) {
      onProblem(e instanceof ApiError ? e.message : "Could not read that.");
    } finally {
      setHearing(false);
    }
  }

  async function playClip(clip: Clip): Promise<void> {
    setPlaying(clip.slug);
    try {
      const audio = await (await fetch(`/api/voice/clips/${clip.slug}.wav`)).blob();
      const url = URL.createObjectURL(audio);
      const player = new Audio(url);
      await new Promise<void>((done) => {
        player.onended = () => done();
        player.onerror = () => done();
        player.play().catch(() => done());
      });
      URL.revokeObjectURL(url);
      await hearAudio(audio, `${clip.slug}.wav`);
    } finally {
      setPlaying(null);
    }
  }

  const recording = mic.state === "recording";
  const [line, fine] = (answering ? ANSWER_LINE : MIC_LINE)[hearing ? "hearing" : mic.state];

  return (
    <Card title="Say it" tight>
      <div className="flex items-center gap-3">
        <button
          type="button"
          aria-label={recording ? "Stop" : "Speak"}
          onClick={() => (recording ? mic.stop() : listen())}
          disabled={hearing}
          className={`grid size-14 shrink-0 place-items-center rounded-full text-white shadow-pill disabled:opacity-40 [&_svg]:size-6 ${recording ? "animate-pulse bg-cyan" : "bg-navy"}`}
        >
          <Mic />
        </button>
        <div>
          <p className="text-[14px] font-extrabold tracking-[-0.015em]">{line}</p>
          <p className="mt-0.5 text-[12px] font-medium text-sub">{fine}</p>
        </div>
      </div>

      <form
        className="mt-3 flex gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          void hearText();
        }}
      >
        <input
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="or type it: Anubhav Shukla ko do sau"
          aria-label="What he said"
          className="min-w-0 flex-1 rounded-[11px] border-[1.5px] border-line bg-white px-3 py-2 text-[14px] font-bold outline-none placeholder:font-medium placeholder:text-sub focus:border-cyan"
        />
        <button
          type="submit"
          disabled={!text.trim() || hearing}
          className="rounded-[11px] bg-navy px-3.5 text-[13px] font-extrabold text-white disabled:opacity-40"
        >
          Hear
        </button>
      </form>

      {clips.length ? (
        <div className="mt-3">
          <p className="text-[11.5px] font-semibold text-sub">Demo clips · work offline</p>
          <div className="mt-1.5 flex flex-wrap gap-1.5">
            {clips.map((c) => (
              <button
                key={c.slug}
                type="button"
                title={c.shows}
                onClick={() => void playClip(c)}
                disabled={hearing || playing !== null}
                className="rounded-pill bg-tile px-3 py-1.5 text-[12px] font-bold text-navy-ink disabled:opacity-40"
              >
                {playing === c.slug ? "Playing…" : `▶ ${c.label}`}
              </button>
            ))}
          </div>
        </div>
      ) : null}
    </Card>
  );
}
