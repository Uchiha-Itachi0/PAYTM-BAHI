"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { Mic } from "@/components/icons";
import { type CardEdit, EntryCard } from "@/components/munshi/EntryCard";
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
 * mic opens again once it has finished speaking (all of it, however long),
 * unless the entry is done or he cut in first. When
 * it proposes an entry, the card shows the stored amount. An ordinary one goes in
 * three seconds unless he says or taps no (the countdown stops the moment he
 * starts speaking); one with reasons waits for a clear हाँ. Nothing is written
 * until then, and the book does the writing.
 *
 * Arriving from the book's Add udhaar (`listen`), the mic is already open.
 *
 * `full`: the whole page is the conversation (Paytm Assistant). The thread grows
 * down the page, the mic and the box stay at the bottom, and before the first
 * question a few `starters` are offered; tapping one asks it.
 */

type Line = { key: string; who: "you" | "munshi"; text: string; done?: string[] };

const LINE: Record<
  "idle" | "recording" | "thinking" | "speaking" | "blocked",
  [string, string]
> = {
  idle: ["Tap and talk to your munshi", "Or type below, in any words"],
  blocked: ["Allow the microphone", "The browser said no to the mic. Allow it, then tap"],
  recording: ["Listening…", "Stops by itself when you stop speaking"],
  thinking: ["Munshi is looking…", "Finding them in your book"],
  speaking: ["Munshi is speaking…", "The mic opens when it's done"],
};

export function Munshi({
  listen,
  onWritten,
  full = false,
  starters = [],
}: {
  /** Open the mic straight away. */
  listen: boolean;
  /** An entry was written: the counter and the book have moved. */
  onWritten: () => void;
  /** The conversation is the whole page. */
  full?: boolean;
  /** Questions to offer before the first one. */
  starters?: string[];
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
    // On its own page, the page scrolls; in the card, the thread does.
    if (full) window.scrollTo({ top: document.body.scrollHeight, behavior: "smooth" });
    else thread.current?.scrollTo({ top: thread.current.scrollHeight });
  }, [lines, card, full]);

  const listenAgain = useRef<() => void>(() => undefined);
  // The mic opened by itself (after a reply, or on arrival), not by his tap. If
  // it then hears only silence, it closes quietly: no "didn't catch" warning
  // for words he never meant to say.
  const byItself = useRef(false);
  // On its own page, the mic opens again after a reply only if he asked by
  // voice: a typed question is answered, and the page waits.
  const byVoice = useRef(false);

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
        const finished = await sayLine(out.say_url, out.reply);
        setSpeaking(false);
        // He cut in (the mic, a tap, an edit): what he did next decides.
        if (!finished) return;
      }
      const waiting = out.card?.status === "shown";
      if (waiting && out.card?.reasons.length === 0) setCounting(true);
      if (!out.finished && (!full || byVoice.current)) listenAgain.current();
    },
    [onWritten, full],
  );

  const failed = useCallback((e: unknown) => {
    setProblem(e instanceof ApiError ? e.message : "The munshi couldn't be reached.");
  }, []);

  const sendAudio = useCallback(
    async (audio: Blob) => {
      byVoice.current = true;
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
        if (byItself.current && e instanceof ApiError && e.status === 422) return;
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
    listenAgain.current = () => {
      byItself.current = true;
      open();
    };
  }, [open]);

  useEffect(() => {
    if (listen) listenAgain.current();
    // Only on arrival: later openings follow the conversation.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function sendText(asked?: string): Promise<void> {
    const words = (asked ?? text).trim();
    if (!words || busy) return;
    byVoice.current = false;
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

  /** He fixed the card on screen: no model, no speech, and no countdown after:
   *  a card he changed waits for his tap. */
  async function edit(change: CardEdit): Promise<void> {
    const cid = conversation.current;
    if (!card || !cid) return;
    setBusy(true);
    setProblem(null);
    try {
      const out = await api<Turn>(
        `/shops/${SHOP_ID}/munshi/${cid}/cards/${card.draft_id}/edit`,
        change,
      );
      setCard(out.card ?? null);
      setCounting(false);
    } catch (e) {
      failed(e);
    } finally {
      setBusy(false);
    }
  }

  const recording = mic.state === "recording";
  const state = busy
    ? "thinking"
    : speaking
      ? "speaking"
      : recording
        ? "recording"
        : mic.state === "blocked"
          ? "blocked"
          : "idle";
  const [line, fine] = LINE[state];

  const thread_ = lines.length ? (
    <div
      ref={thread}
      className={`flex flex-col gap-2 ${full ? "pb-3" : "mb-3 max-h-[340px] overflow-y-auto"}`}
    >
      {lines.map((l) =>
        l.who === "you" ? (
          <p
            key={l.key}
            className="max-w-[85%] self-end rounded-card rounded-br-[5px] bg-av-blue px-3.5 py-2.5 text-[14px] font-semibold text-ink"
          >
            {l.text}
          </p>
        ) : (
          <div key={l.key} className="max-w-[88%] self-start">
            <p className="rounded-card rounded-bl-[5px] border border-hair bg-card px-3.5 py-2.5 text-[14.5px] font-semibold">
              {l.text}
            </p>
            {l.done?.length ? (
              <p className="mt-1 px-1 text-[11px] font-medium text-sub">{l.done.join(" · ")}</p>
            ) : null}
          </div>
        ),
      )}
    </div>
  ) : null;

  const card_ = card ? (
    <div className="mb-3">
      <EntryCard
        card={card}
        counting={counting}
        busy={busy}
        onYes={() => void answer(true)}
        onNo={() => void answer(false)}
        onEdit={edit}
        onEditing={() => {
          setCounting(false);
          cancelMic();
          hush();
        }}
      />
    </div>
  ) : null;

  const problem_ = problem ? (
    <p className="mb-3 text-[12.5px] font-semibold text-warn" role="alert">
      {problem}
    </p>
  ) : null;

  const controls = (
    <>
      <div className="flex items-center gap-3">
        <button
          type="button"
          aria-label={recording ? "Stop" : "Speak"}
          onClick={() => {
            if (recording) return mic.stop();
            byItself.current = false;
            open();
          }}
          disabled={busy}
          className={`grid shrink-0 place-items-center rounded-full text-white shadow-pill disabled:opacity-40 ${full ? "size-12 [&_svg]:size-5" : "size-14 [&_svg]:size-6"} ${recording ? "animate-pulse bg-cyan" : "bg-navy"}`}
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
          placeholder={full ? "Ask anything: Patil kab dega?" : "or type: B wing wale Sharma ji ko do sau"}
          aria-label="Type to the munshi"
          className="min-w-0 flex-1 rounded-pill border-[1.5px] border-line bg-white px-4 py-2.5 text-[14px] font-bold outline-none placeholder:font-medium placeholder:text-sub focus:border-cyan"
        />
        <button
          type="submit"
          disabled={!text.trim() || busy}
          className="rounded-pill bg-navy px-4 text-[13px] font-extrabold text-white disabled:opacity-40"
        >
          Send
        </button>
      </form>
    </>
  );

  if (full) {
    return (
      <div className="flex flex-1 flex-col">
        {lines.length === 0 && starters.length ? (
          <div className="flex flex-col items-start gap-2 pb-3">
            <p className="px-1 text-[12.5px] font-semibold text-sub">Try asking</p>
            {starters.map((q) => (
              <button
                key={q}
                type="button"
                onClick={() => void sendText(q)}
                disabled={busy}
                className="rounded-pill border-2 border-dashed border-line bg-card px-4 py-2 text-left text-[14px] font-bold disabled:opacity-40"
              >
                {q}
              </button>
            ))}
          </div>
        ) : null}
        {thread_}
        {card_}
        {problem_}
        <div className="sticky bottom-2 mt-auto rounded-card bg-card p-3 shadow-sheet">{controls}</div>
      </div>
    );
  }

  return (
    <Card title="Munshi" tight>
      {thread_}
      {card_}
      {problem_}
      {controls}
    </Card>
  );
}
