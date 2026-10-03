"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { MerchantShell } from "@/components/shell/Shell";
import { Card } from "@/components/ui/Card";
import { Dots, Notice } from "@/components/ui/Notice";
import { Pill } from "@/components/ui/Pill";
import { api, ApiError } from "@/lib/api/client";
import type { Plan, Reminder, Tonight } from "@/lib/api/types";
import { SHOP_ID } from "@/lib/config";
import { clockTime, shortDate } from "@/lib/when";

/**
 * A3 · Tomorrow: who gets a reminder, who is left alone, and why.
 *
 * Code decides (the API's domain/tonight.py): a reminder goes only to someone
 * past the longest gap they have ever had. The munshi writes the words, in the
 * customer's language; the shopkeeper can stop any of them. Everyone else is
 * held, and the reason is shown, because "4 of 38" is the point: a tool that
 * messages everyone is the thing BAHI replaces. What was said holds someone too:
 * their promise in chat, or the shopkeeper's note, until the day it names.
 */

const B = ({ children }: { children: React.ReactNode }): React.ReactElement => (
  <b className="font-extrabold text-ink">{children}</b>
);

function Why({ p }: { p: Plan }): React.ReactElement {
  const r = p.rhythm;
  switch (p.why) {
    case "past_longest_gap":
      return (
        <>
          Day <B>{p.day}</B>. {p.display_name} has never gone past <B>{r.max_gap}</B> days
          before. Something has changed: the message asks, it does not chase.
        </>
      );
    case "inside_gap":
      return (
        <>
          Pays every <B>{r.median_gap}</B> days, across <B>{r.n}</B> gaps. Today is day{" "}
          {p.day}.
        </>
      );
    case "not_confirmed":
      return <>Waiting for {p.display_name} to confirm an entry. A reminder waits for that.</>;
    case "disputed":
      return <>{p.display_name} says an entry is wrong. Sort it out in the chat first.</>;
    case "too_new":
      return r.n ? (
        <>
          Only <B>{r.n}</B> {r.n === 1 ? "gap" : "gaps"} so far: too early to know{" "}
          {p.display_name}&apos;s rhythm.
        </>
      ) : (
        <>No payments yet to read a rhythm from.</>
      );
    case "no_phone":
      return <>Kept by name only: there is no phone to send to.</>;
    case "reminded":
      return (
        <>
          Reminded {p.reminded_on ? shortDate(p.reminded_on) : "recently"}. One reminder a gap,
          never a stream.
        </>
      );
    // Past the gap, but something was said: BAHI waits for it (M3, memory).
    case "promised":
      return (
        <>
          {p.display_name} said in chat: <B>&ldquo;{p.wait?.body}&rdquo;</B>. Nothing is sent
          until after <B>{p.wait ? shortDate(p.wait.until) : "that day"}</B>.
        </>
      );
    case "asked_to_wait":
      return (
        <>
          Your note: <B>&ldquo;{p.wait?.body}&rdquo;</B>. Nothing is sent until after{" "}
          <B>{p.wait ? shortDate(p.wait.until) : "that day"}</B>.
        </>
      );
  }
}

function chip(r: Reminder | null, sending: boolean): { text: string; tone: string } {
  if (r?.status === "sent") return { text: `Sent`, tone: "bg-ok-bg text-ok" };
  if (r?.status === "stopped") return { text: "Stopped", tone: "bg-quiet-bg text-quiet" };
  if (r) return { text: `Send ${clockTime(r.send_at)}`, tone: "bg-warn-bg text-warn" };
  return sending
    ? { text: "Writing…", tone: "bg-quiet-bg text-quiet" }
    : { text: "Hold", tone: "bg-ok-bg text-ok" };
}

function SendCard({
  p,
  busy,
  onStop,
}: {
  p: Plan;
  busy: boolean;
  onStop: (r: Reminder, stop: boolean) => void;
}): React.ReactElement {
  const r = p.reminder;
  const c = chip(r, true);
  return (
    <section className="rounded-card border-l-[5px] border-cyan bg-card px-4 py-3.5">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <Link
            href={`/m/chat/${p.customer_id}`}
            className="block truncate text-[17px] font-extrabold tracking-[-0.02em]"
          >
            {p.display_name}
          </Link>
          {p.tag ? <p className="truncate text-[11.5px] font-medium text-sub">{p.tag}</p> : null}
        </div>
        <span className={`flex-none rounded-md px-2.5 py-1 text-[12px] font-extrabold ${c.tone}`}>
          {c.text}
        </span>
      </div>
      <p className="mt-2 text-[13.5px] font-medium leading-normal text-sub">
        {/* Once sent, he is held for a gap; the card still says why it went. */}
        <Why p={r?.status === "sent" ? { ...p, why: "past_longest_gap" } : p} />
      </p>
      {r ? (
        <div className="mt-3 rounded-[12px] bg-tile px-3 py-2.5">
          <p className="text-[11px] font-bold text-sub">
            {r.written === "munshi" ? "The munshi wrote" : "In our words (the munshi was offline)"}
          </p>
          <p
            className={`mt-1 text-[14px] font-semibold leading-snug ${r.status === "stopped" ? "text-sub line-through" : ""}`}
          >
            {r.body}
          </p>
          {r.status !== "sent" ? (
            <button
              type="button"
              disabled={busy}
              onClick={() => onStop(r, r.status !== "stopped")}
              className="mt-2 text-[12.5px] font-extrabold text-cyan-text disabled:opacity-40"
            >
              {r.status === "stopped" ? "Let it go after all" : "Stop this one"}
            </button>
          ) : (
            <Link
              href={`/m/chat/${p.customer_id}`}
              className="mt-2 block text-[12.5px] font-extrabold text-cyan-text"
            >
              In {p.display_name}&apos;s chat →
            </Link>
          )}
        </div>
      ) : null}
    </section>
  );
}

function HoldRow({ p }: { p: Plan }): React.ReactElement {
  return (
    <Link
      href={`/m/chat/${p.customer_id}`}
      className="block border-b border-hair py-2.5 last:border-b-0"
    >
      <div className="flex items-center justify-between gap-3">
        <p className="truncate text-[14px] font-extrabold">{p.display_name}</p>
        <span className="flex-none rounded-md bg-ok-bg px-2 py-0.5 text-[11px] font-extrabold text-ok">
          Hold
        </span>
      </div>
      <p className="mt-0.5 text-[12.5px] font-medium leading-snug text-sub">
        <Why p={p} />
      </p>
    </Link>
  );
}

export function TonightScreen(): React.ReactElement {
  const [t, setT] = useState<Tonight | null>(null);
  const [writing, setWriting] = useState(true);
  const [busy, setBusy] = useState(false);
  const [news, setNews] = useState<{ tone: "ok" | "warn"; text: string } | null>(null);
  const [showAll, setShowAll] = useState(false);

  const load = useCallback(async () => {
    setT(await api<Tonight>(`/shops/${SHOP_ID}/tonight`));
  }, []);

  // The list at once, then the munshi writes the reminders (the 11 pm run).
  useEffect(() => {
    void api<Tonight>(`/shops/${SHOP_ID}/tonight`)
      .then((first) => {
        setT(first);
        return api<Tonight>(`/shops/${SHOP_ID}/tonight`, {});
      })
      .then(setT)
      .catch((e: unknown) =>
        setNews({ tone: "warn", text: e instanceof ApiError ? e.message : "Couldn't work it out." }),
      )
      .finally(() => setWriting(false));
  }, []);

  async function stop(r: Reminder, stopping: boolean): Promise<void> {
    setBusy(true);
    try {
      await api(`/shops/${SHOP_ID}/reminders/${r.id}/${stopping ? "stop" : "resume"}`, {});
      await load();
    } finally {
      setBusy(false);
    }
  }

  async function sendNow(): Promise<void> {
    setBusy(true);
    try {
      const out = await api<{ sent: number }>(`/shops/${SHOP_ID}/tonight/send-now`, {});
      setNews({
        tone: "ok",
        text: out.sent
          ? `${out.sent} ${out.sent === 1 ? "reminder" : "reminders"} sent. Each is in that customer's chat.`
          : "Nothing to send: every reminder has gone or was stopped.",
      });
      await load();
    } finally {
      setBusy(false);
    }
  }

  const top = (t?.plans.filter((p) => p.send || p.reminder?.status === "sent") ?? []).sort(
    (a, b) => a.display_name.localeCompare(b.display_name),
  );
  const held = t?.plans.filter((p) => !top.includes(p)) ?? [];
  const special = held.filter((p) => p.why !== "inside_gap");
  const inside = held.filter((p) => p.why === "inside_gap");
  const planned = top.some((p) => p.reminder?.status === "planned");

  return (
    <MerchantShell
      heading={{
        title: "Tomorrow",
        sub: t
          ? `Worked out at ${clockTime(t.worked_out_at)} · ${t.sending_count} of ${t.owing_count}`
          : "Working it out…",
        back: "/m",
      }}
    >
      {news ? <Notice tone={news.tone}>{news.text}</Notice> : null}
      {!t ? (
        <Card>
          <Dots />
        </Card>
      ) : (
        <>
          {writing ? (
            <Notice>The munshi is writing each reminder in the customer&apos;s words…</Notice>
          ) : null}
          {top.length ? (
            top.map((p) => (
              <SendCard key={p.customer_id} p={p} busy={busy} onStop={(r, s) => void stop(r, s)} />
            ))
          ) : (
            <Notice tone="ok">Nobody needs a reminder tomorrow.</Notice>
          )}

          {special.length ? (
            <Card title="Held, and why" tight>
              {special.map((p) => (
                <HoldRow key={p.customer_id} p={p} />
              ))}
            </Card>
          ) : null}

          <Card tight>
            <p className="text-[13.5px] font-semibold leading-normal text-sub">
              <b className="font-extrabold text-ink">{inside.length}</b> customers are inside
              their own normal gap. Nothing is sent to them.
            </p>
            <button
              type="button"
              onClick={() => setShowAll((s) => !s)}
              className="mt-2 text-[12.5px] font-extrabold text-cyan-text"
            >
              {showAll ? "Hide them" : "See each one's rhythm"}
            </button>
            {showAll ? (
              <div className="mt-2">
                {inside.map((p) => (
                  <HoldRow key={p.customer_id} p={p} />
                ))}
              </div>
            ) : null}
          </Card>

          <div className="flex flex-col gap-1.5">
            <Pill onClick={() => void sendNow()} disabled={busy || writing || !planned}>
              Send now
            </Pill>
            <p className="text-center text-[11.5px] font-medium text-sub">
              For the demo. Each reminder otherwise goes at its own hour.
            </p>
          </div>
        </>
      )}
    </MerchantShell>
  );
}
