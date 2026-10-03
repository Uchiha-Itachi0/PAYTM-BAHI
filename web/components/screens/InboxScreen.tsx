"use client";

import Link from "next/link";
import { useState } from "react";

import { Mic, Search } from "@/components/icons";
import { MerchantShell } from "@/components/shell/Shell";
import { Card } from "@/components/ui/Card";
import { Dots, Notice } from "@/components/ui/Notice";
import { Avatar } from "@/components/ui/Row";
import { StickyPill } from "@/components/ui/StickyPill";
import { api, usePoll } from "@/lib/api/client";
import type { Customer, Inbox, InboxRow } from "@/lib/api/types";
import { SHOP_ID } from "@/lib/config";
import { formatPaise } from "@/lib/money";
import { clockTime, shortDate, shortWhen } from "@/lib/when";

/**
 * C1 · Messages. Every customer thread, the latest first, live.
 *
 * A row says where things stand in a few words: the last message, or the entry
 * it was about ("₹150 · waiting on him since 20 Sep"), or a reminder planned
 * for tomorrow. "Needs reply" is someone who wrote last, or says an entry is
 * wrong. New chat starts a thread with anyone on BAHI.
 */

function line(r: InboxRow): { mark: "ok" | "wait" | "warn" | null; text: string } {
  if (r.reminder_at) return { mark: "warn", text: `Reminder scheduled · ${clockTime(r.reminder_at)}` };
  const e = r.entry;
  // A line about an entry (a payment, a dispute) says what happened.
  if (r.kind === "entry" && !r.card)
    return { mark: e?.status === "disputed" ? "warn" : "ok", text: r.body };
  if (r.kind === "entry" && e) {
    const amount = formatPaise(e.amount_paise);
    if (e.status === "confirmed") return { mark: "ok", text: `${amount} confirmed` };
    if (e.status === "recorded")
      return { mark: "wait", text: `${amount} · waiting since ${shortDate(e.recorded_at)}` };
    if (e.status === "disputed") return { mark: "warn", text: `${amount} · says it's not right` };
    if (e.status === "settled") return { mark: "ok", text: r.body };
    return { mark: null, text: r.body };
  }
  const who = r.author === "shop" ? "You: " : r.kind === "reminder" ? "Reminder: " : "";
  return { mark: null, text: who + r.body };
}

const MARK = {
  ok: "bg-paid text-white",
  wait: "bg-quiet text-white",
  warn: "bg-warn text-white",
} as const;

const GLYPH = { ok: "✓", wait: "?", warn: "!" } as const;

function Line({ r, today }: { r: InboxRow; today: string }): React.ReactElement {
  const { mark, text } = line(r);
  return (
    <Link
      href={`/m/chat/${r.customer_id}`}
      className="flex items-center gap-[11px] border-b border-hair py-3 last:border-b-0"
    >
      <Avatar name={r.display_name} />
      <div className="min-w-0 flex-1">
        <div className="flex items-baseline justify-between gap-2">
          <p className="truncate text-[14.5px] font-extrabold tracking-[-0.015em]">
            {r.display_name}
          </p>
          <span className="flex-none text-[11.5px] font-medium text-sub">
            {shortWhen(r.sent_at, today)}
          </span>
        </div>
        <div className="mt-0.5 flex items-center gap-1.5">
          {mark ? (
            <span
              aria-hidden="true"
              className={`grid size-4 flex-none place-items-center rounded-full text-[10px] font-extrabold ${MARK[mark]}`}
            >
              {GLYPH[mark]}
            </span>
          ) : null}
          <p
            className={`min-w-0 flex-1 truncate text-[12.5px] ${r.unread ? "font-bold text-ink" : "font-medium text-sub"}`}
          >
            {text}
          </p>
          {r.unread ? (
            <span className="grid min-w-5 flex-none place-items-center rounded-full bg-cyan px-1 text-[11px] font-extrabold leading-5 text-white">
              {r.unread}
            </span>
          ) : null}
        </div>
      </div>
    </Link>
  );
}

export function InboxScreen(): React.ReactElement {
  const inbox = usePoll<Inbox>(`/shops/${SHOP_ID}/inbox`);
  const [tab, setTab] = useState<"all" | "reply">("all");
  const [search, setSearch] = useState("");
  const [picking, setPicking] = useState(false);
  const [book, setBook] = useState<Customer[]>([]);

  const q = search.trim().toLowerCase();
  const rows = (inbox.data?.rows ?? [])
    .filter((r) => tab === "all" || r.needs_reply)
    .filter((r) => !q || r.display_name.toLowerCase().includes(q));
  const threaded = new Set(inbox.data?.rows.map((r) => r.customer_id));
  const others = book
    .filter((c) => c.joined === "linked" && !threaded.has(c.id))
    .filter((c) => !q || c.display_name.toLowerCase().includes(q))
    .slice(0, 8);

  async function readAll(): Promise<void> {
    await api(`/shops/${SHOP_ID}/inbox/read`, {});
    inbox.refresh();
  }

  function newChat(): void {
    setPicking((p) => !p);
    if (!book.length) void api<Customer[]>(`/shops/${SHOP_ID}/customers`).then(setBook);
  }

  return (
    <MerchantShell
      heading={{
        title: "Messages",
        back: "/m",
        action: (
          <button type="button" onClick={newChat} className="text-[13.5px] font-extrabold text-cyan-text">
            {picking ? "Close" : "New chat"}
          </button>
        ),
      }}
    >
      <Card tight>
        <label className="flex items-center gap-2 rounded-[11px] border-[1.5px] border-line bg-white px-3 py-2 focus-within:border-cyan">
          <Search className="size-[18px] text-sub" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search a customer"
            aria-label="Search a customer"
            className="min-w-0 flex-1 bg-transparent text-[14px] font-semibold outline-none placeholder:font-medium placeholder:text-sub"
          />
        </label>

        {picking ? (
          <div className="mt-3">
            <p className="mb-1 text-[12px] font-bold text-sub">Start a chat with</p>
            {others.length ? (
              others.map((c) => (
                <Link
                  key={c.id}
                  href={`/m/chat/${c.id}`}
                  className="flex items-center gap-[11px] border-b border-hair py-2.5 last:border-b-0"
                >
                  <Avatar name={c.display_name} />
                  <div className="min-w-0">
                    <p className="truncate text-[14px] font-bold">{c.display_name}</p>
                    <p className="truncate text-[11.5px] font-medium text-sub">{c.tag}</p>
                  </div>
                </Link>
              ))
            ) : (
              <p className="py-2 text-[12.5px] font-medium text-sub">
                {book.length ? "Everyone on BAHI already has a thread." : "Loading your book…"}
              </p>
            )}
          </div>
        ) : null}

        <div className="mt-3 flex items-center gap-4 border-b border-hair">
          {(["all", "reply"] as const).map((t) => (
            <button
              key={t}
              type="button"
              onClick={() => setTab(t)}
              className={`-mb-px border-b-[3px] pb-2 text-[14px] font-extrabold ${tab === t ? "border-cyan text-ink" : "border-transparent text-sub"}`}
            >
              {t === "all" ? "All" : "Needs reply"}
            </button>
          ))}
          <button
            type="button"
            onClick={() => void readAll()}
            disabled={!inbox.data?.unread}
            className="ml-auto pb-2 text-[12.5px] font-extrabold text-cyan-text disabled:text-sub"
          >
            Mark all read
          </button>
        </div>

        {inbox.data ? (
          rows.length ? (
            <div>
              {rows.map((r) => (
                <Line key={r.customer_id} r={r} today={inbox.data!.today} />
              ))}
            </div>
          ) : (
            <p className="py-6 text-center text-[12.5px] font-medium text-sub">
              {tab === "reply" ? "Nobody is waiting on you." : "No threads yet."}
            </p>
          )
        ) : inbox.error ? (
          <div className="mt-3">
            <Notice tone="warn">Cannot reach your messages: {inbox.error}</Notice>
          </div>
        ) : (
          <div className="py-6">
            <Dots />
          </div>
        )}
      </Card>
      <StickyPill icon={<Mic />} href="/m/add?listen=1">
        Add by voice
      </StickyPill>
    </MerchantShell>
  );
}
