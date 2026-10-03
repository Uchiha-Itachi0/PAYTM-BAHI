"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import { Composer } from "@/components/chat/Composer";
import { type DisputedAs, ThreadView } from "@/components/chat/Thread";
import { CustomerShell } from "@/components/shell/Shell";
import { Dots, Notice } from "@/components/ui/Notice";
import { api, ApiError, usePoll } from "@/lib/api/client";
import type { Entry, Thread, ThreadEntry } from "@/lib/api/types";
import { usePerson } from "@/lib/person";
import { tone, unlock } from "@/lib/soundbox";

/**
 * C2 · His thread with one shop, in the Paytm app. Live.
 *
 * An entry waiting for him carries its two answers: "Yes, I owe ₹200" (the
 * button's words come from the server, because they are what is stored) and
 * "Not mine" or "Wrong amount", with his reason if he gives one. A correction from the
 * shop is a new card, and needs its own yes. Pay, beside the message box, opens
 * the payment screen with what he owes here filled in.
 */
export function CustomerThreadScreen({ shopId }: { shopId: string }): React.ReactElement {
  const person = usePerson();
  const path = person ? `/people/${person.id}/shops/${shopId}/thread` : null;
  const thread = usePoll<Thread>(path);
  const t = thread.data;
  const [problem, setProblem] = useState<string | null>(null);
  const count = useRef<number | null>(null);

  const last = t?.messages.at(-1);
  const theirs = last && last.author !== "customer" ? last.id : null;

  useEffect(() => {
    const first = (): void => unlock();
    window.addEventListener("pointerdown", first, { once: true });
    return () => window.removeEventListener("pointerdown", first);
  }, []);

  // Something new from the shop: a soft tone, and it is read.
  useEffect(() => {
    if (!t) return;
    if (count.current !== null && t.messages.length > count.current && theirs) tone("message");
    count.current = t.messages.length;
    if (theirs && path) void api(`${path}/read`, {}).catch(() => undefined);
  }, [t, theirs, path]);

  async function act(run: () => Promise<unknown>, failed: string): Promise<void> {
    setProblem(null);
    try {
      await run();
      thread.refresh();
    } catch (e) {
      setProblem(e instanceof ApiError ? e.message : failed);
    }
  }

  const confirm = (e: ThreadEntry): void =>
    void act(
      () => api<Entry>(`/entries/${e.id}/confirm`, { person_id: person?.id }),
      "Couldn't send your yes.",
    );
  const dispute = (e: ThreadEntry, reason: string, as: DisputedAs): void =>
    void act(
      () =>
        api<Entry>(`/entries/${e.id}/dispute`, {
          person_id: person?.id,
          reason: reason || null,
          disputed_as: as,
        }),
      "Couldn't tell the shop.",
    );

  const heading = {
    title: t?.shop.name ?? "…",
    sub: t ? `${t.shop.locality} · Business` : undefined,
    back: "/c/udhaar",
  };

  if (person === null) {
    return (
      <CustomerShell heading={heading}>
        <Notice>Pick whose phone this is on the home screen first.</Notice>
      </CustomerShell>
    );
  }

  return (
    <CustomerShell heading={heading}>
      {t ? (
        <ThreadView
          messages={t.messages}
          today={t.today}
          side="customer"
          name={t.display_name}
          shop={t.shop.name}
          actions={{ onConfirm: confirm, onDispute: dispute }}
        />
      ) : thread.error ? (
        <Notice tone="warn">Cannot reach this chat: {thread.error}</Notice>
      ) : (
        <div className="py-10">
          <Dots />
        </div>
      )}
      {problem ? <Notice tone="warn">{problem}</Notice> : null}
      {t && person ? (
        <Composer
          placeholder={`Message ${t.shop.name}…`}
          before={
            t.balance_paise > 0 ? (
              <Link
                href={`/c/pay/${shopId}`}
                className="flex-none rounded-pill bg-cyan px-4 py-2 text-[13.5px] font-extrabold text-white"
              >
                Pay
              </Link>
            ) : null
          }
          onSend={(text) =>
            act(
              () => api<Thread>(`/shops/${shopId}/thread`, { person_id: person.id, text }),
              "Couldn't send that.",
            )
          }
        />
      ) : null}
    </CustomerShell>
  );
}
