import Link from "next/link";
import { useState } from "react";

import type { MunshiCard } from "@/lib/api/types";
import { formatPaise } from "@/lib/money";

/**
 * The entry the munshi proposed, as the book will hold it. The amount is the one
 * stored on the draft, never the munshi's sentence, and his own words sit under
 * it so a mishearing shows.
 *
 * A strong match for an ordinary amount goes in three seconds unless he says or
 * taps no. A card with reasons (a name that only sounded close, a large amount,
 * one far above what this customer usually takes, someone new to the book)
 * waits for a clear हाँ.
 *
 * Someone not in the book yet is on the card as "New": his yes adds them by name
 * only, then writes their first udhaar if there is one. A correction shows the
 * old amount struck through beside the right one.
 *
 * Edit fixes the card on screen, no voice needed: the amount, and for someone
 * new, their name and where they live. The same checks apply, and his tap is
 * still what writes it.
 */

export interface CardEdit {
  amount_rupees?: number;
  new_name?: string;
  new_tag?: string;
}

const KIND = {
  udhaar: "उधार",
  payment: "जमा",
  customer: "नया ग्राहक",
  correction: "सुधार",
} as const;

const REASON: Record<MunshiCard["reasons"][number], string> = {
  weak_match: "The name only sounded close",
  one_of_several: "Picked from several who fit",
  large: "A large amount",
  unusual: "Much more than they usually take",
  new_customer: "Not in your book yet: added by name only",
  correction: "A new entry replaces the old one; they confirm it",
};

function Editor({
  card,
  busy,
  onSave,
  onClose,
}: {
  card: MunshiCard;
  busy: boolean;
  onSave: (edit: CardEdit) => void;
  onClose: () => void;
}): React.ReactElement {
  const [rupees, setRupees] = useState(card.amount_paise ? String(card.amount_paise / 100) : "");
  const [name, setName] = useState(card.display_name);
  const [tag, setTag] = useState(card.tag ?? "");
  const input =
    "mt-1 block w-full rounded-[10px] bg-white px-3 py-2 text-[15px] font-bold text-ink outline-none";
  return (
    <form
      className="mt-3 flex flex-col gap-2.5"
      onSubmit={(e) => {
        e.preventDefault();
        const edit: CardEdit = {};
        const n = Number(rupees);
        if (rupees && n * 100 !== card.amount_paise) edit.amount_rupees = n;
        if (card.new) {
          if (name.trim() !== card.display_name) edit.new_name = name.trim();
          if (tag.trim() !== (card.tag ?? "")) edit.new_tag = tag.trim();
        }
        onSave(edit);
      }}
    >
      {card.new ? (
        <>
          <label className="text-[12px] font-bold opacity-80">
            Name
            <input value={name} onChange={(e) => setName(e.target.value)} className={input} />
          </label>
          <label className="text-[12px] font-bold opacity-80">
            Where they live or work
            <input
              value={tag}
              onChange={(e) => setTag(e.target.value)}
              placeholder="Room 4, C wing"
              className={input}
            />
          </label>
        </>
      ) : null}
      <label className="text-[12px] font-bold opacity-80">
        {card.kind === "customer" ? "Their first udhaar, in rupees (optional)" : "Amount, in rupees"}
        <input
          value={rupees}
          onChange={(e) => setRupees(e.target.value.replace(/\D/g, "").slice(0, 6))}
          inputMode="numeric"
          className={input}
        />
      </label>
      <div className="flex gap-2">
        <button
          type="submit"
          disabled={busy || (card.new && !name.trim())}
          className="flex-1 rounded-pill bg-cyan p-[10px] text-[14px] font-extrabold text-white disabled:opacity-40"
        >
          Save the card
        </button>
        <button
          type="button"
          onClick={onClose}
          className="rounded-pill px-4 text-[13px] font-bold opacity-80"
        >
          Back
        </button>
      </div>
    </form>
  );
}

export function EntryCard({
  card,
  counting,
  busy,
  onYes,
  onNo,
  onEdit,
  onEditing,
}: {
  card: MunshiCard;
  /** The three-second countdown is running. */
  counting: boolean;
  busy: boolean;
  onYes: () => void;
  onNo: () => void;
  /** He fixed the card on screen. */
  onEdit?: (edit: CardEdit) => Promise<void>;
  /** He opened the editor: whatever countdown there was stops. */
  onEditing?: () => void;
}): React.ReactElement {
  const [editing, setEditing] = useState(false);
  const saved = card.status === "saved";
  const gone = card.status === "cancelled" || card.status === "replaced";
  return (
    <section
      className={`rounded-card px-3.5 py-3 ${gone ? "bg-tile text-sub" : "bg-navy text-white"}`}
      aria-live="polite"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate text-[16px] font-extrabold tracking-[-0.02em]">
            {card.display_name}
            {card.new ? (
              <span className="ml-2 rounded-md bg-cyan px-1.5 py-0.5 align-middle text-[10.5px] font-extrabold">
                New
              </span>
            ) : null}
          </p>
          {card.tag ? <p className="text-[12px] font-semibold opacity-80">{card.tag}</p> : null}
        </div>
        <div className="text-right">
          {card.corrects_amount_paise ? (
            <p className="text-[14px] font-bold leading-none tabular-nums line-through opacity-70">
              {formatPaise(card.corrects_amount_paise)}
            </p>
          ) : null}
          {card.amount_paise !== null ? (
            <p className="text-[26px] font-extrabold leading-none tracking-[-0.035em] tabular-nums">
              {formatPaise(card.amount_paise)}
            </p>
          ) : null}
          <p className="mt-1 text-[12px] font-extrabold opacity-80">{KIND[card.kind]}</p>
        </div>
      </div>
      {card.spoken_text ? (
        <p className="mt-2 text-[12px] font-medium opacity-80">You said: “{card.spoken_text}”</p>
      ) : null}
      {card.called && card.status !== "cancelled" && card.status !== "replaced" ? (
        <p className="mt-1 text-[12px] font-bold">
          You call them {card.called}
          <span className="font-medium opacity-80">
            {card.status === "saved" ? " · remembered" : " · remembered on your yes"}
          </span>
        </p>
      ) : null}
      {card.reasons.length && card.status === "shown" ? (
        <ul className="mt-2 flex flex-wrap gap-1.5">
          {card.reasons.map((r) => (
            <li key={r} className="rounded-pill bg-white/15 px-2.5 py-1 text-[11px] font-bold">
              {REASON[r]}
            </li>
          ))}
        </ul>
      ) : null}

      {card.status === "shown" && editing && onEdit ? (
        <Editor
          card={card}
          busy={busy}
          onSave={(edit) => void onEdit(edit).then(() => setEditing(false))}
          onClose={() => setEditing(false)}
        />
      ) : null}

      {card.status === "shown" && !editing ? (
        <>
          {counting ? (
            <div className="mt-2.5 h-1.5 overflow-hidden rounded-full bg-white/20">
              <div
                className="h-full origin-left animate-countdown rounded-full bg-cyan"
                onAnimationEnd={onYes}
              />
            </div>
          ) : null}
          <div className="mt-3 flex gap-2">
            {!counting ? (
              <button
                type="button"
                onClick={onYes}
                disabled={busy}
                className="flex-1 rounded-pill bg-cyan p-[11px] text-[15px] font-extrabold text-white disabled:opacity-40"
              >
                हाँ, लिख दो
              </button>
            ) : null}
            <button
              type="button"
              onClick={onNo}
              disabled={busy}
              className="flex-1 rounded-pill bg-white p-[11px] text-[15px] font-extrabold text-navy disabled:opacity-40"
            >
              {counting ? "Cancel" : "नहीं"}
            </button>
          </div>
          {onEdit ? (
            <button
              type="button"
              onClick={() => {
                onEditing?.();
                setEditing(true);
              }}
              disabled={busy}
              className="mt-2 w-full text-center text-[12.5px] font-extrabold opacity-80"
            >
              Something wrong? Edit the card
            </button>
          ) : null}
        </>
      ) : null}

      {saved ? (
        <p className="mt-2.5 text-[13px] font-extrabold">
          {card.kind === "customer"
            ? `Added to your book · ${card.display_name}, by name only`
            : card.kind === "correction"
              ? card.on_bahi
                ? `Corrected · sent to ${card.display_name}'s phone to confirm`
                : `Corrected · ${card.display_name} isn't on BAHI, so nothing was sent`
            : card.on_bahi
              ? `Written · sent to ${card.display_name}'s phone to confirm`
              : card.new
                ? `Added by name and written · nothing is sent to someone with no phone`
                : `Written · ${card.display_name} isn't on BAHI, so nothing was sent`}
        </p>
      ) : null}
      {saved && card.new && card.customer_id ? (
        <Link
          href={`/m/customers/${card.customer_id}`}
          className="mt-2 inline-block text-[12.5px] font-extrabold text-cyan underline underline-offset-2"
        >
          Add their phone, to send them entries →
        </Link>
      ) : null}
      {gone ? <p className="mt-2 text-[12.5px] font-bold">Taken away. Nothing was written.</p> : null}
    </section>
  );
}
