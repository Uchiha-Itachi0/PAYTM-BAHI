"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { CustomerShell } from "@/components/shell/Shell";
import { Card } from "@/components/ui/Card";
import { Figure } from "@/components/ui/Figure";
import { Dots, Notice } from "@/components/ui/Notice";
import { Pill } from "@/components/ui/Pill";
import { Avatar } from "@/components/ui/Row";
import { api, ApiError, usePoll } from "@/lib/api/client";
import type { CircleEntry, CircleView } from "@/lib/api/types";
import { formatPaise } from "@/lib/money";
import { usePerson } from "@/lib/person";
import { shortDate } from "@/lib/when";

/**
 * C3 · One circle: who is in it, and its list.
 *
 * Each bill on the list shows the shop, the amount and the date, and who has paid
 * what; never the item. Anyone in the circle can pay an open one. Its owner can
 * take it back off the list. Leaving takes all of his bills off the list at once:
 * they stay his, and from then on only he can pay them.
 */

function Bill({
  e,
  circleId,
  onTakeBack,
}: {
  e: CircleEntry;
  circleId: string;
  onTakeBack: (entryId: string) => void;
}): React.ReactElement {
  const who = e.mine ? "Yours" : e.debtor_name;
  const paidBy = e.payments
    .map((p) => `${p.by_debtor && e.mine ? "you" : p.payer_name} paid ${formatPaise(p.amount_paise)}`)
    .join(" · ");
  return (
    <div className="border-b border-hair py-3 last:border-b-0">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-[14.5px] font-extrabold">{who}</p>
          <p className="mt-0.5 text-[12px] font-medium text-sub">
            {e.shop.name} · {shortDate(e.recorded_at)}
            {e.state === "paid" ? " · paid in full" : e.state === "closed" ? " · no longer open" : ""}
          </p>
          {paidBy ? <p className="mt-0.5 text-[12px] font-semibold text-paid">{paidBy}</p> : null}
        </div>
        <p
          className={`flex-none text-[15px] font-extrabold tabular-nums ${e.state === "paid" ? "text-paid" : e.state === "closed" ? "text-sub line-through" : ""}`}
        >
          {formatPaise(e.state === "open" ? e.left_paise : e.amount_paise)}
        </p>
      </div>
      {e.state === "open" ? (
        <div className="mt-2.5 flex gap-2 [&>*]:flex-1">
          <Pill tone="cyan" href={`/c/circle/${circleId}/pay/${e.entry_id}`}>
            {e.mine ? "Pay" : "Pay for them"}
          </Pill>
          {e.mine ? (
            <Pill tone="outline" onClick={() => onTakeBack(e.entry_id)}>
              Take it back
            </Pill>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

export function CircleScreen({ circleId }: { circleId: string }): React.ReactElement {
  const person = usePerson();
  const router = useRouter();
  const circle = usePoll<CircleView>(
    person ? `/circles/${circleId}?person_id=${person.id}` : null,
  );
  const [leaving, setLeaving] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const c = circle.data;
  const heading = { title: c?.name ?? "Family circle", back: "/c/circle" };

  async function act(path: string): Promise<boolean> {
    if (!person) return false;
    setProblem(null);
    try {
      await api(path, { person_id: person.id });
      return true;
    } catch (e) {
      setProblem(e instanceof ApiError ? e.message : "That didn't go through.");
      return false;
    }
  }

  async function takeBack(entryId: string): Promise<void> {
    await act(`/circles/${circleId}/entries/${entryId}/take-back`);
    circle.refresh();
  }

  async function leave(): Promise<void> {
    if (await act(`/circles/${circleId}/leave`)) router.push("/c/circle");
  }

  if (person === null) {
    return (
      <CustomerShell heading={heading}>
        <Notice>Pick whose phone this is on the home screen first.</Notice>
      </CustomerShell>
    );
  }

  const mineOpen = c?.entries.filter((e) => e.mine && e.state === "open").length ?? 0;

  return (
    <CustomerShell heading={heading}>
      {problem ? <Notice tone="warn">{problem}</Notice> : null}
      {circle.error && !c ? <Notice tone="warn">{circle.error}</Notice> : null}
      {!c ? (
        !circle.error ? (
          <Card>
            <Dots />
          </Card>
        ) : null
      ) : (
        <>
          <Card>
            <Figure
              label={c.open_paise ? "Open on the list" : "Nothing open on the list"}
              value={formatPaise(c.open_paise)}
            />
          </Card>

          <Card title="On the list" tight>
            {c.entries.length ? (
              c.entries.map((e) => (
                <Bill key={e.entry_id} e={e} circleId={c.id} onTakeBack={(id) => void takeBack(id)} />
              ))
            ) : (
              <p className="py-2 text-[12.5px] font-medium text-sub">
                Nothing yet. When someone here takes udhaar, it can come here for any of you to
                pay.
              </p>
            )}
          </Card>

          <Card title={`${c.members.length} in this circle`} tight>
            {c.members.map((m) => (
              <div key={m.person_id} className="flex items-center gap-3 py-2">
                <Avatar name={m.name} />
                <p className="text-[14px] font-extrabold">
                  {m.me ? `${m.name} (you)` : m.name}
                </p>
                {m.made_it ? (
                  <span className="ml-auto text-[11.5px] font-semibold text-sub">Made it</span>
                ) : null}
              </div>
            ))}
          </Card>

          {leaving ? (
            <Card tight>
              <p className="text-[14px] font-extrabold">Leave {c.name}?</p>
              <p className="mt-1 text-[12.5px] font-medium leading-normal text-sub">
                {mineOpen
                  ? "Your udhaar comes off the list now. It stays yours to pay, and nobody here can pay it after you leave."
                  : "You won't see this list any more."}
              </p>
              <div className="mt-3 flex gap-2 [&>*]:flex-1">
                <Pill onClick={() => void leave()}>Leave</Pill>
                <Pill tone="outline" onClick={() => setLeaving(false)}>
                  Stay
                </Pill>
              </div>
            </Card>
          ) : (
            <Pill tone="outline" onClick={() => setLeaving(true)}>
              Leave circle
            </Pill>
          )}
        </>
      )}
    </CustomerShell>
  );
}
