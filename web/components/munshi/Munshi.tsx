"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { Mic } from "@/components/icons";
import { EntryCard } from "@/components/munshi/EntryCard";
import { Card } from "@/components/ui/Card";
import { api, ApiError, apiForm } from "@/lib/api/client";
import type { Munshi as Turn, MunshiCard } from "@/lib/api/types";
import { SHOP_ID } from "@/lib/config";
import { useRecorder } from "@/lib/useRecorder";
import { hush, sayLine } from "@/lib/voice";

/**
 * A2 · The munshi: talk or type, it finds, asks and proposes; you approve.
 *
 * One conversation. What he says or types goes to the munshi (Sarvam's model with
 * tools, on the server); its reply is shown and said in Sarvam's voice, and the
 * mic opens again once it has finished speaking, unless the entry is done. When
 * it proposes an entry, the card shows the stored amount. An ordinary one goes in
 * three seconds unless he says or taps no (the countdown stops the moment he
 * starts speaking); one with reasons waits for a clear हाँ. Nothing is written
 * until then, and the book does the writing.
 *
 * Arriving from the book's Add udhaar (`listen`), the mic is already open.
 */

type Line = { key: string; who: "you" | "munshi"; text: string; done?: string[] };

const LINE: Record<"idle" | "recording" | "thinking" | "speaking", [string, string]> = {
  idle: ["Tap and talk to your munshi", "Or type below, in any words"],
  recording: ["Listening…", "Stops by itself when you stop speaking"],
  thinking: ["Munshi is looking…", "Finding them in your book"],
  speaking: ["Munshi is speaking…", "The mic opens when it's done"],
};

export function Munshi({
  listen,
  onWritten,
}: {
  /** Open the mic straight away. */
  listen: boolean;
  /** An entry was written: the counter and the book have moved. */
  onWritten: () => void;
}): React.ReactElement {
  // A ref, not state: the mic can reopen before React has re-rendered, and the
  // next turn must still land in this conversation.
  const conversation = useRef<string | null>(null);
  const [lines, setLines] = useState<Line[]>([]);
  const [card, setCard] = useState<MunshiCard | null>(null);
  const [counting, setCounting] = useState(false);
  const [busy, setBusy] = useState(false);
  const [speaking, setSpeaking] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const [text, setText] = useState("");
  const thread = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    thread.current?.scrollTo({ top: thread.current.scrollHeight });
  }, [lines, card]);

  const listenAgain = useRef<() => void>(() => undefined);

  const take = useCallback(
    async (out: Turn): Promise<void> => {
      conversation.current = out.conversation_id;
      const said: Line[] = [];
      if (out.heard) said.push({ key: `you-${Date.now()}`, who: "you", text: out.heard });
      if (out.reply)
        said.push({ key: `m-${Date.now()}`, who: "munshi", text: out.reply, done: out.done });
      setLines((l) => [...l, ...said]);
      setCard(out.card ?? null);
      setCounting(false);
      if (out.finished && out.card?.status === "saved") onWritten();

      if (out.reply && out.say_url) {
        setSpeaking(true);
        await sayLine(out.say_url, out.reply);
        setSpeaking(false);
      }
      const waiting = out.card?.status === "shown";
      if (waiting && out.card?.reasons.length === 0) setCounting(true);
      if (!out.finished) listenAgain.current();
    },
    [onWritten],
  );

  const failed = useCallback((e: unknown) => {
    setProblem(e instanceof ApiError ? e.message : "The munshi couldn't be reached.");
  }, []);

  const sendAudio = useCallback(
    async (audio: Blob) => {
      setBusy(true);
      setProblem(null);
      try {
        const form = new FormData();
        form.append("audio", audio, audio.type.includes("mp4") ? "speech.mp4" : "speech.webm");
        if (conversation.current) form.append("conversation_id", conversation.current);
        const out = await apiForm<Turn>(`/shops/${SHOP_ID}/munshi/voice`, form);
        setBusy(false);
        await take(out);
      } catch (e) {
        setBusy(false);
        failed(e);
      }
    },
    [failed, take],
  );

  const mic = useRecorder(
    useCallback((audio: Blob) => void sendAudio(audio), [sendAudio]),
    useCallback(() => undefined, []),
    // He started speaking: whatever he says now decides the card, not the countdown.
    useCallback(() => setCounting(false), []),
  );
  const { start: startMic, cancel: cancelMic } = mic;

  const open = useCallback(() => {
    hush();
    void startMic();
  }, [startMic]);
  useEffect(() => {
    listenAgain.current = open;
  }, [open]);

  useEffect(() => {
    if (listen) open();
    // Only on arrival: later openings follow the conversation.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function sendText(): Promise<void> {
    const words = text.trim();
    if (!words || busy) return;
    cancelMic();
    hush();
    setBusy(true);
    setProblem(null);
    try {
      const out = await api<Turn>(`/shops/${SHOP_ID}/munshi`, {
        text: words,
        conversation_id: conversation.current,
      });
      setText("");
      setBusy(false);
      await take(out);
    } catch (e) {
      setBusy(false);
      failed(e);
    }
  }

  async function answer(yes: boolean): Promise<void> {
    const cid = conversation.current;
    if (!card || !cid || busy) return;
    cancelMic();
    hush();
    setCounting(false);
    setBusy(true);
    try {
      const out = await api<Turn>(
        `/shops/${SHOP_ID}/munshi/${cid}/cards/${card.draft_id}/${yes ? "yes" : "no"}`,
        {},
      );
      setBusy(false);
      await take(out);
    } catch (e) {
      setBusy(false);
      failed(e);
    }
  }

  const recording = mic.state === "recording";
  const state = busy ? "thinking" : speaking ? "speaking" : recording ? "recording" : "idle";
  const [line, fine] = LINE[state];

  return (
    <Card title="Munshi" tight>
      {lines.length ? (
        <div ref={thread} className="mb-3 flex max-h-[340px] flex-col gap-2 overflow-y-auto">
          {lines.map((l) =>
            l.who === "you" ? (
              <p
                key={l.key}
                className="max-w-[85%] self-end rounded-card rounded-br-[5px] bg-navy px-3 py-2 text-[14px] font-semibold text-white"
              >
                {l.text}
              </p>
            ) : (
              <div key={l.key} className="max-w-[88%] self-start">
                <p className="rounded-card rounded-bl-[5px] bg-tile px-3 py-2 text-[14.5px] font-semibold">
                  {l.text}
                </p>
                {l.done?.length ? (
                  <p className="mt-1 px-1 text-[11px] font-medium text-sub">{l.done.join(" · ")}</p>
                ) : null}
              </div>
            ),
          )}
        </div>
      ) : null}

      {card ? (
        <div className="mb-3">
          <EntryCard
            card={card}
            counting={counting}
            busy={busy}
            onYes={() => void answer(true)}
            onNo={() => void answer(false)}
          />
        </div>
      ) : null}

      {problem ? (
        <p className="mb-3 text-[12.5px] font-semibold text-warn" role="alert">
          {problem}
        </p>
      ) : null}

      <div className="flex items-center gap-3">
        <button
          type="button"
          aria-label={recording ? "Stop" : "Speak"}
          onClick={() => (recording ? mic.stop() : open())}
          disabled={busy}
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
          void sendText();
        }}
      >
        <input
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="or type: B wing wale Sharma ji ko do sau"
          aria-label="Type to the munshi"
          className="min-w-0 flex-1 rounded-[11px] border-[1.5px] border-line bg-white px-3 py-2 text-[14px] font-bold outline-none placeholder:font-medium placeholder:text-sub focus:border-cyan"
        />
        <button
          type="submit"
          disabled={!text.trim() || busy}
          className="rounded-[11px] bg-navy px-3.5 text-[13px] font-extrabold text-white disabled:opacity-40"
        >
          Send
        </button>
      </form>
    </Card>
  );
}
