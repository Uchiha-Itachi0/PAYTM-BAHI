"use client";

import { useState } from "react";

import { Card } from "@/components/ui/Card";
import { Notice } from "@/components/ui/Notice";
import { Pill } from "@/components/ui/Pill";
import { formatPaise } from "@/lib/money";

/**
 * The UPI PIN step, shared by every way of paying: who is being paid, how much,
 * and four dots.
 *
 * The demo's stand-in for UPI's own PIN screen: any four digits go through, and
 * they never leave this screen. In Paytm, that screen belongs to the bank and
 * NPCI, and BAHI never sees it.
 */

export const PIN = 4;

export function UpiPin({
  payee,
  paise,
  onPaid,
  onBack,
}: {
  payee: string;
  paise: number;
  /** The fourth digit is in: pay. */
  onPaid: () => void;
  onBack: () => void;
}): React.ReactElement {
  const [pin, setPin] = useState("");

  function key(k: string): void {
    if (k === "⌫") return setPin((p) => p.slice(0, -1));
    if (pin.length >= PIN) return;
    const next = pin + k;
    setPin(next);
    if (next.length === PIN) setTimeout(onPaid, 250);
  }

  return (
    <>
      <Card>
        <div className="text-center">
          <p className="text-[12.5px] font-semibold text-sub">Paying {payee}</p>
          <p className="mt-1 text-[28px] font-extrabold tracking-[-0.03em] tabular-nums">
            {formatPaise(paise)}
          </p>
          <p className="mt-4 text-[12px] font-extrabold uppercase tracking-[0.08em] text-sub">
            Enter {PIN}-digit UPI PIN
          </p>
          <div className="mt-3 flex justify-center gap-3" aria-label={`${pin.length} of ${PIN} digits`}>
            {Array.from({ length: PIN }, (_, i) => (
              <span
                key={i}
                className={`size-3.5 rounded-full ${i < pin.length ? "bg-navy" : "border-2 border-line"}`}
              />
            ))}
          </div>
        </div>
        <div className="mt-5 grid grid-cols-3 gap-2">
          {["1", "2", "3", "4", "5", "6", "7", "8", "9", "", "0", "⌫"].map((k) =>
            k ? (
              <button
                key={k}
                type="button"
                onClick={() => key(k)}
                className="rounded-[12px] bg-tile py-3.5 text-[20px] font-extrabold active:bg-hair"
              >
                {k}
              </button>
            ) : (
              <span key="blank" />
            ),
          )}
        </div>
      </Card>
      <Notice>
        Demo: any {PIN} digits work, and they never leave this screen. Never type your real UPI
        PIN here.
      </Notice>
      <Pill tone="outline" onClick={onBack}>
        Back
      </Pill>
    </>
  );
}
