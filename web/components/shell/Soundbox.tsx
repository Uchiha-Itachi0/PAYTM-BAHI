"use client";

import { useEffect, useRef, useState } from "react";

import type { Events, ShopEvent } from "@/lib/api/types";
import { SHOP_ID } from "@/lib/config";
import { formatPaise } from "@/lib/money";
import { sayAsked, sayReceived, tone, unlock } from "@/lib/soundbox";

/**
 * V7 · The Soundbox, and the news strip above the shopkeeper's screen.
 *
 * Asks the API every two seconds what happened since it last asked: a scan at
 * the counter, a customer's yes, a dispute, a UPI payment, a message. Each one
 * plays its tone; money arriving says what was owed, what came and what is still
 * open ("दो सौ रुपये का उधार था, उसमें से सौ रुपये मिले, सौ रुपये बाकी"). The
 * strip shows who, for a few seconds. The sound never
 * carries a name; the screen does.
 */

const EVERY_MS = 2000;
const SHOWN_MS = 6000;

function news(e: ShopEvent): string {
  const amount = e.amount_paise ? formatPaise(e.amount_paise) : "";
  switch (e.kind) {
    case "scanned":
      return `${e.display_name} is at the counter`;
    case "asked":
      return `${e.display_name} is asking for ${amount} udhaar`;
    case "confirmed":
      return `${e.display_name} confirmed ${amount}`;
    case "disputed":
      return `${e.display_name} says ${amount} is not right`;
    case "paid":
      return `${amount} received from ${e.display_name} by UPI · ${
        e.left_paise ? `${formatPaise(e.left_paise)} left` : "all paid"
      }`;
    case "message":
      return `New message from ${e.display_name}`;
  }
}

function play(e: ShopEvent): void {
  if (e.kind === "paid" && e.amount_paise) sayReceived(e.amount_paise, e.left_paise ?? 0);
  else if (e.kind === "asked" && e.amount_paise) sayAsked(e.amount_paise);
  else if (e.kind === "scanned") tone("chime");
  else if (e.kind === "disputed") tone("question");
  else if (e.kind === "confirmed") tone("done");
  else tone("message");
}

export function Soundbox(): React.ReactElement | null {
  const after = useRef<string | null>(null);
  const [shown, setShown] = useState<{ key: string; text: string }[]>([]);

  useEffect(() => {
    const first = (): void => unlock();
    window.addEventListener("pointerdown", first, { once: true });
    let live = true;

    async function ask(): Promise<void> {
      try {
        const q = after.current ? `?after=${encodeURIComponent(after.current)}` : "";
        const res = await fetch(`/api/shops/${SHOP_ID}/events${q}`, { cache: "no-store" });
        if (!res.ok || !live) return;
        const out = (await res.json()) as Events;
        after.current = out.now;
        if (!out.events.length) return;
        out.events.forEach(play);
        const fresh = out.events.map((e) => ({ key: `${e.kind}-${e.at}`, text: news(e) }));
        setShown((s) => [...s, ...fresh].slice(-3));
        setTimeout(() => {
          if (live) setShown((s) => s.filter((x) => !fresh.some((f) => f.key === x.key)));
        }, SHOWN_MS);
      } catch {
        // Offline for a moment: the next ask picks up from the same point.
      }
    }

    void ask();
    const timer = setInterval(() => void ask(), EVERY_MS);
    return () => {
      live = false;
      clearInterval(timer);
      window.removeEventListener("pointerdown", first);
    };
  }, []);

  if (!shown.length) return null;
  return (
    <div className="pointer-events-none fixed inset-x-0 top-2 z-20 mx-auto flex w-full max-w-[430px] flex-col gap-1.5 px-2.5">
      {shown.map((s) => (
        <p
          key={s.key}
          role="status"
          className="rounded-card bg-navy px-3.5 py-2.5 text-[13px] font-bold text-white shadow-pill"
        >
          {s.text}
        </p>
      ))}
    </div>
  );
}
