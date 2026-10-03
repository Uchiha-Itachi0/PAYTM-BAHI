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
 * only, then writes their first udhaar if there is one.
 */

const KIND = { udhaar: "उधार", payment: "जमा", customer: "नया ग्राहक" } as const;

const REASON: Record<MunshiCard["reasons"][number], string> = {
  weak_match: "The name only sounded close",
  large: "A large amount",
  unusual: "Much more than they usually take",
  new_customer: "Not in your book yet: added by name only",
};

export function EntryCard({
  card,
  counting,
  busy,
  onYes,
  onNo,
}: {
  card: MunshiCard;
  /** The three-second countdown is running. */
  counting: boolean;
  busy: boolean;
  onYes: () => void;
  onNo: () => void;
}): React.ReactElement {
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
      {card.reasons.length && card.status === "shown" ? (
        <ul className="mt-2 flex flex-wrap gap-1.5">
          {card.reasons.map((r) => (
            <li key={r} className="rounded-pill bg-white/15 px-2.5 py-1 text-[11px] font-bold">
              {REASON[r]}
            </li>
          ))}
        </ul>
      ) : null}

      {card.status === "shown" ? (
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
        </>
      ) : null}

      {saved ? (
        <p className="mt-2.5 text-[13px] font-extrabold">
          {card.kind === "customer"
            ? `Added to your book · ${card.display_name}, by name only`
            : card.on_bahi
              ? `Written · sent to ${card.display_name}'s phone to confirm`
              : card.new
                ? `Added by name and written · nothing is sent to someone with no phone`
                : `Written · ${card.display_name} isn't on BAHI, so nothing was sent`}
        </p>
      ) : null}
      {gone ? <p className="mt-2 text-[12.5px] font-bold">Taken away. Nothing was written.</p> : null}
    </section>
  );
}
