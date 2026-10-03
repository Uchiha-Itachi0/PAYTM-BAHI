"use client";

import { useCallback, useEffect, useState } from "react";

import { Mic } from "@/components/icons";
import { Card } from "@/components/ui/Card";
import { api, ApiError, apiForm } from "@/lib/api/client";
import type { Clip, Heard } from "@/lib/api/types";
import { SHOP_ID } from "@/lib/config";
import { useRecorder, type MicState } from "@/lib/useRecorder";

/**
 * Three ways to say it, all ending in the same reading and checks on the server:
 *
 * - the mic, sent to /voice (Sarvam when online);
 * - typing the words, sent to /heard;
 * - a demo clip: played aloud in the room, then sent to /voice like a recording.
 *   Sarvam's transcript of it is on disk, so this works with the wifi off.
 */

const MIC_LINE: Record<MicState | "hearing", [string, string]> = {
  idle: ["Tap, then say the amount", "Say the name too if several are waiting"],
  recording: ["Listening… tap to stop", "Stops by itself after six seconds"],
  hearing: ["Hearing…", "Sarvam reads it, our code checks it"],
  blocked: ["The mic is blocked", "Allow it in the browser, or type below"],
  unsupported: ["This browser can't record", "Type below instead"],
};

export function VoicePanel({
  onHeard,
  onProblem,
}: {
  onHeard: (h: Heard) => void;
  onProblem: (message: string) => void;
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
        onHeard(await apiForm<Heard>(`/shops/${SHOP_ID}/voice`, form));
      } catch (e) {
        onProblem(e instanceof ApiError ? e.message : "Could not hear that. Type it instead.");
      } finally {
        setHearing(false);
      }
    },
    [onHeard, onProblem],
  );

  const mic = useRecorder(
    useCallback(
      (audio: Blob) =>
        void hearAudio(audio, audio.type.includes("mp4") ? "speech.mp4" : "speech.webm"),
      [hearAudio],
    ),
  );

  async function hearText(): Promise<void> {
    const words = text.trim();
    if (!words) return;
    setHearing(true);
    try {
      onHeard(await api<Heard>(`/shops/${SHOP_ID}/heard`, { text: words }));
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
  const [line, fine] = MIC_LINE[hearing ? "hearing" : mic.state];

  return (
    <Card title="Say it" tight>
      <div className="flex items-center gap-3">
        <button
          type="button"
          aria-label={recording ? "Stop" : "Speak"}
          onClick={() => (recording ? mic.stop() : void mic.start())}
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
