"use client";

import { useCallback, useEffect, useRef, useState } from "react";

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
import { formatPaise, inWords } from "@/lib/money";
import { forgetPerson, newPerson, usePerson } from "@/lib/person";

/**
 * B0 → B1 · He scanned the udhaar QR, then confirms on the phone in his hand.
 *
 * The scan only says "I'm here". This screen waits, polling the scan, until the
 * shopkeeper attaches an amount; then the confirmation sheet rises. The button's
 * words come from the server, because they are what gets stored.
 *
 * She can also ask, here: how much she is taking and what for. The shop answers
 * on its screen. A yes writes exactly that, and her ask was her yes, so it is in
 * both books at once; a no writes nothing; a different amount comes back as the
 * usual sheet, for her own yes.
 */

/** What she asks for: whole rupees, as typed, and what for. */
type Asking = { rupees: number; note: string | null };

function askOf(rupees: string, note: string): Asking | null {
  const n = Number(rupees);
  return Number.isInteger(n) && n > 0 ? { rupees: n, note: note.trim() || null } : null;
}

/** The two fields she fills to ask: how much, and what for. */
function AskFields({
  rupees,
  setRupees,
  note,
  setNote,
}: {
  rupees: string;
  setRupees: (v: string) => void;
  note: string;
  setNote: (v: string) => void;
}): React.ReactElement {
  const paise = Number(rupees || "0") * 100;
  return (
    <div className="flex flex-col gap-3">
      <div>
        <Field
          label="How much are you taking? (optional)"
          value={rupees}
          onChange={(v) => setRupees(v.replace(/\D/g, "").slice(0, 6))}
          placeholder="200"
          inputMode="numeric"
        />
        {paise ? (
          <p className="mt-1 px-1 text-[11.5px] font-medium text-sub">{inWords(paise)}</p>
        ) : null}
      </div>
      <Field
        label="What for? (optional)"
        value={note}
        onChange={setNote}
        placeholder="Atta and oil"
        maxLength={80}
      />
    </div>
  );
}

type Outcome = { kind: "confirmed" | "disputed"; entry: Entry };

export function JoinScreen({ shopId }: { shopId: string }): React.ReactElement {
  const person = usePerson();
  const [name, setName] = useState("");
  const [joined, setJoined] = useState<Joined | null>(null);
  const [outcome, setOutcome] = useState<Outcome | null>(null);
  const [error, setError] = useState<string>();
  const [busy, setBusy] = useState(false);
  const [rupees, setRupees] = useState("");
  const [note, setNote] = useState("");
  const [asking, setAsking] = useState(false);
  // Asked on the first-time card, before the scan existed: sent once it does.
  const pendingAsk = useRef<Asking | null>(null);

  const personId = person?.id;
  const sendAsk = useCallback(
    async (scanId: string, a: Asking): Promise<void> => {
      if (!personId) return;
      setAsking(true);
      setError(undefined);
      try {
        await api(`/scans/${scanId}/ask`, {
          person_id: personId,
          amount_rupees: a.rupees,
          note: a.note,
        });
        setRupees("");
        setNote("");
      } catch (e) {
        setError(e instanceof ApiError ? e.message : "Could not ask the shop.");
      } finally {
        setAsking(false);
      }
    },
    [personId],
  );

  // Tell the shop he is here: once he is known, and again after "scan again".
  useEffect(() => {
    if (!person || joined) return;
    let live = true;
    api<Joined>(`/join/${shopId}`, { person_id: person.id, name: person.name })
      .then((j) => {
        if (!live) return;
        setJoined(j);
        const a = pendingAsk.current;
        pendingAsk.current = null;
        if (a) void sendAsk(j.scan_id, a);
      })
      .catch((e: unknown) => {
        if (live) setError(e instanceof ApiError ? e.message : "Could not reach the shop.");
      });
    return () => {
      live = false;
    };
  }, [person, joined, shopId, sendAsk]);

  const scan = usePoll<ScanState>(
    joined && !outcome ? `/scans/${joined.scan_id}` : null,
    1500,
  );
  const state = scan.data?.state;
  const entry = scan.data?.entry ?? null;
  const asked = scan.data?.asked_paise ?? null;
  // His yes to exactly what she asked: already agreed by both, no sheet.
  const agreed =
    state === "recorded" && entry?.status === "confirmed" && scan.data?.answer === "yes";
  const shown: Outcome | null = outcome ?? (agreed && entry ? { kind: "confirmed", entry } : null);

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
          <div className="mt-4">
            <AskFields rupees={rupees} setRupees={setRupees} note={note} setNote={setNote} />
          </div>
          <div className="mt-3.5">
            <Pill
              onClick={() => {
                pendingAsk.current = askOf(rupees, note);
                newPerson(name);
              }}
              disabled={!name.trim()}
            >
              {askOf(rupees, note)
                ? `Ask for ${formatPaise(Number(rupees) * 100)} udhaar`
                : "Continue"}
            </Pill>
          </div>
        </Card>
      </CustomerShell>
    );
  }

  return (
    <CustomerShell heading={heading}>
      {error ? <Notice tone="warn">{error}</Notice> : null}

      {shown ? (
        <Card>
          <div className="py-3 text-center">
            <div className="mx-auto mb-3 grid size-14 place-items-center rounded-full bg-ok-bg text-paid [&_svg]:size-7">
              <Check />
            </div>
            <p className="text-[21px] font-extrabold tracking-[-0.03em]">
              {shown.kind === "confirmed" ? "In both books" : "Marked as not right"}
            </p>
            <p className="mt-1.5 text-[12.5px] font-medium leading-normal text-sub">
              {agreed && !outcome
                ? `You asked for ${formatPaise(shown.entry.amount_paise)} and ${shown.entry.shop_name} said yes. Nothing here promises a date.`
                : shown.kind === "confirmed"
                  ? `${formatPaise(shown.entry.amount_paise)} at ${shown.entry.shop_name}, confirmed by you. Nothing here promises a date.`
                  : `${shown.entry.shop_name} has been told. Nothing is agreed until you both are.`}
            </p>
          </div>
        </Card>
      ) : state === "left" || state === "expired" || state === "declined" ? (
        <Card>
          <p className="text-[15px] font-extrabold">
            {state === "declined" && asked
              ? `${shopName} said no to ${formatPaise(asked)}.`
              : state === "left"
                ? "You left the counter."
                : "That scan has expired."}
          </p>
          {state === "declined" ? (
            <p className="mt-1 text-[12.5px] font-medium text-sub">Nothing was written.</p>
          ) : null}
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
                {asked
                  ? `You asked for ${formatPaise(asked)}. ${shopName} will say yes or no on their screen.`
                  : "They will enter the amount. You confirm it on this screen."}
              </p>
            </div>
          </Card>
          {joined && !asked ? (
            <Card title="Taking something now?" tight>
              <AskFields rupees={rupees} setRupees={setRupees} note={note} setNote={setNote} />
              <div className="mt-3.5">
                <Pill
                  onClick={() => {
                    const a = askOf(rupees, note);
                    if (a) void sendAsk(joined.scan_id, a).then(() => scan.refresh());
                  }}
                  disabled={!askOf(rupees, note) || asking}
                >
                  {askOf(rupees, note)
                    ? `Ask ${shopName} for ${formatPaise(Number(rupees) * 100)} udhaar`
                    : "Ask the shop"}
                </Pill>
              </div>
            </Card>
          ) : null}
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

      {entry && state === "recorded" && entry.status === "recorded" && !outcome ? (
        <Sheet>
          <div className="mb-3.5 flex items-center gap-[11px]">
            <Avatar name={entry.shop_name} />
            <p className="text-[14px] font-extrabold tracking-[-0.02em]">{entry.shop_name}</p>
          </div>
          <p className="mb-1.5 text-[20px] font-extrabold leading-tight tracking-[-0.03em]">
            {entry.shop_name} has recorded {formatPaise(entry.amount_paise)} udhaar against
            your name.
          </p>
          {scan.data?.answer === "changed" && asked ? (
            <p className="mb-1.5 text-[13px] font-bold text-warn">
              You asked for {formatPaise(asked)}; {entry.shop_name} wrote{" "}
              {formatPaise(entry.amount_paise)}.
            </p>
          ) : null}
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
