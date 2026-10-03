"use client";

import { Fragment, useEffect, useRef, useState } from "react";

import { Check } from "@/components/icons";
import type { Message, ThreadEntry } from "@/lib/api/types";
import { formatPaise } from "@/lib/money";
import { clockTime, dayLabel, dayOf, fullDate } from "@/lib/when";

/**
 * C2 / C3 · One thread, from either side.
 *
 * Three things appear in it. Words, from the shop or the customer. BAHI's card
 * for each entry, drawn from the entry as it is *now*: ₹200 posted this morning
 * shows ✓ the moment he confirms. And BAHI's short lines when something happens
 * to an entry later (he says it's wrong, it was paid). A reminder is BAHI's too,
 * sent on the shop's behalf after the shopkeeper let it go.
 *
 * What each side can do is on the card: the customer answers an entry waiting
 * for him; the shopkeeper corrects one the customer says is wrong.
 */

export type Side = "shop" | "customer";

export interface CardActions {
  /** Customer: "Yes, I owe ₹200". */
  onConfirm?: (entry: ThreadEntry) => void;
  /** Customer: "That's not right", with his reason if he gives one. */
  onDispute?: (entry: ThreadEntry, reason: string) => void;
  /** Shopkeeper: the right amount, in paise. */
  onCorrect?: (entry: ThreadEntry, paise: number) => void;
}

function status(e: ThreadEntry, side: Side, name: string, shop: string): string {
  if (e.expired) return "Udhaar · no longer claimable";
  const who = side === "shop" ? name : "you";
  switch (e.status) {
    case "recorded":
      return side === "shop" ? `Udhaar · waiting on ${name}` : "Udhaar · waiting for your yes";
    case "confirmed":
      return `Udhaar · confirmed by ${who}`;
    case "disputed":
      return side === "shop" ? `Udhaar · ${name} says this is wrong` : "Udhaar · you said this is wrong";
    case "corrected":
      return `Replaced by ${side === "shop" ? "your" : `${shop}'s`} correction`;
    case "settled":
      return "Udhaar · paid in full";
  }
}

function tone(e: ThreadEntry): string {
  if (e.expired || e.status === "corrected") return "bg-tile text-sub";
  if (e.status === "disputed") return "bg-warn-bg";
  return "bg-av-blue";
}

function EntryBubble({
  entry: e,
  side,
  name,
  shop,
  at,
  actions,
}: {
  entry: ThreadEntry;
  side: Side;
  name: string;
  shop: string;
  at: string;
  actions: CardActions;
}): React.ReactElement {
  const [mode, setMode] = useState<"idle" | "why" | "fix">("idle");
  const [words, setWords] = useState("");
  const [rupees, setRupees] = useState("");
  const done = e.status === "confirmed" || e.status === "settled";
  const struck = e.expired || e.status === "corrected";
  const answer = side === "customer" && e.status === "recorded" && !e.expired;
  const fix = side === "shop" && e.status === "disputed";
  const mine = side === "shop";

  return (
    <div className={`max-w-[86%] ${mine ? "self-end" : "self-start"}`}>
      <section className={`rounded-card px-4 pb-3 pt-3.5 ${tone(e)}`}>
        <div className="flex items-center gap-2">
          <p
            className={`text-[30px] font-extrabold leading-none tracking-[-0.035em] tabular-nums ${struck ? "line-through" : ""}`}
          >
            {formatPaise(e.amount_paise)}
          </p>
          {done ? (
            <span className="grid size-6 place-items-center rounded-full bg-paid text-white [&_svg]:size-4">
              <Check />
            </span>
          ) : null}
        </div>
        <p className="mt-2 text-[14px] font-bold leading-snug">{status(e, side, name, shop)}</p>
        {e.corrects_amount_paise ? (
          <p className="mt-0.5 text-[12px] font-semibold text-sub">
            {side === "shop" ? "Your correction" : `Corrected by ${shop}`}, from{" "}
            {formatPaise(e.corrects_amount_paise)}
          </p>
        ) : null}
        {e.note ? <p className="mt-0.5 text-[12px] font-medium text-sub">{e.note}</p> : null}

        {answer && mode === "idle" ? (
          <div className="mt-3 flex flex-col gap-2">
            <button
              type="button"
              onClick={() => actions.onConfirm?.(e)}
              className="rounded-pill border-[1.5px] border-cyan bg-white px-4 py-2 text-[14px] font-extrabold text-cyan-text"
            >
              {e.button}
            </button>
            <button
              type="button"
              onClick={() => setMode("why")}
              className="text-[12.5px] font-bold text-sub"
            >
              That&apos;s not right
            </button>
          </div>
        ) : null}
        {answer && mode === "why" ? (
          <form
            className="mt-3 flex flex-col gap-2"
            onSubmit={(ev) => {
              ev.preventDefault();
              actions.onDispute?.(e, words.trim());
            }}
          >
            <input
              value={words}
              onChange={(ev) => setWords(ev.target.value)}
              placeholder="What's wrong? (optional)"
              aria-label="What's wrong"
              className="rounded-[11px] border-[1.5px] border-line bg-white px-3 py-2 text-[14px] font-semibold outline-none focus:border-cyan"
            />
            <div className="flex gap-2">
              <button
                type="submit"
                className="flex-1 rounded-pill bg-navy px-3 py-2 text-[13.5px] font-extrabold text-white"
              >
                Tell {shop}
              </button>
              <button
                type="button"
                onClick={() => setMode("idle")}
                className="rounded-pill px-3 py-2 text-[13px] font-bold text-sub"
              >
                Back
              </button>
            </div>
          </form>
        ) : null}

        {fix && mode !== "fix" ? (
          <button
            type="button"
            onClick={() => setMode("fix")}
            className="mt-3 w-full rounded-pill border-[1.5px] border-cyan bg-white px-4 py-2 text-[14px] font-extrabold text-cyan-text"
          >
            Correct the amount
          </button>
        ) : null}
        {fix && mode === "fix" ? (
          <form
            className="mt-3 flex flex-col gap-2"
            onSubmit={(ev) => {
              ev.preventDefault();
              const paise = Number(rupees) * 100;
              if (Number.isInteger(paise) && paise > 0) actions.onCorrect?.(e, paise);
            }}
          >
            <label className="flex items-center gap-1 rounded-[11px] border-[1.5px] border-line bg-white px-3 py-2 focus-within:border-cyan">
              <span className="text-[15px] font-extrabold">₹</span>
              <input
                value={rupees}
                onChange={(ev) => setRupees(ev.target.value.replace(/\D/g, ""))}
                inputMode="numeric"
                placeholder="The right amount"
                aria-label="The right amount, in rupees"
                autoFocus
                className="min-w-0 flex-1 bg-transparent text-[15px] font-extrabold outline-none placeholder:font-medium placeholder:text-sub"
              />
            </label>
            <p className="text-[11.5px] font-medium leading-snug text-sub">
              A new entry. {name} confirms it on their phone; the old one stays, marked
              corrected.
            </p>
            <div className="flex gap-2">
              <button
                type="submit"
                disabled={!rupees || Number(rupees) <= 0}
                className="flex-1 rounded-pill bg-navy px-3 py-2 text-[13.5px] font-extrabold text-white disabled:opacity-40"
              >
                Send the correction
              </button>
              <button
                type="button"
                onClick={() => setMode("idle")}
                className="rounded-pill px-3 py-2 text-[13px] font-bold text-sub"
              >
                Back
              </button>
            </div>
          </form>
        ) : null}

        <p className="mt-2 text-right text-[11.5px] font-medium text-sub">
          {e.expired ? `${fullDate(e.recorded_at)} · ` : ""}
          {clockTime(at)}
        </p>
      </section>
      <div
        aria-hidden="true"
        className={`mx-3 h-1 rounded-b-full ${e.status === "disputed" ? "bg-warn" : "bg-navy"}`}
      />
    </div>
  );
}

function Bubble({
  m,
  side,
  shop,
}: {
  m: Message;
  side: Side;
  shop: string;
}): React.ReactElement {
  // The shop's words and BAHI's reminders are the shop's side of the thread.
  const fromShop = m.author === "shop" || m.kind === "reminder";
  const mine = fromShop === (side === "shop");
  return (
    <div className={`max-w-[80%] ${mine ? "self-end" : "self-start"}`}>
      {m.kind === "reminder" ? (
        <p className={`mb-1 px-1 text-[11px] font-bold text-sub ${mine ? "text-right" : ""}`}>
          {side === "shop" ? "Reminder · sent by BAHI for you" : `Reminder from ${shop}`}
        </p>
      ) : null}
      <div
        className={`rounded-card px-3.5 py-2.5 ${mine ? "rounded-br-[5px] bg-av-blue" : "rounded-bl-[5px] bg-card"}`}
      >
        <p className="whitespace-pre-wrap text-[14.5px] font-medium leading-snug">{m.body}</p>
        <p className="mt-1 text-right text-[11px] font-medium text-sub">{clockTime(m.sent_at)}</p>
      </div>
    </div>
  );
}

export function ThreadView({
  messages,
  today,
  side,
  name,
  shop,
  actions = {},
}: {
  messages: Message[];
  today: string;
  side: Side;
  /** The customer, as the shop names them. */
  name: string;
  shop: string;
  actions?: CardActions;
}): React.ReactElement {
  const end = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    end.current?.scrollIntoView({ block: "end" });
  }, [messages.length]);

  if (!messages.length) {
    return (
      <p className="py-10 text-center text-[12.5px] font-medium text-sub">
        Nothing here yet. Entries and messages will appear in this thread.
      </p>
    );
  }
  return (
    <div className="flex flex-col gap-2.5 pb-2">
      {messages.map((m, i) => {
        const day = dayOf(m.sent_at);
        const newDay = i === 0 || dayOf(messages[i - 1].sent_at) !== day;
        return (
          <Fragment key={m.id}>
            {newDay ? (
              <p className="my-1 self-center rounded-full bg-quiet-bg px-3 py-1 text-[11.5px] font-bold text-quiet">
                {dayLabel(m.sent_at, today)}
              </p>
            ) : null}
            {m.entry && m.card ? (
              <EntryBubble
                entry={m.entry}
                side={side}
                name={name}
                shop={shop}
                at={m.sent_at}
                actions={actions}
              />
            ) : m.kind === "entry" ? (
              <p className="self-center px-4 text-center text-[12px] font-semibold text-sub">
                {m.body.replace(/\.$/, "")} · {clockTime(m.sent_at)}
              </p>
            ) : (
              <Bubble m={m} side={side} shop={shop} />
            )}
          </Fragment>
        );
      })}
      <div ref={end} className="scroll-mb-24" />
    </div>
  );
}
