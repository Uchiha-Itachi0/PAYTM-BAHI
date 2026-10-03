"use client";

import { useState } from "react";

import { Amount } from "@/components/ui/Amount";
import { Pill } from "@/components/ui/Pill";
import { Avatar } from "@/components/ui/Row";
import { Sheet } from "@/components/ui/Sheet";
import { api, ApiError, usePoll } from "@/lib/api/client";
import type { Counter, Waiting } from "@/lib/api/types";
import { SHOP_ID } from "@/lib/config";
import { formatPaise, inWords } from "@/lib/money";

/**
 * A customer at the counter asked for udhaar on her phone: "₹200, atta and
 * oil". It rises over whatever screen he is on, one ask at a time, oldest first.
 *
 * Yes writes exactly that, and her ask was her yes, so it is agreed by both at
 * once. No writes nothing. Change amount writes his figure instead, and she
 * confirms it on her phone like any entry. The Soundbox has already said the
 * amount; who and what for are read here, never out loud.
 */
export function AskPopup(): React.ReactElement | null {
  const counter = usePoll<Counter>(`/shops/${SHOP_ID}/counter`, 2000);
  const asks = (counter.data?.waiting ?? []).filter((w) => w.asked_paise);
  const first = asks[0];
  if (!first) return null;
  // Keyed by the scan, so a new ask starts with a clean form.
  return <Ask key={first.scan_id} ask={first} more={asks.length - 1} onDone={counter.refresh} />;
}

function Ask({
  ask,
  more,
  onDone,
}: {
  ask: Waiting;
  more: number;
  onDone: () => void;
}): React.ReactElement {
  const [mode, setMode] = useState<"ask" | "change">("ask");
  const [rupees, setRupees] = useState("");
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const asked = ask.asked_paise ?? 0;

  async function answer(said: "yes" | "no" | "change", amount?: number): Promise<void> {
    setBusy(true);
    setProblem(null);
    try {
      await api(`/shops/${SHOP_ID}/scans/${ask.scan_id}/answer`, {
        answer: said,
        amount_rupees: amount ?? null,
      });
      onDone();
    } catch (e) {
      setProblem(e instanceof ApiError ? e.message : "Couldn't send your answer.");
    } finally {
      setBusy(false);
    }
  }

  const changed = Number(rupees);
  return (
    <Sheet>
      <div className="mb-3 flex items-center gap-[11px]">
        <Avatar name={ask.display_name} />
        <div className="min-w-0 flex-1">
          <p className="truncate text-[14px] font-extrabold tracking-[-0.02em]">
            {ask.display_name}
          </p>
          <p className="truncate text-[12px] font-medium text-sub">
            {[ask.tag, ask.first_time ? "New here" : null].filter(Boolean).join(" · ") ||
              "At the counter"}
          </p>
        </div>
        {more > 0 ? (
          <span className="rounded-full bg-quiet-bg px-2 py-0.5 text-[11px] font-extrabold text-quiet">
            +{more} waiting
          </span>
        ) : null}
      </div>

      <p className="text-[13px] font-semibold text-sub">is asking for udhaar</p>
      <Amount paise={asked} className="mt-1 text-[40px]" />
      <p className="mt-1 text-[12px] font-medium text-sub">{inWords(asked)}</p>
      {ask.asked_note ? (
        <p className="mt-2.5 rounded-[10px] bg-sky-low px-3 py-2 text-[14px] font-bold">
          {ask.asked_note}
        </p>
      ) : null}

      {problem ? (
        <p className="mt-3 text-[12.5px] font-semibold text-warn" role="alert">
          {problem}
        </p>
      ) : null}

      {mode === "ask" ? (
        <div className="mt-4 flex flex-col gap-2.5">
          <Pill onClick={() => void answer("yes")} disabled={busy}>
            Yes, give {formatPaise(asked)}
          </Pill>
          <div className="flex gap-2.5">
            <div className="flex-1">
              <Pill tone="outline" onClick={() => setMode("change")} disabled={busy}>
                Change amount
              </Pill>
            </div>
            <div className="flex-1">
              <Pill tone="outline" onClick={() => void answer("no")} disabled={busy}>
                No
              </Pill>
            </div>
          </div>
          <p className="text-center text-[11.5px] font-medium leading-snug text-sub">
            Yes writes it agreed by both: {ask.display_name} asked for it.
          </p>
        </div>
      ) : (
        <form
          className="mt-4 flex flex-col gap-2.5"
          onSubmit={(ev) => {
            ev.preventDefault();
            if (Number.isInteger(changed) && changed > 0) void answer("change", changed);
          }}
        >
          <label className="flex items-center gap-1 rounded-[11px] border-[1.5px] border-line bg-white px-3 py-2.5 focus-within:border-cyan">
            <span className="text-[16px] font-extrabold">₹</span>
            <input
              value={rupees}
              onChange={(e) => setRupees(e.target.value.replace(/\D/g, "").slice(0, 6))}
              inputMode="numeric"
              placeholder="The right amount"
              aria-label="The right amount, in rupees"
              autoFocus
              className="min-w-0 flex-1 bg-transparent text-[16px] font-extrabold outline-none placeholder:font-medium placeholder:text-sub"
            />
          </label>
          <p className="text-[11.5px] font-medium leading-snug text-sub">
            Written as yours: {ask.display_name} confirms it on their phone.
          </p>
          <div className="flex gap-2.5">
            <div className="flex-1">
              <button
                type="submit"
                disabled={busy || !(changed > 0)}
                className="w-full rounded-pill bg-navy p-[13px] text-[15px] font-extrabold text-white disabled:opacity-40"
              >
                {changed > 0 ? `Write ${formatPaise(changed * 100)}` : "Write it"}
              </button>
            </div>
            <button
              type="button"
              onClick={() => setMode("ask")}
              className="rounded-pill px-4 text-[13px] font-bold text-sub"
            >
              Back
            </button>
          </div>
        </form>
      )}
    </Sheet>
  );
}
