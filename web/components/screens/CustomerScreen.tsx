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
import { api, apiDelete, ApiError } from "@/lib/api/client";
import type {
  Account,
  CustomerDetail,
  Pattern,
  Remembered,
  ThreadEntry,
} from "@/lib/api/types";
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
 *
 * What BAHI remembers about them is here too (M3): the shopkeeper's notes, their
 * promises in chat, the nickname he uses. Only the shop sees it. A day on it
 * holds tomorrow's reminder until then; Forget takes it back at once.
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

const SAID: Record<Remembered["kind"], string> = {
  note: "Your note",
  promise: "They promised in chat",
  nickname: "You call them",
  said: "From their chat",
};

const NOW: Record<Pattern["now"], { text: string; tone: string } | null> = {
  early: { text: "Not due yet", tone: "bg-ok-bg text-ok" },
  due: { text: "Due about now", tone: "bg-warn-bg text-warn" },
  late: { text: "Later than usual", tone: "bg-warn-bg text-warn" },
  unknown: null,
  clear: { text: "Nothing owed", tone: "bg-ok-bg text-ok" },
};

function clock12(hhmm: string): string {
  const [h, m] = hhmm.split(":").map(Number);
  return `${h % 12 || 12}${m ? `:${String(m).padStart(2, "0")}` : ""} ${h < 12 ? "am" : "pm"}`;
}

/** How they pay, from their own book: the figures are the book's arithmetic. */
function HowTheyPay({ p }: { p: Pattern }): React.ReactElement | null {
  if (!p.payments && !p.entries) return null;
  const now = NOW[p.now];
  const rows: [string, string][] = [];
  if (p.usual_gap !== null && p.usual_gap !== undefined)
    rows.push([
      "Usually pays",
      `every ${p.usual_gap} days · 8 in 10 times within ${p.usually_within}`,
    ]);
  if (p.last_paid) rows.push(["Last paid", shortDate(p.last_paid)]);
  if (p.expect_from && p.expect_by) {
    const window = `${shortDate(p.expect_from)} to ${shortDate(p.expect_by)}`;
    // A window that has passed is not a guess for the future.
    rows.push(p.now === "late" ? ["Usual window", `${window}, passed`] : ["Likely next", window]);
  }
  if (p.promised) rows.push(["Promised by", shortDate(p.promised)]);
  if (p.usual_time) rows.push(["Usually at", clock12(p.usual_time)]);
  if (p.recent_gaps.length) rows.push(["Latest gaps", `${p.recent_gaps.join(", ")} days`]);
  if (p.promises_due) rows.push(["Promises kept", `${p.promises_kept} of ${p.promises_due}`]);
  if (p.entries) rows.push(["Said wrong", `${p.disputed} of ${p.entries} entries`]);
  return (
    <Card title="How they pay" tight>
      {now ? (
        <span
          className={`mb-2 inline-block rounded-full px-2.5 py-1 text-[11.5px] font-extrabold ${now.tone}`}
        >
          {now.text}
        </span>
      ) : null}
      {rows.length ? (
        rows.map(([k, v]) => (
          <div
            key={k}
            className="flex items-baseline justify-between gap-3 border-b border-hair py-2 last:border-b-0"
          >
            <p className="text-[12.5px] font-semibold text-sub">{k}</p>
            <p className="text-right text-[13.5px] font-extrabold tabular-nums">{v}</p>
          </div>
        ))
      ) : (
        <p className="py-1 text-[12.5px] font-medium text-sub">No payments yet.</p>
      )}
      {p.payments > 0 && p.payments < 4 ? (
        <p className="mt-2 text-[11.5px] font-medium text-sub">
          Only {p.payments} {p.payments === 1 ? "payment" : "payments"} so far: too few to read
          a rhythm.
        </p>
      ) : null}
    </Card>
  );
}

function Memories({
  c,
  busy,
  onForget,
  onNote,
}: {
  c: CustomerDetail;
  busy: boolean;
  onForget: (m: Remembered) => void;
  onNote: (body: string, until: string | null) => Promise<boolean>;
}): React.ReactElement {
  const [body, setBody] = useState("");
  const [until, setUntil] = useState("");
  const memories = c.memories ?? [];
  return (
    <Card title="BAHI remembers" tight>
      <p className="mb-2 text-[12px] font-medium leading-normal text-sub">
        Only you see these. A day on one holds tomorrow&apos;s reminder until then.
      </p>
      {memories.length ? (
        memories.map((m) => (
          <div
            key={m.id}
            className="flex items-start justify-between gap-3 border-b border-hair py-2.5 last:border-b-0"
          >
            <div className="min-w-0">
              <p className="text-[11.5px] font-bold uppercase tracking-[0.04em] text-sub">
                {SAID[m.kind]}
              </p>
              <p className="mt-0.5 text-[14px] font-bold leading-snug">
                {m.kind === "nickname" ? m.body : `“${m.body}”`}
              </p>
              <p className="mt-0.5 text-[12px] font-medium text-sub">
                {shortDate(m.remembered_at)}
                {m.until ? ` · quiet until ${shortDate(m.until)}` : ""}
              </p>
            </div>
            <button
              type="button"
              onClick={() => onForget(m)}
              disabled={busy}
              className="flex-none pt-4 text-[12.5px] font-extrabold text-cyan-text disabled:opacity-40"
            >
              Forget
            </button>
          </div>
        ))
      ) : (
        <p className="py-1.5 text-[12.5px] font-medium text-sub">
          Nothing yet. Tell the munshi, or write it here.
        </p>
      )}
      <div className="mt-3 flex flex-col gap-3">
        <Field
          label="A note about them"
          value={body}
          onChange={setBody}
          placeholder="Salary comes on the 10th"
        />
        <label className="block">
          <span className="text-[12.5px] font-semibold text-sub">
            Stay quiet about their udhaar until (optional)
          </span>
          <input
            type="date"
            value={until}
            onChange={(e) => setUntil(e.target.value)}
            className="mt-2 block w-full rounded-[11px] border-[1.5px] border-line bg-white px-3 py-2.5 text-[15px] font-bold outline-none focus:border-cyan"
          />
        </label>
        <Pill
          tone="outline"
          onClick={() =>
            void onNote(body.trim(), until || null).then((ok) => {
              if (ok) {
                setBody("");
                setUntil("");
              }
            })
          }
          disabled={busy || !body.trim()}
        >
          Remember it
        </Pill>
      </div>
    </Card>
  );
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

  async function act(run: () => Promise<CustomerDetail>, done: string): Promise<boolean> {
    setBusy(true);
    setNews(null);
    try {
      take(await run());
      setNews({ tone: "ok", text: done });
      return true;
    } catch (e) {
      setNews({ tone: "warn", text: e instanceof ApiError ? e.message : "That didn't go through." });
      return false;
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
            {c.paytm ? (
              <p className="mt-0.5 truncate text-[12px] font-medium text-sub">
                Paytm: {c.paytm.name} · {c.paytm.upi}
              </p>
            ) : null}
          </div>
        </div>
        <div className="mt-4">
          <Figure
            label="Owes you · agreed"
            value={formatPaise(c.balance_paise)}
            fine={c.balance_paise && c.day !== null ? `day ${c.day}` : undefined}
          />
          {(c.waiting_paise ?? 0) > 0 || (c.disputed_paise ?? 0) > 0 ? (
            <p className="mt-1 text-[12px] font-semibold text-sub">
              Not counted:{" "}
              {[
                (c.waiting_paise ?? 0) > 0
                  ? `${formatPaise(c.waiting_paise ?? 0)} waiting for their yes`
                  : null,
                (c.disputed_paise ?? 0) > 0
                  ? `${formatPaise(c.disputed_paise ?? 0)} they say is wrong`
                  : null,
              ]
                .filter(Boolean)
                .join(" · ")}
            </p>
          ) : null}
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

      {c.pattern ? <HowTheyPay p={c.pattern} /> : null}

      <Memories
        c={c}
        busy={busy}
        onForget={(m) =>
          void act(async () => {
            await apiDelete(`/shops/${SHOP_ID}/memories/${m.id}`);
            return api<CustomerDetail>(path);
          }, "Forgotten.")
        }
        onNote={(body, until) =>
          act(
            () => api<CustomerDetail>(`${path}/memories`, { body, until }),
            until
              ? `Remembered. No reminder goes to ${c.display_name} until after ${shortDate(until)}.`
              : "Remembered.",
          )
        }
      />

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
