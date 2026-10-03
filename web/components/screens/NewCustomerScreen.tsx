"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { Search } from "@/components/icons";
import { MerchantShell } from "@/components/shell/Shell";
import { Card } from "@/components/ui/Card";
import { Field } from "@/components/ui/Field";
import { Notice } from "@/components/ui/Notice";
import { Pill } from "@/components/ui/Pill";
import { Avatar } from "@/components/ui/Row";
import { api, ApiError } from "@/lib/api/client";
import type { Account, Customer } from "@/lib/api/types";
import { NAME_CHARS, SHOP_ID, TAG_CHARS } from "@/lib/config";

/**
 * A4 · Add a customer: for someone who can't scan.
 *
 * A mobile number or UPI ID finds their Paytm account (the number is only used
 * to look, never kept), and an invite goes to their phone; nothing is recorded
 * until they accept. No phone at all: kept by name only, like the notebook.
 * The munshi can do either by voice.
 */

/** Looks like a mobile number or a UPI ID: worth asking Paytm. */
function lookable(q: string): boolean {
  return q.includes("@") ? /^[^@\s]+@[^@\s]+$/.test(q.trim()) : q.replace(/\D/g, "").length >= 10;
}

const HERE: Record<string, string> = {
  linked: "Already in your book",
  invited: "Invited · waiting for their yes",
  name_only: "In your book by name",
};

export function NewCustomerScreen(): React.ReactElement {
  const [q, setQ] = useState("");
  const [found, setFound] = useState<{ q: string; account: Account | null } | null>(null);
  const [tag, setTag] = useState("");
  const [nameOnly, setNameOnly] = useState(false);
  const [name, setName] = useState("");
  const [book, setBook] = useState<Customer[]>([]);
  const [busy, setBusy] = useState(false);
  const [news, setNews] = useState<{ tone: "ok" | "warn"; text: string } | null>(null);

  useEffect(() => {
    void api<Customer[]>(`/shops/${SHOP_ID}/customers`).then(setBook);
  }, []);

  // Look the number up once it is a whole number, a moment after typing stops.
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

  const shown = found && found.q === q.trim() ? found : null;
  const same = name.trim()
    ? book.filter((c) => c.display_name.toLowerCase() === name.trim().toLowerCase())
    : [];

  async function invite(a: Account): Promise<void> {
    setBusy(true);
    try {
      await api(`/shops/${SHOP_ID}/customers/invite`, {
        query: q.trim(),
        tag: tag.trim() || null,
        display_name: a.named ? null : name.trim(),
      });
      setNews({
        tone: "ok",
        text: `Invite sent to ${a.named ? a.name : name.trim()}. They accept it on their phone; nothing is recorded until they do.`,
      });
      setFound({ q: q.trim(), account: { ...a, here: "invited" } });
    } catch (e) {
      setNews({ tone: "warn", text: e instanceof ApiError ? e.message : "Couldn't send the invite." });
    } finally {
      setBusy(false);
    }
  }

  async function addByName(): Promise<void> {
    setBusy(true);
    try {
      const c = await api<Customer>(`/shops/${SHOP_ID}/customers`, {
        display_name: name.trim(),
        tag: tag.trim() || null,
      });
      setNews({
        tone: "ok",
        text: `${c.display_name} is in your book, by name only. Their book works; nothing is sent to them.`,
      });
      setBook((b) => [...b, c]);
      setName("");
      setTag("");
    } catch (e) {
      setNews({ tone: "warn", text: e instanceof ApiError ? e.message : "Couldn't add them." });
    } finally {
      setBusy(false);
    }
  }

  return (
    <MerchantShell heading={{ title: "Add a customer", sub: "For someone who can't scan", back: "/m" }}>
      {news ? <Notice tone={news.tone}>{news.text}</Notice> : null}

      {!nameOnly ? (
        <>
          <Card tight>
            <p className="text-[12.5px] font-semibold text-sub">Mobile number or UPI ID</p>
            <label className="mt-2 flex items-center gap-2 rounded-[11px] border-[1.5px] border-line bg-white px-3 py-2.5 focus-within:border-cyan">
              <Search className="size-[18px] text-sub" />
              <input
                value={q}
                onChange={(e) => {
                  setQ(e.target.value);
                  setNews(null);
                }}
                placeholder="98765 43210"
                inputMode="text"
                aria-label="Mobile number or UPI ID"
                autoFocus
                className="min-w-0 flex-1 bg-transparent text-[15px] font-bold outline-none placeholder:font-medium placeholder:text-sub"
              />
            </label>
            <p className="mt-2 text-[11.5px] font-medium leading-normal text-sub">
              Only used to find their Paytm account. BAHI never keeps a number.
            </p>
          </Card>

          {shown?.account ? (
            <Card tight>
              <div className="flex items-center gap-3">
                <Avatar name={shown.account.name} size="lg" />
                <div className="min-w-0">
                  <p className="truncate text-[17px] font-extrabold tracking-[-0.02em]">
                    {shown.account.name}
                  </p>
                  <p className="text-[12.5px] font-medium text-sub">
                    {shown.account.here ? HERE[shown.account.here] : "On Paytm"}
                  </p>
                </div>
              </div>
              {!shown.account.here ? (
                <div className="mt-3.5 flex flex-col gap-3">
                  {!shown.account.named ? (
                    <Field
                      label="What you call them"
                      value={name}
                      onChange={setName}
                maxLength={NAME_CHARS}
                      placeholder="Shreya"
                    />
                  ) : null}
                  <Field
                    label="Where they live or work (optional)"
                    value={tag}
                    onChange={setTag}
                maxLength={TAG_CHARS}
                    placeholder="Room 12, C wing"
                  />
                  <Pill
                    onClick={() => void invite(shown.account!)}
                    disabled={busy || (!shown.account.named && !name.trim())}
                  >
                    Send invite
                  </Pill>
                  <p className="text-center text-[12px] font-medium leading-normal text-sub">
                    They accept it on their phone. Nothing is recorded until they do.
                  </p>
                </div>
              ) : null}
            </Card>
          ) : shown ? (
            <Notice tone="warn">
              No Paytm account with that number or UPI ID. You can keep them by name only.
            </Notice>
          ) : null}

          <button
            type="button"
            onClick={() => setNameOnly(true)}
            className="py-2 text-center text-[14px] font-extrabold text-cyan-text"
          >
            No phone? Add by name only
          </button>
        </>
      ) : (
        <>
          <Card title="Keep them by name" tight>
            <div className="flex flex-col gap-3">
              <Field label="Name" value={name} onChange={setName}
                maxLength={NAME_CHARS} placeholder="Ganpat" autoFocus />
              <Field
                label="Where they live or work"
                value={tag}
                onChange={setTag}
                maxLength={TAG_CHARS}
                placeholder="Chawl 7"
              />
              {same.length ? (
                <Notice tone="warn">
                  Already in your book: {same.map((c) => [c.display_name, c.tag].filter(Boolean).join(", ")).join(" · ")}.
                  Add a description so you can tell them apart.
                </Notice>
              ) : null}
              <Pill onClick={() => void addByName()} disabled={busy || !name.trim()}>
                Add to your book
              </Pill>
              <p className="text-center text-[12px] font-medium leading-normal text-sub">
                Their book works like the notebook. With no phone, nothing is sent to them.
              </p>
            </div>
          </Card>
          <button
            type="button"
            onClick={() => setNameOnly(false)}
            className="py-2 text-center text-[14px] font-extrabold text-cyan-text"
          >
            They have a phone? Invite them
          </button>
        </>
      )}

      <Notice>
        Or tell the munshi: <Link href="/m/add?listen=1" className="font-extrabold text-cyan-text">“नया ग्राहक जोड़ो, गणपत, चॉल सात”</Link>.
        It shows a card, and adds them on your yes.
      </Notice>
    </MerchantShell>
  );
}
