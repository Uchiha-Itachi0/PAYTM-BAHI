"use client";

import { useCallback, useEffect, useState } from "react";

import { Search } from "@/components/icons";
import { MerchantShell } from "@/components/shell/Shell";
import { Card } from "@/components/ui/Card";
import { Field } from "@/components/ui/Field";
import { Figure } from "@/components/ui/Figure";
import { Dots, Notice } from "@/components/ui/Notice";
import { Pill } from "@/components/ui/Pill";
import { Avatar } from "@/components/ui/Row";
import { api, ApiError } from "@/lib/api/client";
import type { Account, CustomerDetail, ThreadEntry } from "@/lib/api/types";
import { SHOP_ID } from "@/lib/config";
import { formatPaise } from "@/lib/money";
import { fullDate, shortDate } from "@/lib/when";

/**
 * One customer, as the shop keeps them: on BAHI or not, what they owe, their
 * entries, and what the shop calls them.
 *
 * Someone kept by name only has no phone, so nothing reaches them. Adding their
 * mobile number or UPI ID sends an invite to their Paytm; the number is only used
 * to find the account. Until they accept, the shop still writes their udhaar by
 * name. When they do, the row is theirs, and each open entry goes to their phone
 * for their own yes.
 */

function lookable(q: string): boolean {
  return q.includes("@") ? /^[^@\s]+@[^@\s]+$/.test(q.trim()) : q.replace(/\D/g, "").length >= 10;
}

function entryLine(e: ThreadEntry): string {
  const on = shortDate(e.recorded_at);
  if (e.expired) return `${fullDate(e.recorded_at)} · no longer claimable`;
  if (e.status === "settled") return `${on} · paid`;
  if (e.status === "corrected") return `${on} · replaced by a correction`;
  if (e.status === "disputed") return `${on} · they say it's wrong`;
  if (e.paid_paise > 0) return `${on} · ${formatPaise(e.paid_paise)} paid`;
  return `${on} · ${e.status === "confirmed" ? "confirmed" : "not confirmed"}`;
}

export function CustomerScreen({ customerId }: { customerId: string }): React.ReactElement {
  const path = `/shops/${SHOP_ID}/customers/${customerId}`;
  const [c, setC] = useState<CustomerDetail | null>(null);
  const [name, setName] = useState("");
  const [tag, setTag] = useState("");
  const [q, setQ] = useState("");
  const [found, setFound] = useState<{ q: string; account: Account | null } | null>(null);
  const [busy, setBusy] = useState(false);
  const [news, setNews] = useState<{ tone: "ok" | "warn"; text: string } | null>(null);

  const take = useCallback((d: CustomerDetail) => {
    setC(d);
    setName(d.display_name);
    setTag(d.tag ?? "");
  }, []);

  useEffect(() => {
    void api<CustomerDetail>(path).then(take);
  }, [path, take]);

  useEffect(() => {
    const query = q.trim();
    if (!lookable(query)) return;
    const timer = setTimeout(() => {
      api<Account>(`/shops/${SHOP_ID}/accounts?q=${encodeURIComponent(query)}`)
        .then((account) => setFound({ q: query, account }))
        .catch(() => setFound({ q: query, account: null }));
    }, 350);
    return () => clearTimeout(timer);
  }, [q]);

  async function act(run: () => Promise<CustomerDetail>, done: string): Promise<void> {
    setBusy(true);
    setNews(null);
    try {
      take(await run());
      setNews({ tone: "ok", text: done });
    } catch (e) {
      setNews({ tone: "warn", text: e instanceof ApiError ? e.message : "That didn't go through." });
    } finally {
      setBusy(false);
    }
  }

  const heading = { title: c?.display_name ?? "…", sub: c?.tag ?? undefined, back: "/m/customers" };
  if (!c) {
    return (
      <MerchantShell heading={heading}>
        <Card>
          <Dots />
        </Card>
      </MerchantShell>
    );
  }

  const shown = found && found.q === q.trim() ? found : null;
  const edited = name.trim() !== c.display_name || (tag.trim() || null) !== c.tag;
  const byName = c.joined === "name_only";

  return (
    <MerchantShell heading={heading}>
      {news ? <Notice tone={news.tone}>{news.text}</Notice> : null}

      <Card>
        <div className="flex items-center gap-3">
          <Avatar name={c.display_name} size="lg" />
          <div className="min-w-0">
            <p className="truncate text-[18px] font-extrabold tracking-[-0.02em]">
              {c.display_name}
            </p>
            <p className="text-[12.5px] font-semibold text-sub">
              {c.joined === "linked"
                ? "On BAHI · sees each entry and confirms it"
                : c.joined === "invited"
                  ? "Invited · nothing is recorded until they accept"
                  : c.invite_pending
                    ? "Invite sent · waiting for their yes"
                    : "Name only · no phone, nothing reaches them"}
            </p>
          </div>
        </div>
        <div className="mt-4">
          <Figure
            label="Owes you"
            value={formatPaise(c.balance_paise)}
            fine={c.balance_paise && c.day !== null ? `day ${c.day}` : undefined}
          />
        </div>
        {c.joined === "linked" ? (
          <div className="mt-3.5">
            <Pill href={`/m/chat/${c.id}`}>Open chat</Pill>
          </div>
        ) : null}
      </Card>

      {byName && !c.invite_pending ? (
        <Card title="Add their phone" tight>
          <p className="mb-3 text-[12.5px] font-medium leading-normal text-sub">
            Their mobile number or UPI ID sends an invite to their Paytm. Until they accept,
            you keep writing their udhaar by name; then every open entry goes to their phone
            for their yes. The number is only used to find them, never kept.
          </p>
          <label className="flex items-center gap-2 rounded-[11px] border-[1.5px] border-line bg-white px-3 py-2.5 focus-within:border-cyan">
            <Search className="size-[18px] text-sub" />
            <input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Mobile number or UPI ID"
              aria-label="Their mobile number or UPI ID"
              className="min-w-0 flex-1 bg-transparent text-[15px] font-bold outline-none placeholder:font-medium placeholder:text-sub"
            />
          </label>
          {shown?.account ? (
            <div className="mt-3 flex flex-col gap-3">
              <div className="flex items-center gap-3 rounded-[12px] bg-tile px-3 py-2.5">
                <Avatar name={shown.account.named ? shown.account.name : c.display_name} />
                <div className="min-w-0">
                  <p className="truncate text-[14.5px] font-extrabold">{shown.account.name}</p>
                  <p className="text-[12px] font-medium text-sub">
                    {shown.account.here ? "Already in your book" : "On Paytm"}
                  </p>
                </div>
              </div>
              <Pill
                onClick={() =>
                  void act(
                    () => api<CustomerDetail>(`${path}/invite`, { query: q.trim() }),
                    `Invite sent. When ${c.display_name} accepts, their entries go to their phone.`,
                  )
                }
                disabled={busy || Boolean(shown.account.here)}
              >
                Send invite
              </Pill>
            </div>
          ) : shown ? (
            <p className="mt-2.5 text-[12.5px] font-semibold text-warn">
              No Paytm account with that number or UPI ID.
            </p>
          ) : null}
        </Card>
      ) : null}

      {byName && c.invite_pending ? (
        <Card title="Invite sent" tight>
          <p className="text-[12.5px] font-medium leading-normal text-sub">
            {c.invited_at ? `Sent ${shortDate(c.invited_at)}. ` : ""}Waiting for {c.display_name}
            &apos;s yes on their phone. You can still write their udhaar by name meanwhile.
          </p>
          <div className="mt-3">
            <Pill
              tone="outline"
              onClick={() =>
                void act(() => api<CustomerDetail>(`${path}/invite/cancel`, {}), "Invite taken back.")
              }
              disabled={busy}
            >
              Take the invite back
            </Pill>
          </div>
        </Card>
      ) : null}

      <Card title="How you know them" tight>
        <div className="flex flex-col gap-3">
          <Field label="Name" value={name} onChange={setName} />
          <Field label="Where they live or work" value={tag} onChange={setTag} placeholder="Room 12, C wing" />
          <Pill
            tone="outline"
            onClick={() =>
              void act(
                () => api<CustomerDetail>(path, { display_name: name.trim(), tag: tag.trim() || null }),
                "Saved. Their entries don't change.",
              )
            }
            disabled={busy || !edited || !name.trim()}
          >
            Save
          </Pill>
        </div>
      </Card>

      <Card title="Entries" tight>
        {c.entries.length ? (
          c.entries.map((e) => (
            <div
              key={e.id}
              className="flex items-start justify-between gap-3 border-b border-hair py-2.5 last:border-b-0"
            >
              <div className="min-w-0">
                <p className="truncate text-[14px] font-extrabold">{e.note ?? "Udhaar"}</p>
                <p className="mt-0.5 text-[12px] font-medium text-sub">{entryLine(e)}</p>
              </div>
              <p
                className={`flex-none text-[14.5px] font-extrabold tabular-nums ${e.status === "settled" ? "text-paid" : e.expired || e.status === "corrected" ? "text-sub line-through" : ""}`}
              >
                {formatPaise(e.amount_paise)}
              </p>
            </div>
          ))
        ) : (
          <p className="py-2 text-[12.5px] font-medium text-sub">No entries yet.</p>
        )}
      </Card>
    </MerchantShell>
  );
}
