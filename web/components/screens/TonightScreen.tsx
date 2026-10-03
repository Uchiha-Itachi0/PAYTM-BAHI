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

/** The day `n` days after `iso` (YYYY-MM-DD), as YYYY-MM-DD. */
function addDays(iso: string, n: number): string {
  const d = new Date(`${iso}T12:00:00Z`);
  d.setUTCDate(d.getUTCDate() + n);
  return d.toISOString().slice(0, 10);
}

/** HH:MM of a send time, in India's time. */
function hhmm(at: string): string {
  return new Date(at).toLocaleTimeString("en-GB", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
    timeZone: "Asia/Kolkata",
  });
}

const PAUSES = [
  { days: 7, label: "1 week" },
  { days: 14, label: "2 weeks" },
  { days: 30, label: "1 month" },
] as const;

function SendCard({
  p,
  today,
  busy,
  onStop,
  onEdit,
  onPause,
}: {
  p: Plan;
  today: string;
  busy: boolean;
  onStop: (r: Reminder, stop: boolean) => void;
  onEdit: (r: Reminder, body: string, at: string) => Promise<void>;
  onPause: (p: Plan, until: string) => Promise<void>;
}): React.ReactElement {
  const r = p.reminder;
  const c = chip(r, true);
  const [mode, setMode] = useState<"idle" | "edit" | "pause">("idle");
  const [body, setBody] = useState(r?.body ?? "");
  const [at, setAt] = useState(r ? hhmm(r.send_at) : "10:00");
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
            {r.written === "munshi"
              ? "The munshi wrote"
              : r.written === "shop"
                ? "In your words"
                : "In our words (the munshi was offline)"}
          </p>
          <p
            className={`mt-1 text-[14px] font-semibold leading-snug ${r.status === "stopped" ? "text-sub line-through" : ""}`}
          >
            {r.body}
          </p>
          {r.status !== "sent" && mode === "edit" ? (
            <form
              className="mt-2 flex flex-col gap-2"
              onSubmit={(ev) => {
                ev.preventDefault();
                void onEdit(r, body, at).then(() => setMode("idle"));
              }}
            >
              <textarea
                value={body}
                onChange={(ev) => setBody(ev.target.value)}
                rows={3}
                maxLength={300}
                aria-label="The reminder, in your words"
                className="rounded-[11px] border-[1.5px] border-line bg-white px-3 py-2 text-[14px] font-semibold outline-none focus:border-cyan"
              />
              <label className="flex items-center gap-2 text-[12.5px] font-bold text-sub">
                Send at
                <input
                  type="time"
                  value={at}
                  min="09:00"
                  max="20:00"
                  onChange={(ev) => setAt(ev.target.value)}
                  className="rounded-[9px] border-[1.5px] border-line bg-white px-2 py-1 text-[14px] font-bold text-ink"
                />
                <span className="font-medium">between 9 am and 8 pm</span>
              </label>
              <div className="flex gap-2">
                <button
                  type="submit"
                  disabled={busy || !body.trim()}
                  className="flex-1 rounded-pill bg-navy px-3 py-2 text-[13.5px] font-extrabold text-white disabled:opacity-40"
                >
                  Save
                </button>
                <button
                  type="button"
                  onClick={() => setMode("idle")}
                  className="rounded-pill px-3 py-2 text-[13px] font-bold text-sub"
                >
                  Back
                </button>
              </div>
            </form>
          ) : null}
          {r.status !== "sent" && mode === "pause" ? (
            <div className="mt-2 flex flex-col gap-2">
              <p className="text-[12.5px] font-semibold text-sub">
                No reminders to {p.display_name} for…
              </p>
              <div className="flex flex-wrap gap-2">
                {PAUSES.map((x) => (
                  <button
                    key={x.days}
                    type="button"
                    disabled={busy}
                    onClick={() => void onPause(p, addDays(today, x.days))}
                    className="rounded-pill border-[1.5px] border-cyan bg-white px-3 py-1.5 text-[13px] font-extrabold text-cyan-text disabled:opacity-40"
                  >
                    {x.label}
                  </button>
                ))}
                <button
                  type="button"
                  onClick={() => setMode("idle")}
                  className="px-2 text-[13px] font-bold text-sub"
                >
                  Back
                </button>
              </div>
            </div>
          ) : null}
          {r.status !== "sent" && mode === "idle" ? (
            <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1">
              {r.status !== "stopped" ? (
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => {
                    setBody(r.body);
                    setAt(hhmm(r.send_at));
                    setMode("edit");
                  }}
                  className="text-[12.5px] font-extrabold text-cyan-text disabled:opacity-40"
                >
                  Edit words or time
                </button>
              ) : null}
              <button
                type="button"
                disabled={busy}
                onClick={() => onStop(r, r.status !== "stopped")}
                className="text-[12.5px] font-extrabold text-cyan-text disabled:opacity-40"
              >
                {r.status === "stopped" ? "Let it go after all" : "Stop this one"}
              </button>
              <button
                type="button"
                disabled={busy}
                onClick={() => setMode("pause")}
                className="text-[12.5px] font-extrabold text-cyan-text disabled:opacity-40"
              >
                Pause {p.display_name}
              </button>
            </div>
          ) : r.status === "sent" ? (
            <Link
              href={`/m/chat/${p.customer_id}`}
              className="mt-2 block text-[12.5px] font-extrabold text-cyan-text"
            >
              In {p.display_name}&apos;s chat →
            </Link>
          ) : null}
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

  async function edit(r: Reminder, body: string, at: string): Promise<void> {
    setBusy(true);
    setNews(null);
    try {
      await api(`/shops/${SHOP_ID}/reminders/${r.id}`, {
        body: body.trim() === r.body ? null : body.trim(),
        at,
      });
      await load();
    } catch (e) {
      setNews({ tone: "warn", text: e instanceof ApiError ? e.message : "Couldn't save it." });
    } finally {
      setBusy(false);
    }
  }

  async function pause(p: Plan, until: string): Promise<void> {
    setBusy(true);
    setNews(null);
    try {
      await api(`/shops/${SHOP_ID}/customers/${p.customer_id}/pause`, { until });
      setNews({
        tone: "ok",
        text: `Paused. No reminder goes to ${p.display_name} until after ${shortDate(until)}.`,
      });
      await load();
    } catch (e) {
      setNews({ tone: "warn", text: e instanceof ApiError ? e.message : "Couldn't pause." });
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
              <SendCard
                key={p.customer_id}
                p={p}
                today={t.today}
                busy={busy}
                onStop={(r, s) => void stop(r, s)}
                onEdit={edit}
                onPause={pause}
              />
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
