"use client";

import { useState } from "react";

import { PaidView } from "@/components/customer/PaidView";
import { CustomerShell } from "@/components/shell/Shell";
import { Card } from "@/components/ui/Card";
import { Dots, Notice } from "@/components/ui/Notice";
import { Pill } from "@/components/ui/Pill";
import { Avatar } from "@/components/ui/Row";
import { api, ApiError, usePoll } from "@/lib/api/client";
import type { MyUdhaar, Paid } from "@/lib/api/types";
import { formatPaise } from "@/lib/money";
import { usePerson } from "@/lib/person";

/**
 * Paying a shop, as Paytm pays anyone: the amount, then Proceed securely, then
 * the UPI PIN.
 *
 * The amount starts at what he can pay here (his balance, less anything he says
 * is wrong) and he can pay less: the book takes it from his oldest entries first,
 * and the shop is told what is still open. It can't be more than he owes.
 *
 * The PIN step is the demo's stand-in for UPI's own PIN screen: any four digits
 * go through, and they never leave this screen. In Paytm, that screen belongs to
 * the bank and NPCI, and BAHI never sees it.
 */

const PIN = 4;

type Step = "amount" | "pin" | "paying";

export function PayScreen({ shopId, from }: { shopId: string; from: string }): React.ReactElement {
  const person = usePerson();
  const mine = usePoll<MyUdhaar>(person ? `/people/${person.id}/udhaar` : null, 5000);
  const shop = mine.data?.shops.find((s) => s.shop.id === shopId);
  const most = shop?.payable_paise ?? 0;

  const [typed, setTyped] = useState<string | null>(null);
  const rupees = typed ?? (most ? String(most / 100) : "");
  const paise = Number(rupees || "0") * 100;
  const [step, setStep] = useState<Step>("amount");
  const [pin, setPin] = useState("");
  const [paid, setPaid] = useState<Paid | null>(null);
  const [problem, setProblem] = useState<string | null>(null);

  const back = from === "udhaar" ? "/c/udhaar" : `/c/chat/${shopId}`;
  const backLabel = from === "udhaar" ? "Back to my udhaar" : "Back to the chat";
  const valid = Number.isInteger(paise) && paise > 0 && paise <= most;

  async function pay(): Promise<void> {
    if (!person) return;
    setStep("paying");
    setProblem(null);
    try {
      setPaid(
        await api<Paid>(`/shops/${shopId}/pay`, { person_id: person.id, amount_paise: paise }),
      );
    } catch (e) {
      setProblem(e instanceof ApiError ? e.message : "The payment didn't go through.");
      setStep("amount");
      setPin("");
    }
  }

  function key(k: string): void {
    if (k === "⌫") return setPin((p) => p.slice(0, -1));
    if (pin.length >= PIN) return;
    const next = pin + k;
    setPin(next);
    if (next.length === PIN) setTimeout(() => void pay(), 250);
  }

  if (paid) return <PaidView paid={paid} back={back} backLabel={backLabel} />;

  const heading = { title: "Pay", sub: shop?.shop.name, back };

  if (person === null) {
    return (
      <CustomerShell heading={heading}>
        <Notice>Pick whose phone this is on the home screen first.</Notice>
      </CustomerShell>
    );
  }

  if (step === "paying") {
    return (
      <CustomerShell heading={heading}>
        <Card>
          <div className="py-8 text-center">
            <Dots />
            <p className="mt-4 text-[15px] font-extrabold">Paying {formatPaise(paise)}…</p>
            <p className="mt-1 text-[12.5px] font-medium text-sub">to {shop?.shop.name}</p>
          </div>
        </Card>
      </CustomerShell>
    );
  }

  if (step === "pin") {
    return (
      <CustomerShell heading={{ ...heading, title: "Enter UPI PIN" }}>
        <Card>
          <div className="text-center">
            <p className="text-[12.5px] font-semibold text-sub">Paying {shop?.shop.name}</p>
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
          Demo: any {PIN} digits work, and they never leave this screen. Never type your real
          UPI PIN here.
        </Notice>
        <Pill
          tone="outline"
          onClick={() => {
            setStep("amount");
            setPin("");
          }}
        >
          Back
        </Pill>
      </CustomerShell>
    );
  }

  return (
    <CustomerShell heading={heading}>
      {problem ? <Notice tone="warn">{problem}</Notice> : null}
      {!mine.data ? (
        <Card>
          <Dots />
        </Card>
      ) : !shop || most === 0 ? (
        <Notice>Nothing to pay {shop ? shop.shop.name : "this shop"} right now.</Notice>
      ) : (
        <>
          <Card>
            <div className="flex flex-col items-center py-2 text-center">
              <Avatar name={shop.shop.name} size="lg" />
              <p className="mt-2.5 text-[16px] font-extrabold tracking-[-0.02em]">
                {shop.shop.name}
              </p>
              <p className="text-[12px] font-medium text-sub">{shop.shop.locality}</p>
              <label className="mt-5 flex items-baseline justify-center gap-1 border-b-2 border-cyan px-2 pb-1">
                <span className="text-[30px] font-extrabold">₹</span>
                <input
                  value={rupees}
                  onChange={(e) => setTyped(e.target.value.replace(/\D/g, "").slice(0, 7))}
                  inputMode="numeric"
                  aria-label="Amount in rupees"
                  className="w-[7ch] bg-transparent text-center text-[38px] font-extrabold tracking-[-0.03em] tabular-nums outline-none"
                />
              </label>
              <p className="mt-2.5 text-[12.5px] font-medium text-sub">
                You owe {formatPaise(most)} here.{" "}
                {paise !== most ? (
                  <button
                    type="button"
                    onClick={() => setTyped(null)}
                    className="font-extrabold text-cyan-text"
                  >
                    Pay all
                  </button>
                ) : (
                  "Pay less if you like; the rest stays open."
                )}
              </p>
              {paise > most ? (
                <p className="mt-1 text-[12.5px] font-bold text-warn">
                  That is more than you owe.
                </p>
              ) : null}
            </div>
          </Card>
          <Pill tone="cyan" onClick={() => setStep("pin")} disabled={!valid}>
            Proceed securely
          </Pill>
          <p className="text-center text-[11.5px] font-medium text-sub">
            Paid by UPI. {shop.shop.name} is told in your chat, with what is left.
          </p>
        </>
      )}
    </CustomerShell>
  );
}
