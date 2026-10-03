"use client";

import { useEffect, useRef, useState } from "react";

import { Composer } from "@/components/chat/Composer";
import { ThreadView } from "@/components/chat/Thread";
import { MerchantShell } from "@/components/shell/Shell";
import { Dots, Notice } from "@/components/ui/Notice";
import { api, ApiError, usePoll } from "@/lib/api/client";
import type { Replies, Thread } from "@/lib/api/types";
import { SHOP_ID } from "@/lib/config";
import { clockTime } from "@/lib/when";

/**
 * C3 · One customer's thread, as the shopkeeper sees it. Live.
 *
 * When the customer wrote last, the munshi suggests two replies in their
 * language; they are only offered, and go only if he taps one. A disputed card
 * carries "Correct the amount", which records the right amount as a new entry
 * for the customer's own yes.
 */
export function ShopThreadScreen({ customerId }: { customerId: string }): React.ReactElement {
  const path = `/shops/${SHOP_ID}/customers/${customerId}`;
  const thread = usePoll<Thread>(`${path}/thread`);
  const t = thread.data;
  const [problem, setProblem] = useState<string | null>(null);
  const [replies, setReplies] = useState<{ after: string; list: string[] } | null>(null);
  const asked = useRef<string | null>(null);

  const last = t?.messages.at(-1);
  const theirs = last?.author === "customer" ? last.id : null;

  // He has seen it: mark read whenever something new of theirs is on screen.
  useEffect(() => {
    if (theirs) void api(`${path}/thread/read`, {}).catch(() => undefined);
  }, [theirs, path]);

  // Ask the munshi once per message of theirs.
  useEffect(() => {
    if (!theirs || asked.current === theirs) return;
    asked.current = theirs;
    api<Replies>(`${path}/thread/suggest`, {})
      .then((r) => setReplies({ after: theirs, list: r.replies }))
      .catch(() => setReplies(null));
  }, [theirs, path]);

  async function send(text: string): Promise<void> {
    setProblem(null);
    try {
      await api<Thread>(`${path}/thread`, { text });
      setReplies(null);
      thread.refresh();
    } catch (e) {
      setProblem(e instanceof ApiError ? e.message : "Couldn't send that.");
    }
  }

  async function correct(entryId: string, paise: number): Promise<void> {
    setProblem(null);
    try {
      await api(`/shops/${SHOP_ID}/entries/${entryId}/correct`, { amount_paise: paise });
      thread.refresh();
    } catch (e) {
      setProblem(e instanceof ApiError ? e.message : "Couldn't send the correction.");
    }
  }

  const sub = t
    ? [t.tag, t.day !== null && t.balance_paise > 0 ? `day ${t.day}` : null]
        .filter(Boolean)
        .join(" · ")
    : undefined;
  const offered = replies && replies.after === theirs ? replies.list : [];

  return (
    <MerchantShell heading={{ title: t?.display_name ?? "…", sub, back: "/m/messages" }}>
      {t?.reminder_at ? (
        <Notice tone="warn">
          A reminder goes to {t.display_name} tomorrow at {clockTime(t.reminder_at)}. You can
          stop it on Tomorrow.
        </Notice>
      ) : null}
      {t ? (
        <ThreadView
          messages={t.messages}
          today={t.today}
          side="shop"
          name={t.display_name}
          shop={t.shop.name}
          actions={{ onCorrect: (e, paise) => void correct(e.id, paise) }}
        />
      ) : thread.error ? (
        <Notice tone="warn">Cannot reach this thread: {thread.error}</Notice>
      ) : (
        <div className="py-10">
          <Dots />
        </div>
      )}

      {offered.length ? (
        <div className="flex flex-wrap justify-end gap-2">
          <p className="w-full text-right text-[11px] font-bold text-sub">
            The munshi suggests · tap to send
          </p>
          {offered.map((r) => (
            <button
              key={r}
              type="button"
              onClick={() => void send(r)}
              className="rounded-pill border-2 border-dashed border-line bg-card px-4 py-2 text-[14px] font-bold"
            >
              {r}
            </button>
          ))}
        </div>
      ) : null}

      {problem ? <Notice tone="warn">{problem}</Notice> : null}

      {t ? (
        <Composer
          placeholder={`Message ${t.display_name}…`}
          disabled={t.joined !== "linked"}
          why={
            t.joined === "name_only"
              ? `${t.display_name} is kept by name only. Nothing you write reaches them.`
              : `${t.display_name} hasn't accepted your invite yet.`
          }
          onSend={send}
        />
      ) : null}
    </MerchantShell>
  );
}
