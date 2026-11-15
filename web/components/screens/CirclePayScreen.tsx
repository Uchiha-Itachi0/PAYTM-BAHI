"use client";

import { useState } from "react";

import { UpiPin } from "@/components/customer/UpiPin";
import { Check } from "@/components/icons";
import { CustomerShell } from "@/components/shell/Shell";
import { Card } from "@/components/ui/Card";
import { Dots, Notice } from "@/components/ui/Notice";
import { Pill } from "@/components/ui/Pill";
import { Avatar } from "@/components/ui/Row";
import { api, ApiError, usePoll } from "@/lib/api/client";
import type { CirclePaid, CircleView } from "@/lib/api/types";
import { formatPaise } from "@/lib/money";
import { usePerson } from "@/lib/person";
import { clockTime, fullDate } from "@/lib/when";

/**
 * C5 · Paying a bill on a circle's list, as any UPI payment: the amount, Proceed
 * securely, the UPI PIN.
 *
 * The money goes straight to the shop, against the bill's owner's own entry. The
 * amount starts at what is left on it, and he can pay less. Paying for someone
 * never makes them owe him anything here.
 */

type Step = "amount" | "pin" | "paying";

export function CirclePayScreen({
  circleId,
  entryId,
}: {
  circleId: string;
  entryId: string;
}): React.ReactElement {
  const person = usePerson();
  const circle = usePoll<CircleView>(
    person ? `/circles/${circleId}?person_id=${person.id}` : null,
    5000,
  );
  const bill = circle.data?.entries.find((e) => e.entry_id === entryId);
  const most = bill?.state === "open" ? bill.left_paise : 0;

  const [typed, setTyped] = useState<string | null>(null);
  const rupees = typed ?? (most ? String(most / 100) : "");
  const paise = Number(rupees || "0") * 100;
  const [step, setStep] = useState<Step>("amount");
  const [paid, setPaid] = useState<CirclePaid | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const valid = Number.isInteger(paise) && paise > 0 && paise <= most;
  const back = `/c/circle/${circleId}`;

  async function pay(): Promise<void> {
    if (!person) return;
    setStep("paying");
    setProblem(null);
    try {
      setPaid(
        await api<CirclePaid>(`/circles/${circleId}/entries/${entryId}/pay`, {
          person_id: person.id,
          amount_paise: paise,
        }),
      );
    } catch (e) {
      setProblem(e instanceof ApiError ? e.message : "The payment didn't go through.");
      setStep("amount");
    }
  }

  const heading = { title: "Pay", sub: bill?.shop.name, back };
  if (person === null) {
    return (
      <CustomerShell heading={heading}>
        <Notice>Pick whose phone this is on the home screen first.</Notice>
      </CustomerShell>
    );
  }

  if (paid) {
    return (
      <CustomerShell heading={{ title: "Paid", sub: paid.shop.name, back }}>
        <Card>
          <div className="py-3 text-center">
            <div className="mx-auto mb-3 grid size-16 place-items-center rounded-full bg-ok-bg text-paid [&_svg]:size-8">
              <Check />
            </div>
            <p className="text-[26px] font-extrabold tracking-[-0.03em]">
              {formatPaise(paid.amount_paise)} paid
            </p>
            <p className="mt-1.5 text-[13px] font-medium leading-normal text-sub">
              {fullDate(paid.paid_at)}, {clockTime(paid.paid_at)} · UPI to {paid.shop.name}
              <br />
              {bill?.mine
                ? "Paid from your circle's list."
                : `For ${paid.debtor_name}, who has been told.`}
            </p>
          </div>
        </Card>
        <Card tight>
          <div className="flex items-start justify-between">
            <p className="text-[14.5px] font-extrabold">
              {paid.left_paise ? "Still open on this bill" : "Nothing left on this bill"}
            </p>
            <p className="text-[15px] font-extrabold tabular-nums">
              {formatPaise(paid.left_paise)}
            </p>
          </div>
        </Card>
        <Pill tone="outline" href={back}>
          Back to the circle
        </Pill>
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
            <p className="mt-1 text-[12.5px] font-medium text-sub">to {bill?.shop.name}</p>
          </div>
        </Card>
      </CustomerShell>
    );
  }

  if (step === "pin") {
    return (
      <CustomerShell heading={{ ...heading, title: "Enter UPI PIN" }}>
        <UpiPin
          payee={bill?.shop.name ?? ""}
          paise={paise}
          onPaid={() => void pay()}
          onBack={() => setStep("amount")}
        />
      </CustomerShell>
    );
  }

  return (
    <CustomerShell heading={heading}>
      {problem ? <Notice tone="warn">{problem}</Notice> : null}
      {circle.error && !circle.data ? <Notice tone="warn">{circle.error}</Notice> : null}
      {!circle.data ? (
        !circle.error ? (
          <Card>
            <Dots />
          </Card>
        ) : null
      ) : !bill || most === 0 ? (
        <Notice>Nothing to pay on this bill right now.</Notice>
      ) : (
        <>
          <Card>
            <div className="flex flex-col items-center py-2 text-center">
              <Avatar name={bill.shop.name} size="lg" />
              <p className="mt-2.5 text-[16px] font-extrabold tracking-[-0.02em]">
                {bill.shop.name}
              </p>
              <p className="text-[12px] font-medium text-sub">
                {bill.mine ? "Your bill" : `${bill.debtor_name}'s bill`}, on{" "}
                {circle.data.name}&apos;s list
              </p>
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
                {formatPaise(most)} left on it.{" "}
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
                  That is more than is left on it.
                </p>
              ) : null}
            </div>
          </Card>
          <Pill tone="cyan" onClick={() => setStep("pin")} disabled={!valid}>
            Proceed securely
          </Pill>
          <p className="text-center text-[11.5px] font-medium text-sub">
            Paid by UPI, straight to {bill.shop.name}.
            {bill.mine ? "" : ` It stays ${bill.debtor_name}'s udhaar; they won't owe you anything here.`}
          </p>
        </>
      )}
    </CustomerShell>
  );
}
