"use client";

import Link from "next/link";
import { useState } from "react";

import { Chat, Check } from "@/components/icons";
import { CustomerShell } from "@/components/shell/Shell";
import { Card } from "@/components/ui/Card";
import { Figure } from "@/components/ui/Figure";
import { Dots, Notice } from "@/components/ui/Notice";
import { Pill } from "@/components/ui/Pill";
import { api, ApiError, usePoll } from "@/lib/api/client";
import type { MyShop, MyUdhaar, Paid, ThreadEntry } from "@/lib/api/types";
import { formatPaise } from "@/lib/money";
import { usePerson } from "@/lib/person";
import { clockTime, fullDate, shortDate } from "@/lib/when";

/**
 * B2 · My udhaar: what he owes across every shop, each entry, and Pay.
 * B3 · Cleared: what he just paid, and what is still open elsewhere.
 *
 * Every figure is from the API. Paying pays everything he owes that shop, by UPI,
 * each entry named; a disputed entry waits until it is agreed. An entry past the
 * limitation line is shown struck through: kept, and claiming nothing.
 * Invitations from shops wait at the top for his yes.
 */

function EntryLine({ e }: { e: ThreadEntry }): React.ReactElement {
  const paid = e.status === "settled";
  const title = e.expired
    ? "Expired"
    : paid
      ? "Paid in full"
      : e.status === "corrected"
        ? "Replaced by a correction"
        : (e.note ?? "Udhaar");
  const sub = e.expired
    ? fullDate(e.recorded_at)
    : paid && e.last_paid_at
      ? `${shortDate(e.last_paid_at)} · ${e.last_method === "cash" ? "cash" : "UPI"}`
      : e.status === "recorded"
        ? `${shortDate(e.recorded_at)} · waiting for your yes`
        : e.status === "disputed"
          ? `${shortDate(e.recorded_at)} · you said it's wrong`
          : e.status === "confirmed"
            ? `${shortDate(e.recorded_at)} · confirmed by you`
            : shortDate(e.recorded_at);
  return (
    <div className="flex items-start justify-between gap-3 border-b border-hair py-3 last:border-b-0">
      <div className="min-w-0">
        <p className={`flex items-center gap-2 text-[14.5px] font-extrabold ${e.expired ? "text-sub" : ""}`}>
          {title}
          {e.expired ? (
            <span className="rounded-md bg-quiet-bg px-2 py-0.5 text-[11px] font-bold text-quiet">
              No longer claimable
            </span>
          ) : null}
        </p>
        <p className="mt-0.5 text-[12px] font-medium text-sub">{sub}</p>
      </div>
      <p
        className={`flex-none text-[15px] font-extrabold tabular-nums ${paid ? "text-paid" : e.expired || e.status === "corrected" ? "text-sub line-through" : ""}`}
      >
        {formatPaise(e.amount_paise)}
      </p>
    </div>
  );
}

function Cleared({
  paid,
  onBack,
}: {
  paid: Paid;
  onBack: () => void;
}): React.ReactElement {
  return (
    <CustomerShell heading={{ title: "Cleared", sub: paid.shop.name, back: "/c/udhaar" }}>
      <Card>
        <div className="py-3 text-center">
          <div className="mx-auto mb-3 grid size-16 place-items-center rounded-full bg-ok-bg text-paid [&_svg]:size-8">
            <Check />
          </div>
          <p className="text-[26px] font-extrabold tracking-[-0.03em]">
            {formatPaise(paid.amount_paise)} paid
          </p>
          <p className="mt-1.5 text-[13px] font-medium leading-normal text-sub">
            {fullDate(paid.paid_at)}, {clockTime(paid.paid_at)} · UPI
            <br />
            {paid.shop.name} has been told.
          </p>
        </div>
      </Card>
      <Card title={paid.shop.name} tight>
        <div className="flex items-start justify-between">
          <div>
            <p className="text-[14.5px] font-extrabold">Nothing outstanding</p>
            <p className="mt-0.5 text-[12px] font-medium text-sub">
              {paid.settled_in === 0
                ? "Settled the same day"
                : `Settled in ${paid.settled_in} ${paid.settled_in === 1 ? "day" : "days"}`}
            </p>
          </div>
          <p className="text-[15px] font-extrabold tabular-nums">{formatPaise(0)}</p>
        </div>
      </Card>
      {paid.elsewhere.length ? (
        <Card title="Still open elsewhere" tight>
          {paid.elsewhere.map((s) => (
            <div
              key={s.shop.id}
              className="flex items-start justify-between border-b border-hair py-2.5 last:border-b-0"
            >
              <div>
                <p className="text-[14.5px] font-extrabold">{s.shop.name}</p>
                {s.day !== null ? (
                  <p className="mt-0.5 text-[12px] font-medium text-sub">day {s.day}</p>
                ) : null}
              </div>
              <p className="text-[15px] font-extrabold tabular-nums">
                {formatPaise(s.balance_paise)}
              </p>
            </div>
          ))}
        </Card>
      ) : null}
      <Pill tone="outline" onClick={onBack}>
        Back to my udhaar
      </Pill>
    </CustomerShell>
  );
}

export function MyUdhaarScreen(): React.ReactElement {
  const person = usePerson();
  const mine = usePoll<MyUdhaar>(person ? `/people/${person.id}/udhaar` : null);
  const [picked, setPicked] = useState<string | null>(null);
  const [paid, setPaid] = useState<Paid | null>(null);
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);

  const heading = { title: "My udhaar", back: "/c" };
  const m = mine.data;
  const shop: MyShop | undefined = m?.shops.find((s) => s.shop.id === picked) ?? m?.shops[0];
  const owing = m?.shops.filter((s) => s.balance_paise > 0) ?? [];

  async function pay(s: MyShop): Promise<void> {
    if (!person) return;
    setBusy(true);
    setProblem(null);
    try {
      setPaid(await api<Paid>(`/shops/${s.shop.id}/pay`, { person_id: person.id }));
      mine.refresh();
    } catch (e) {
      setProblem(e instanceof ApiError ? e.message : "The payment didn't go through.");
    } finally {
      setBusy(false);
    }
  }

  async function invite(shopId: string, yes: boolean): Promise<void> {
    if (!person) return;
    await api(`/shops/${shopId}/invite/${yes ? "accept" : "decline"}`, { person_id: person.id });
    mine.refresh();
  }

  if (paid) return <Cleared paid={paid} onBack={() => setPaid(null)} />;

  if (person === null) {
    return (
      <CustomerShell heading={heading}>
        <Notice>
          Whose phone is this? Pick someone on the{" "}
          <Link href="/c" className="font-extrabold text-cyan-text">
            home screen
          </Link>
          , or scan a shop&apos;s udhaar QR.
        </Notice>
      </CustomerShell>
    );
  }

  return (
    <CustomerShell heading={heading}>
      {problem ? <Notice tone="warn">{problem}</Notice> : null}
      {!m ? (
        <Card>
          <Dots />
        </Card>
      ) : (
        <>
          {m.invites.map((i) => (
            <Card key={i.shop.id} tight>
              <p className="text-[15px] font-extrabold tracking-[-0.02em]">
                {i.shop.name} wants to keep your udhaar book with you
              </p>
              <p className="mt-1 text-[12.5px] font-medium leading-normal text-sub">
                You&apos;d be in their book as {i.display_name}. Nothing can be recorded against
                you unless you say yes, and you confirm every entry yourself.
              </p>
              <div className="mt-3 flex gap-2">
                <div className="flex-1">
                  <Pill onClick={() => void invite(i.shop.id, true)}>Yes, add me</Pill>
                </div>
                <div className="flex-1">
                  <Pill tone="outline" onClick={() => void invite(i.shop.id, false)}>
                    Not now
                  </Pill>
                </div>
              </div>
            </Card>
          ))}

          <Card>
            <Figure
              label={
                owing.length > 1
                  ? `You owe, across ${owing.length} shops`
                  : m.shops.length
                    ? "You owe"
                    : "You owe nothing"
              }
              value={formatPaise(m.total_paise)}
              fine={
                owing.length
                  ? owing.map((s) => `${s.shop.name} ${formatPaise(s.balance_paise)}`).join(" · ")
                  : undefined
              }
            />
          </Card>

          {shop ? (
            <Card tight>
              {m.shops.length > 1 ? (
                <div className="mb-1 flex gap-4 overflow-x-auto border-b border-hair [scrollbar-width:none]">
                  {m.shops.map((s) => (
                    <button
                      key={s.shop.id}
                      type="button"
                      onClick={() => setPicked(s.shop.id)}
                      className={`-mb-px flex-none border-b-[3px] pb-2 text-[14.5px] font-extrabold ${s.shop.id === shop.shop.id ? "border-cyan text-ink" : "border-transparent text-sub"}`}
                    >
                      {s.shop.name.split(" ").slice(0, 2).join(" ")}
                    </button>
                  ))}
                </div>
              ) : null}
              {shop.entries.length ? (
                shop.entries.map((e) => <EntryLine key={e.id} e={e} />)
              ) : (
                <p className="py-3 text-[12.5px] font-medium text-sub">Nothing here yet.</p>
              )}
              <Link
                href={`/c/chat/${shop.shop.id}`}
                className="mt-2 flex items-center justify-center gap-1.5 border-t border-hair pt-3 text-[13.5px] font-extrabold text-cyan-text [&_svg]:size-4"
              >
                <Chat />
                Chat with {shop.shop.name}
                {shop.unread ? (
                  <span className="grid min-w-5 place-items-center rounded-full bg-cyan px-1 text-[11px] font-extrabold leading-5 text-white">
                    {shop.unread}
                  </span>
                ) : null}
              </Link>
            </Card>
          ) : (
            <Notice>
              You&apos;re not in any shop&apos;s book yet. Scan a shop&apos;s udhaar QR at the
              counter.
            </Notice>
          )}

          {shop && shop.balance_paise > 0 ? (
            <Pill tone="cyan" onClick={() => void pay(shop)} disabled={busy}>
              Pay {formatPaise(shop.balance_paise)} now
            </Pill>
          ) : null}
        </>
      )}
    </CustomerShell>
  );
}
