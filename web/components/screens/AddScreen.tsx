"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { MerchantShell } from "@/components/shell/Shell";
import { Card } from "@/components/ui/Card";
import { Field } from "@/components/ui/Field";
import { Figure } from "@/components/ui/Figure";
import { Keypad, press } from "@/components/ui/Keypad";
import { Notice } from "@/components/ui/Notice";
import { Pill } from "@/components/ui/Pill";
import { Row } from "@/components/ui/Row";
import { Countdown } from "@/components/voice/Countdown";
import { HeardCard } from "@/components/voice/HeardCard";
import { VoicePanel } from "@/components/voice/VoicePanel";
import { api, ApiError, usePoll } from "@/lib/api/client";
import type { Counter, Customer, Entry, Heard, HeardPerson } from "@/lib/api/types";
import { SHOP_ID } from "@/lib/config";
import { formatPaise } from "@/lib/money";
import { askWho, PROBLEM_LINE, sayAmount } from "@/lib/voice";

/**
 * A2 · Who is at the counter, then how much.
 *
 * Everyone who scanned the udhaar QR in the last three minutes is listed. With
 * one person there, he is the one: that is not a guess. With several, nobody is
 * picked until the shopkeeper says a name or taps one. The screen never chooses
 * by queue order.
 *
 * Spoken: Sarvam-105B reads the words and our code checks the reading: the
 * amount must be in the words, and the words that name the person must fit
 * exactly one customer, or the screen asks "Kaunse Anubhav?". A pick is read
 * back and sent after three seconds unless he cancels. When our parser read it
 * instead (offline, or Sarvam didn't answer), nothing goes by itself: the amount
 * and the person are filled in and he taps Send, because that reader was wrong
 * five times as often in the test. Typed: the keypad and Send, as before. All of
 * it ends in the same POST /entries.
 */

type Pick =
  | { kind: "scan"; scanId: string; name: string }
  | { kind: "customer"; customerId: string; name: string };

/** A spoken amount waiting to go, or waiting to be told who it is for. */
type Spoken = { paise: number; transcript: string; readback: string | null };

function ago(seconds: number): string {
  return seconds < 60 ? `${seconds}s ago` : `${Math.floor(seconds / 60)}m ago`;
}

function pickOf(p: HeardPerson): Pick {
  return p.scan_id
    ? { kind: "scan", scanId: p.scan_id, name: p.display_name }
    : { kind: "customer", customerId: p.customer_id, name: p.display_name };
}

export function AddScreen(): React.ReactElement {
  const counter = usePoll<Counter>(`/shops/${SHOP_ID}/counter`, 1500);
  const waiting = useMemo(() => counter.data?.waiting ?? [], [counter.data]);

  const [chosen, setPicked] = useState<Pick | null>(null);
  const [rupees, setRupees] = useState("");
  const [busy, setBusy] = useState(false);
  const [news, setNews] = useState<{ tone: "ok" | "warn"; text: string } | null>(null);

  const [heard, setHeard] = useState<Heard | null>(null);
  /** What our parser heard, kept with the amount it filled in for him to check. */
  const [prefilled, setPrefilled] = useState<Spoken | null>(null);
  const [pending, setPending] = useState<{ who: Pick; spoken: Spoken } | null>(null);
  const [asking, setAsking] = useState<{ spoken: Spoken; heard: Heard } | null>(null);

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

  async function record(to: Pick, amount: number, spokenText?: string): Promise<void> {
    setBusy(true);
    try {
      await api<Entry>(`/shops/${SHOP_ID}/entries`, {
        amount_paise: amount,
        spoken_text: spokenText?.slice(0, 200),
        ...(to.kind === "scan" ? { scan_id: to.scanId } : { customer_id: to.customerId }),
      });
      setNews({
        tone: "ok",
        text:
          to.kind === "scan"
            ? `Sent to ${to.name}. Their phone now asks them to confirm ${formatPaise(amount)}.`
            : `Recorded ${formatPaise(amount)} for ${to.name}.`,
      });
      setRupees("");
      setPicked(null);
      setPrefilled(null);
      setSearch("");
      counter.refresh();
    } catch (e) {
      setNews({ tone: "warn", text: e instanceof ApiError ? e.message : "Could not send." });
    } finally {
      setBusy(false);
    }
  }

  // ── what was said ──

  const onHeard = useCallback((h: Heard) => {
    setHeard(h);
    setNews(null);
    setPending(null);
    setAsking(null);
    setPrefilled(null);
    if (h.amount_paise === null) {
      if (h.who.kind === "picked") setPicked(pickOf(h.who.person));
      const why = h.problem ? PROBLEM_LINE[h.problem] : "No amount in that.";
      setNews({ tone: "warn", text: `${why} Nothing was sent. Say it again, or type it.` });
      return;
    }
    if (h.intent !== "udhaar") {
      const from = h.who.kind === "picked" ? ` from ${h.who.person.display_name}` : "";
      setNews({
        tone: "warn",
        text:
          h.intent === "payment"
            ? `Heard a payment of ${formatPaise(h.amount_paise)}${from}. Recording payments by voice comes next, so nothing was sent.`
            : `Heard ${formatPaise(h.amount_paise)}, but not whether it is udhaar. Nothing was sent. Say it again, or type it.`,
      });
      return;
    }
    const spoken: Spoken = {
      paise: h.amount_paise,
      transcript: h.transcript,
      readback: h.readback?.devanagari ?? null,
    };
    if (h.who.kind === "picked" && h.reader === "rules") {
      const to = pickOf(h.who.person);
      setPicked(to);
      setRupees(String(spoken.paise / 100));
      setPrefilled(spoken);
      if (spoken.readback) sayAmount(spoken.paise, spoken.readback);
      setNews({
        tone: "warn",
        text: `${h.fallback === "no_answer" ? "Sarvam-105B didn't answer" : "Voice is offline"}, so our parser read this. Check ${formatPaise(spoken.paise)} for ${to.name}, then tap Send.`,
      });
    } else if (h.who.kind === "picked") {
      setPending({ who: pickOf(h.who.person), spoken });
      if (spoken.readback) sayAmount(spoken.paise, spoken.readback);
    } else {
      setAsking({ spoken, heard: h });
      askWho();
      if (h.who.why === "not_found" || h.who.why === "not_said") {
        setNews({
          tone: "warn",
          text:
            h.who.why === "not_found"
              ? `“${h.name}” is not in your book. Tap who it is for, or find them below.`
              : "The name Sarvam read isn't in the words. Tap who it is for, or find them below.",
        });
      }
    }
  }, []);

  const onProblem = useCallback((text: string) => setNews({ tone: "warn", text }), []);

  /** A tap on someone: the answer to "kiske liye?", or the pick for the keypad. */
  function choose(p: Pick): void {
    if (asking) {
      setPending({ who: p, spoken: asking.spoken });
      setAsking(null);
      if (asking.spoken.readback) sayAmount(asking.spoken.paise, asking.spoken.readback);
    } else {
      setPicked(p);
    }
  }

  function sendPending(): void {
    if (!pending) return;
    const { who: to, spoken } = pending;
    setPending(null);
    void record(to, spoken.paise, spoken.transcript);
  }

  const heading =
    waiting.length === 0
      ? "Nobody at the counter"
      : waiting.length === 1
        ? "1 person at the counter"
        : `${waiting.length} people at the counter`;

  const askingWho = asking?.heard.who.kind === "ask" ? asking.heard.who : null;

  return (
    <MerchantShell heading={{ title: "Add udhaar", sub: heading, back: "/m" }}>
      {news ? <Notice tone={news.tone}>{news.text}</Notice> : null}

      {pending ? (
        <Countdown
          key={`${pending.spoken.transcript}:${pending.who.name}`}
          name={pending.who.name}
          paise={pending.spoken.paise}
          onDone={sendPending}
          onCancel={() => {
            setPending(null);
            setNews({ tone: "warn", text: "Cancelled. Nothing was sent." });
          }}
        />
      ) : null}

      {askingWho?.why === "several" || askingWho?.why === "maybe" ? (
        <Card
          title={
            askingWho.why === "several" ? `Kaunse ${asking?.heard.name}?` : `${asking?.heard.name}?`
          }
          tight
        >
          <p className="mb-2 text-[12px] font-semibold text-cyan-text">
            {askingWho.why === "several"
              ? `“${asking?.heard.name}” fits ${askingWho.among.length} people. Tap the one in front of you.`
              : "Only a close sound, so nobody was picked. Is it one of these?"}
          </p>
          {askingWho.among.map((p) => (
            <Row
              key={p.customer_id}
              name={p.display_name}
              sub={
                [p.tag, p.scan_id ? "At the counter" : null].filter(Boolean).join(" · ") ||
                "In your book"
              }
              onSelect={() => choose(pickOf(p))}
            />
          ))}
          <p className="mt-2 text-[11.5px] font-medium text-sub">
            Someone else? Find them in your book below.
          </p>
        </Card>
      ) : null}

      <Card title={askingWho?.why === "who" ? "Kiske liye?" : "At the counter"} tight>
        {asking ? (
          <p className="mb-2 text-[12px] font-semibold text-cyan-text">
            Heard {formatPaise(asking.spoken.paise)}. Tap who it is for
            {askingWho?.why === "who" ? "." : ", or find them below."}
          </p>
        ) : null}
        {waiting.length ? (
          waiting.map((w) => (
            <Row
              key={w.scan_id}
              name={w.display_name}
              sub={`${w.first_time ? "New here" : (w.tag ?? "Regular")} · scanned ${ago(w.waited_s)}`}
              selected={!asking && who?.kind === "scan" && who.scanId === w.scan_id}
              onSelect={() => choose({ kind: "scan", scanId: w.scan_id, name: w.display_name })}
            />
          ))
        ) : (
          <p className="text-[12.5px] font-medium leading-normal text-sub">
            When a customer scans your udhaar QR, they appear here for three minutes.
          </p>
        )}
        {waiting.length > 1 && !who && !asking ? (
          <p className="mt-2 text-[12px] font-semibold text-cyan-text">
            Say their name with the amount, or tap who is in front of you.
          </p>
        ) : null}
      </Card>

      <VoicePanel onHeard={onHeard} onProblem={onProblem} />

      {heard ? <HeardCard heard={heard} /> : null}

      <Card title="Or type it" tight>
        <Figure
          label={who ? `For ${who.name}` : "Pick who it is for"}
          value={formatPaise(paise)}
        />
        <div className="mt-3">
          <Keypad onKey={(k) => setRupees((r) => press(r, k))} />
        </div>
      </Card>

      <Pill
        onClick={() =>
          who && void record(who, paise, prefilled?.paise === paise ? prefilled.transcript : undefined)
        }
        disabled={!who || paise <= 0 || busy || pending !== null}
      >
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
                selected={!asking && who?.kind === "customer" && who.customerId === c.id}
                onSelect={() =>
                  choose({ kind: "customer", customerId: c.id, name: c.display_name })
                }
              />
            ))}
          </div>
        ) : null}
      </Card>
    </MerchantShell>
  );
}
