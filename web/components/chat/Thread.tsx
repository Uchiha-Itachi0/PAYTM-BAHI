"use client";

import { Fragment, useEffect, useRef, useState } from "react";

import { Check } from "@/components/icons";
import { Amount } from "@/components/ui/Amount";
import type { Message, Passbook, Payment, ThreadEntry } from "@/lib/api/types";
import { formatPaise } from "@/lib/money";
import { clockTime, dayLabel, dayOf, fullDate } from "@/lib/when";

/**
 * C2 / C3 · One thread, from either side.
 *
 * Four things appear in it. Words, from the shop or the customer. BAHI's white
 * card for each udhaar, drawn from the entry as it is *now*, with its state on a
 * badge: waiting for his yes, agreed, part paid, paid. A Paytm-blue card for each
 * payment, with the green tick, on the payer's side. And BAHI's short lines when
 * something else happens to an entry (he says it's wrong, it was taken back). A
 * reminder is BAHI's too, sent on the shop's behalf after the shopkeeper let it go.
 *
 * Each udhaar and each payment also shows what he owed before it and after it
 * (`passbook`, from the API), so the thread reads like a passbook: ₹80 → ₹180
 * when ₹100 was agreed, ₹180 → ₹100 when ₹80 was paid.
 *
 * What each side can do is on the card: the customer answers an entry waiting
 * for him (yes, not mine, or the wrong amount); the shopkeeper corrects one, or
 * takes back one that should never have been written.
 */

export type Side = "shop" | "customer";

export type DisputedAs = "not_mine" | "wrong_amount";

export interface CardActions {
  /** Customer: "Yes, I owe ₹200". */
  onConfirm?: (entry: ThreadEntry) => void;
  /** Customer: "Not mine" or "Wrong amount", with his reason if he gives one. */
  onDispute?: (entry: ThreadEntry, reason: string, as: DisputedAs) => void;
  /** Shopkeeper: the right amount, in paise. */
  onCorrect?: (entry: ThreadEntry, paise: number) => void;
  /** Shopkeeper: take it back; it should never have been written. */
  onRemove?: (entry: ThreadEntry) => void;
}

function status(e: ThreadEntry, side: Side, name: string, shop: string): string {
  if (e.expired) return "Udhaar · no longer claimable";
  const part = e.paid_paise > 0 && e.status !== "settled";
  if (part)
    return `Udhaar · ${formatPaise(e.paid_paise)} paid, ${formatPaise(e.amount_paise - e.paid_paise)} left`;
  switch (e.status) {
    case "recorded":
      return side === "shop"
        ? `Udhaar · waiting for ${name}'s yes`
        : "Udhaar · waiting for your yes";
    case "confirmed":
      return side === "shop"
        ? `Udhaar · ${name} said yes, not paid yet`
        : "Udhaar · you said yes, not paid yet";
    case "disputed":
      if (e.disputed_as === "not_mine")
        return side === "shop" ? `Udhaar · ${name} says this isn't theirs` : "Udhaar · you said this isn't yours";
      return side === "shop"
        ? `Udhaar · ${name} says the amount is wrong`
        : "Udhaar · you said the amount is wrong";
    case "corrected":
      return `Replaced by ${side === "shop" ? "your" : `${shop}'s`} correction`;
    case "settled":
      return "Udhaar · paid in full";
    case "removed":
      return side === "shop" ? "Taken back by you · not owed" : `Taken back by ${shop} · nothing to pay`;
  }
}

function tone(e: ThreadEntry): string {
  if (e.expired || e.status === "corrected" || e.status === "removed") return "bg-tile text-sub";
  if (e.status === "disputed") return "bg-warn-bg";
  return "bg-card";
}

/** The state of an udhaar at a glance. Green only once it is paid: in Paytm a
 *  green tick means money moved, so agreeing gets navy, not green. */
function Badge({ e, side, name }: { e: ThreadEntry; side: Side; name: string }): React.ReactElement | null {
  const base = "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-extrabold [&_svg]:size-3";
  if (e.expired) return <span className={`${base} bg-quiet-bg text-quiet`}>Not claimable</span>;
  if (e.status === "corrected" || e.status === "removed") return null;
  if (e.status === "settled")
    return (
      <span className={`${base} bg-ok-bg text-ok`}>
        <Check />
        Paid
      </span>
    );
  if (e.paid_paise > 0) return <span className={`${base} bg-ok-bg text-ok`}>Part paid</span>;
  if (e.status === "confirmed")
    return (
      <span className={`${base} bg-av-blue text-navy-ink`}>
        <Check />
        {side === "shop" ? `${name} agreed` : "You agreed"}
      </span>
    );
  if (e.status === "disputed")
    return (
      <span className={`${base} bg-card text-warn`}>
        {e.disputed_as === "not_mine" ? "Not theirs, they say" : "Amount questioned"}
      </span>
    );
  return <span className={`${base} bg-quiet-bg text-quiet`}>Waiting for yes</span>;
}

/** Before → after, the passbook line under an udhaar or a payment. */
function Ledger({ book, side }: { book: Passbook; side: Side }): React.ReactElement {
  const label = side === "shop" ? "Total udhaar" : "Your udhaar here";
  return (
    <p className="mt-2.5 flex items-center justify-between gap-2 rounded-[10px] bg-sky-low px-2.5 py-1.5 text-[12px] font-bold">
      <span className="truncate text-sub">{label}</span>
      <span className="flex-none tabular-nums">
        <span className="text-sub">{formatPaise(book.before_paise)}</span>
        {" → "}
        {book.after_paise === 0 ? "nothing left" : formatPaise(book.after_paise)}
      </span>
    </p>
  );
}

/** Paytm's two-tone line under a chat card. */
function Stripe({ warn = false }: { warn?: boolean }): React.ReactElement {
  return (
    <div
      aria-hidden="true"
      className={`mx-3 h-[5px] rounded-b-full border-t-2 ${warn ? "border-warn bg-warn" : "border-cyan bg-navy"}`}
    />
  );
}

/** A payment: its own card, on the payer's side, with the green tick. */
function PaymentBubble({
  payment,
  book,
  side,
  name,
  shop,
  at,
}: {
  payment: Payment;
  book: Passbook | null | undefined;
  side: Side;
  name: string;
  shop: string;
  at: string;
}): React.ReactElement {
  const how = payment.method === "upi" ? "by UPI" : "in cash";
  const mine = side === "customer";
  return (
    <div className={`max-w-[86%] ${mine ? "self-end" : "self-start"}`}>
      <section className="rounded-card bg-av-blue px-4 pb-3 pt-3.5">
        <div className="flex items-center gap-2">
          <Amount paise={payment.amount_paise} className="text-[30px]" />
          <span className="grid size-6 place-items-center rounded-full bg-paid text-white [&_svg]:size-4">
            <Check />
          </span>
        </div>
        <p className="mt-2 text-[14px] font-bold leading-snug">
          {side === "shop" ? `Received from ${name} ${how}` : `Paid to ${shop} ${how}`}
        </p>
        {book ? <Ledger book={book} side={side} /> : null}
        <p className="mt-2 text-right text-[11.5px] font-medium text-sub">{clockTime(at)}</p>
      </section>
      <Stripe />
    </div>
  );
}

function EntryBubble({
  entry: e,
  book,
  side,
  name,
  shop,
  at,
  actions,
}: {
  entry: ThreadEntry;
  book: Passbook | null | undefined;
  side: Side;
  name: string;
  shop: string;
  at: string;
  actions: CardActions;
}): React.ReactElement {
  const [mode, setMode] = useState<"idle" | "why" | "fix" | "remove">("idle");
  const [why, setWhy] = useState<DisputedAs>("wrong_amount");
  const [words, setWords] = useState("");
  const [rupees, setRupees] = useState("");
  const struck = e.expired || e.status === "corrected" || e.status === "removed";
  const answer = side === "customer" && e.status === "recorded" && !e.expired;
  // The shopkeeper can correct any entry nothing has been paid against: one he
  // says is wrong gets the button up front, any other a quieter link.
  const fix =
    side === "shop" &&
    ["recorded", "confirmed", "disputed"].includes(e.status) &&
    e.paid_paise === 0 &&
    !e.expired;
  const urgent = e.status === "disputed";
  // "Not mine" puts taking it back first; "wrong amount" puts the correction first.
  const notTheirs = e.status === "disputed" && e.disputed_as === "not_mine";
  const mine = side === "shop";

  return (
    <div className={`max-w-[86%] ${mine ? "self-end" : "self-start"}`}>
      <section className={`rounded-card px-4 pb-3 pt-3.5 ${tone(e)}`}>
        <div className="flex items-start justify-between gap-3">
          <Amount paise={e.amount_paise} struck={struck} className="text-[30px]" />
          <Badge e={e} side={side} name={name} />
        </div>
        <p className="mt-2 text-[14px] font-bold leading-snug">{status(e, side, name, shop)}</p>
        {e.corrects_amount_paise ? (
          <p className="mt-0.5 text-[12px] font-semibold text-sub">
            {side === "shop" ? "Your correction" : `Corrected by ${shop}`}, from{" "}
            {formatPaise(e.corrects_amount_paise)}
          </p>
        ) : null}
        {e.note ? <p className="mt-0.5 text-[12px] font-medium text-sub">{e.note}</p> : null}
        {book && !struck ? <Ledger book={book} side={side} /> : null}

        {answer && mode === "idle" ? (
          <div className="mt-3 flex flex-col gap-2">
            <button
              type="button"
              onClick={() => actions.onConfirm?.(e)}
              className="rounded-pill border-[1.5px] border-cyan bg-white px-4 py-2 text-[14px] font-extrabold text-cyan-text"
            >
              {e.button}
            </button>
            <div className="flex justify-center gap-4">
              <button
                type="button"
                onClick={() => {
                  setWhy("not_mine");
                  setMode("why");
                }}
                className="text-[12.5px] font-bold text-sub"
              >
                Not mine
              </button>
              <button
                type="button"
                onClick={() => {
                  setWhy("wrong_amount");
                  setMode("why");
                }}
                className="text-[12.5px] font-bold text-sub"
              >
                Wrong amount
              </button>
            </div>
          </div>
        ) : null}
        {answer && mode === "why" ? (
          <form
            className="mt-3 flex flex-col gap-2"
            onSubmit={(ev) => {
              ev.preventDefault();
              actions.onDispute?.(e, words.trim(), why);
            }}
          >
            <p className="text-[12.5px] font-bold">
              {why === "not_mine"
                ? `Tell ${shop} this udhaar isn't yours.`
                : `Tell ${shop} the amount is wrong.`}
            </p>
            <input
              value={words}
              onChange={(ev) => setWords(ev.target.value)}
              placeholder={why === "not_mine" ? "Anything to add? (optional)" : "What should it be? (optional)"}
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

        {fix && mode === "idle" ? (
          <div className={urgent ? "mt-3 flex flex-col gap-2" : "mt-2 flex gap-4"}>
            {(notTheirs
              ? (["remove", "fix"] as const)
              : (["fix", "remove"] as const)
            ).map((what, i) => (
              <button
                key={what}
                type="button"
                onClick={() => setMode(what)}
                className={
                  urgent && i === 0
                    ? "w-full rounded-pill border-[1.5px] border-cyan bg-white px-4 py-2 text-[14px] font-extrabold text-cyan-text"
                    : "text-[12.5px] font-extrabold text-cyan-text"
                }
              >
                {what === "fix" ? "Correct the amount" : "Take it back"}
              </button>
            ))}
          </div>
        ) : null}
        {fix && mode === "remove" ? (
          <div className="mt-3 flex flex-col gap-2">
            <p className="text-[12.5px] font-semibold leading-snug">
              Take back {formatPaise(e.amount_paise)}? {name} won&apos;t owe it. It stays in the
              thread, marked taken back, and their phone shows it.
            </p>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => actions.onRemove?.(e)}
                className="flex-1 rounded-pill bg-navy px-3 py-2 text-[13.5px] font-extrabold text-white"
              >
                Take it back
              </button>
              <button
                type="button"
                onClick={() => setMode("idle")}
                className="rounded-pill px-3 py-2 text-[13px] font-bold text-sub"
              >
                Keep it
              </button>
            </div>
          </div>
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
      <Stripe warn={e.status === "disputed"} />
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
            {m.payment ? (
              <PaymentBubble
                payment={m.payment}
                book={m.passbook}
                side={side}
                name={name}
                shop={shop}
                at={m.sent_at}
              />
            ) : m.entry && m.card ? (
              <EntryBubble
                entry={m.entry}
                book={m.passbook}
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
