"use client";

import { useEffect, useState } from "react";

import { Check } from "@/components/icons";
import { CustomerShell } from "@/components/shell/Shell";
import { Card } from "@/components/ui/Card";
import { Field } from "@/components/ui/Field";
import { Dots, Notice } from "@/components/ui/Notice";
import { Pill } from "@/components/ui/Pill";
import { Avatar } from "@/components/ui/Row";
import { Sheet } from "@/components/ui/Sheet";
import { api, ApiError, usePoll } from "@/lib/api/client";
import type { Entry, Joined, ScanState } from "@/lib/api/types";
import { formatPaise } from "@/lib/money";
import { forgetPerson, newPerson, usePerson } from "@/lib/person";

/**
 * B0 → B1 · He scanned the udhaar QR, then confirms on the phone in his hand.
 *
 * The scan only says "I'm here". This screen waits, polling the scan, until the
 * shopkeeper attaches an amount; then the confirmation sheet rises. The button's
 * words come from the server, because they are what gets stored.
 */

type Outcome = { kind: "confirmed" | "disputed"; entry: Entry };

export function JoinScreen({ shopId }: { shopId: string }): React.ReactElement {
  const person = usePerson();
  const [name, setName] = useState("");
  const [joined, setJoined] = useState<Joined | null>(null);
  const [outcome, setOutcome] = useState<Outcome | null>(null);
  const [error, setError] = useState<string>();
  const [busy, setBusy] = useState(false);

  // Tell the shop he is here: once he is known, and again after "scan again".
  useEffect(() => {
    if (!person || joined) return;
    let live = true;
    api<Joined>(`/join/${shopId}`, { person_id: person.id, name: person.name })
      .then((j) => {
        if (live) setJoined(j);
      })
      .catch((e: unknown) => {
        if (live) setError(e instanceof ApiError ? e.message : "Could not reach the shop.");
      });
    return () => {
      live = false;
    };
  }, [person, joined, shopId]);

  const scan = usePoll<ScanState>(
    joined && !outcome ? `/scans/${joined.scan_id}` : null,
    1500,
  );
  const state = scan.data?.state;
  const entry = scan.data?.entry ?? null;

  async function answer(kind: "confirm" | "dispute"): Promise<void> {
    if (!entry || !person) return;
    setBusy(true);
    try {
      const done = await api<Entry>(`/entries/${entry.id}/${kind}`, { person_id: person.id });
      setOutcome({ kind: kind === "confirm" ? "confirmed" : "disputed", entry: done });
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not send your answer.");
    } finally {
      setBusy(false);
    }
  }

  async function leave(): Promise<void> {
    if (!joined) return;
    await api(`/scans/${joined.scan_id}/leave`, {}).catch(() => undefined);
    scan.refresh();
  }

  const shopName = joined?.shop.name ?? "the shop";
  const heading = { title: "Udhaar", sub: "Scanned the udhaar QR", back: "/c" };

  if (person === undefined) {
    return (
      <CustomerShell heading={heading}>
        <Card>
          <Dots />
        </Card>
      </CustomerShell>
    );
  }

  if (person === null) {
    return (
      <CustomerShell heading={heading}>
        <Card title="First time here?">
          <Field
            label="Your name, as on Paytm"
            value={name}
            onChange={setName}
            placeholder="Kavita"
            autoFocus
          />
          <p className="mt-2.5 text-[12px] font-medium leading-normal text-sub">
            In the Paytm app this comes from your account. The shop sees your name,
            never your number.
          </p>
          <div className="mt-3.5">
            <Pill onClick={() => newPerson(name)} disabled={!name.trim()}>
              Continue
            </Pill>
          </div>
        </Card>
      </CustomerShell>
    );
  }

  return (
    <CustomerShell heading={heading}>
      {error ? <Notice tone="warn">{error}</Notice> : null}

      {outcome ? (
        <Card>
          <div className="py-3 text-center">
            <div className="mx-auto mb-3 grid size-14 place-items-center rounded-full bg-ok-bg text-paid [&_svg]:size-7">
              <Check />
            </div>
            <p className="text-[21px] font-extrabold tracking-[-0.03em]">
              {outcome.kind === "confirmed" ? "In both books" : "Marked as not right"}
            </p>
            <p className="mt-1.5 text-[12.5px] font-medium leading-normal text-sub">
              {outcome.kind === "confirmed"
                ? `${formatPaise(outcome.entry.amount_paise)} at ${outcome.entry.shop_name}, confirmed by you. Nothing here promises a date.`
                : `${outcome.entry.shop_name} has been told. Nothing is agreed until you both are.`}
            </p>
          </div>
        </Card>
      ) : state === "left" || state === "expired" ? (
        <Card>
          <p className="text-[15px] font-extrabold">
            {state === "left" ? "You left the counter." : "That scan has expired."}
          </p>
          <p className="mt-1 text-[12.5px] font-medium text-sub">
            Scan again when you are at the counter.
          </p>
          <div className="mt-3.5">
            <Pill
              onClick={() => {
                setOutcome(null);
                setError(undefined);
                setJoined(null);
              }}
            >
              I&apos;m at the counter again
            </Pill>
          </div>
        </Card>
      ) : (
        <>
          <Card>
            <div className="py-2 text-center">
              <div className="mb-2.5 flex justify-center">
                <Avatar name={shopName} size="lg" />
              </div>
              <p className="text-[17px] font-extrabold tracking-[-0.02em]">{shopName}</p>
              <p className="mt-0.5 text-[12px] font-medium text-sub">{joined?.shop.locality}</p>
              <div className="mb-3 mt-5">
                <Dots />
              </div>
              <p className="text-[15px] font-extrabold tracking-[-0.02em]">
                {joined ? "The shop can see you're here" : "Telling the shop you're here"}
              </p>
              <p className="mt-1 text-[12.5px] font-medium leading-normal text-sub">
                They will enter the amount. You confirm it on this screen.
              </p>
            </div>
          </Card>
          {joined?.first_time ? (
            <Notice>
              New here? You join {shopName}&apos;s udhaar book as {person.name}. They never
              see your number.
            </Notice>
          ) : null}
          <Pill tone="outline" onClick={() => void leave()} disabled={!joined}>
            Cancel
          </Pill>
          <button
            type="button"
            onClick={() => {
              forgetPerson();
              setJoined(null);
            }}
            className="text-center text-[12px] font-bold text-cyan-text"
          >
            Not {person.name}?
          </button>
        </>
      )}

      {entry && state === "recorded" && !outcome ? (
        <Sheet>
          <div className="mb-3.5 flex items-center gap-[11px]">
            <Avatar name={entry.shop_name} />
            <p className="text-[14px] font-extrabold tracking-[-0.02em]">{entry.shop_name}</p>
          </div>
          <p className="mb-1.5 text-[20px] font-extrabold leading-tight tracking-[-0.03em]">
            {entry.shop_name} has recorded {formatPaise(entry.amount_paise)} udhaar against
            your name.
          </p>
          <p className="mb-4 text-[12.5px] font-medium leading-normal text-sub">
            Confirming makes this a shared record you can both see. It does not promise a
            date.
          </p>
          <div className="flex flex-col gap-2.5">
            <Pill onClick={() => void answer("confirm")} disabled={busy}>
              {entry.button}
            </Pill>
            <Pill tone="outline" onClick={() => void answer("dispute")} disabled={busy}>
              That&apos;s not right
            </Pill>
          </div>
        </Sheet>
      ) : null}
    </CustomerShell>
  );
}
