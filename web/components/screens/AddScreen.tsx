"use client";

import { useEffect, useMemo, useState } from "react";

import { MerchantShell } from "@/components/shell/Shell";
import { Card } from "@/components/ui/Card";
import { Field } from "@/components/ui/Field";
import { Figure } from "@/components/ui/Figure";
import { Keypad, press } from "@/components/ui/Keypad";
import { Notice } from "@/components/ui/Notice";
import { Pill } from "@/components/ui/Pill";
import { Row } from "@/components/ui/Row";
import { api, ApiError, usePoll } from "@/lib/api/client";
import type { Counter, Customer, Entry } from "@/lib/api/types";
import { SHOP_ID } from "@/lib/config";
import { formatPaise } from "@/lib/money";

/**
 * A2 · Who is at the counter, then how much.
 *
 * Everyone who scanned the udhaar QR in the last three minutes is listed. With
 * one person there, he is the one: that is not a guess. With several, nobody is
 * picked until the shopkeeper taps a name (or says it, once voice lands). The
 * screen never chooses by queue order.
 *
 * Someone who is not at the counter can be picked from the book instead.
 */

type Pick =
  | { kind: "scan"; scanId: string; name: string }
  | { kind: "customer"; customerId: string; name: string };

function ago(seconds: number): string {
  return seconds < 60 ? `${seconds}s ago` : `${Math.floor(seconds / 60)}m ago`;
}

export function AddScreen(): React.ReactElement {
  const counter = usePoll<Counter>(`/shops/${SHOP_ID}/counter`, 1500);
  const waiting = useMemo(() => counter.data?.waiting ?? [], [counter.data]);

  const [chosen, setPicked] = useState<Pick | null>(null);
  const [rupees, setRupees] = useState("");
  const [busy, setBusy] = useState(false);
  const [news, setNews] = useState<{ tone: "ok" | "warn"; text: string } | null>(null);

  // A picked scan that has expired or walked away is no longer a choice.
  const picked =
    chosen?.kind === "scan" && !waiting.some((w) => w.scan_id === chosen.scanId)
      ? null
      : chosen;

  const only = waiting.length === 1 ? waiting[0] : null;
  const who: Pick | null =
    picked ?? (only ? { kind: "scan", scanId: only.scan_id, name: only.display_name } : null);

  const [book, setBook] = useState<Customer[]>([]);
  const [search, setSearch] = useState("");
  useEffect(() => {
    void api<Customer[]>(`/shops/${SHOP_ID}/customers`).then(setBook);
  }, []);
  const matches = search.trim()
    ? book
        .filter((c) => c.joined !== "invited")
        .filter((c) => c.display_name.toLowerCase().includes(search.trim().toLowerCase()))
        .slice(0, 5)
    : [];

  const paise = Number(rupees || "0") * 100;

  async function send(): Promise<void> {
    if (!who || paise <= 0) return;
    setBusy(true);
    try {
      await api<Entry>(`/shops/${SHOP_ID}/entries`, {
        amount_paise: paise,
        ...(who.kind === "scan" ? { scan_id: who.scanId } : { customer_id: who.customerId }),
      });
      setNews({
        tone: "ok",
        text: `Sent to ${who.name}. Their phone now asks them to confirm ${formatPaise(paise)}.`,
      });
      setRupees("");
      setPicked(null);
      setSearch("");
      counter.refresh();
    } catch (e) {
      setNews({ tone: "warn", text: e instanceof ApiError ? e.message : "Could not send." });
    } finally {
      setBusy(false);
    }
  }

  const heading =
    waiting.length === 0
      ? "Nobody at the counter"
      : waiting.length === 1
        ? "1 person at the counter"
        : `${waiting.length} people at the counter`;

  return (
    <MerchantShell heading={{ title: "Add udhaar", sub: heading, back: "/m" }}>
      {news ? <Notice tone={news.tone}>{news.text}</Notice> : null}

      <Card title="At the counter" tight>
        {waiting.length ? (
          waiting.map((w) => (
            <Row
              key={w.scan_id}
              name={w.display_name}
              sub={`${w.first_time ? "New here" : (w.tag ?? "Regular")} · scanned ${ago(w.waited_s)}`}
              selected={who?.kind === "scan" && who.scanId === w.scan_id}
              onSelect={() =>
                setPicked({ kind: "scan", scanId: w.scan_id, name: w.display_name })
              }
            />
          ))
        ) : (
          <p className="text-[12.5px] font-medium leading-normal text-sub">
            When a customer scans your udhaar QR, they appear here for three minutes.
          </p>
        )}
        {waiting.length > 1 && !who ? (
          <p className="mt-2 text-[12px] font-semibold text-cyan-text">
            Tap who is in front of you.
          </p>
        ) : null}
      </Card>

      <Card tight>
        <Figure
          label={who ? `For ${who.name}` : "Pick who it is for"}
          value={formatPaise(paise)}
          fine="Type the amount. Voice comes next."
        />
        <div className="mt-3">
          <Keypad onKey={(k) => setRupees((r) => press(r, k))} />
        </div>
      </Card>

      <Pill onClick={() => void send()} disabled={!who || paise <= 0 || busy}>
        {who ? `Send to ${who.name}` : "Send"}
      </Pill>

      <Card title="Not at the counter?" tight>
        <Field
          label="Find someone in your book"
          value={search}
          onChange={setSearch}
          placeholder="Name"
          inputMode="search"
        />
        {matches.length ? (
          <div className="mt-2">
            {matches.map((c) => (
              <Row
                key={c.id}
                name={c.display_name}
                sub={c.joined === "name_only" ? `${c.tag ?? ""} · name only` : (c.tag ?? "")}
                selected={who?.kind === "customer" && who.customerId === c.id}
                onSelect={() =>
                  setPicked({ kind: "customer", customerId: c.id, name: c.display_name })
                }
              />
            ))}
          </div>
        ) : null}
      </Card>
    </MerchantShell>
  );
}
