"use client";

import { useState } from "react";

import { AddToCircle, CirclePicker, addToCircle } from "@/components/customer/AddToCircle";
import { Card } from "@/components/ui/Card";
import { Notice } from "@/components/ui/Notice";
import { Pill } from "@/components/ui/Pill";
import { api, ApiError } from "@/lib/api/client";
import type { CircleNotice, MyCircles } from "@/lib/api/types";

/**
 * BAHI's notes about his family circles, on his own phone: the in-app
 * notification. Each says what happened and offers what he can do next. The
 * shop never sees any of them.
 *
 *   choose  his new udhaar, and which circle it should go to (the picker)
 *   kept    his new udhaar stayed with him: pay it, or add it to a circle
 *   shared  his new udhaar is on the circle's list; he can take it back
 *   help    someone's bill is on the list; he can pay it for them
 *   added   someone put him in a circle
 *   paid    someone paid part or all of his udhaar
 */

function Choices({
  n,
  mine,
  personId,
  refresh,
  report,
}: {
  n: CircleNotice;
  mine: MyCircles;
  personId: string;
  refresh: () => void;
  report: (problem: string | null) => void;
}): React.ReactElement {
  const [picking, setPicking] = useState(false);

  async function done(): Promise<void> {
    await api(`/circle-notices/${n.id}/done`, { person_id: personId });
    refresh();
  }

  async function takeBack(): Promise<void> {
    try {
      await api(`/circles/${n.circle_id}/entries/${n.entry_id}/take-back`, {
        person_id: personId,
      });
      report(null);
    } catch (e) {
      report(e instanceof ApiError ? e.message : "That didn't go through.");
    }
    refresh();
  }

  async function shared(problem: string | null): Promise<void> {
    report(problem);
    refresh();
  }

  const row = "mt-3 flex gap-2 [&>*]:flex-1";
  if (n.kind === "choose" && n.entry_id) {
    const entry = n.entry_id;
    return (
      <div className={row}>
        <Pill onClick={() => setPicking(true)}>Add to circle</Pill>
        <Pill tone="outline" onClick={() => void done()}>
          Keep it to myself
        </Pill>
        {picking ? (
          <CirclePicker
            circles={mine.circles}
            onPick={(id) => {
              setPicking(false);
              void addToCircle(id, entry, personId).then(shared);
            }}
            onClose={() => setPicking(false)}
          />
        ) : null}
      </div>
    );
  }
  if (n.kind === "kept" && n.entry_id) {
    return (
      <div className={row}>
        {n.shop_id ? (
          <Pill tone="cyan" href={`/c/pay/${n.shop_id}?from=udhaar`}>
            Pay it myself
          </Pill>
        ) : null}
        <AddToCircle
          entryId={n.entry_id}
          personId={personId}
          circles={mine.circles}
          onDone={(p) => void shared(p)}
        />
      </div>
    );
  }
  if (n.kind === "shared" && n.circle_id) {
    return (
      <div className={row}>
        <Pill onClick={() => void done()}>OK</Pill>
        <Pill tone="outline" onClick={() => void takeBack()}>
          Take it back
        </Pill>
      </div>
    );
  }
  if (n.kind === "help" && n.circle_id && n.entry_id) {
    return (
      <div className={row}>
        <Pill tone="cyan" href={`/c/circle/${n.circle_id}/pay/${n.entry_id}`}>
          Pay for them
        </Pill>
        <Pill tone="outline" onClick={() => void done()}>
          Not now
        </Pill>
      </div>
    );
  }
  return (
    <div className={row}>
      {n.kind === "added" && n.circle_id ? (
        <Pill href={`/c/circle/${n.circle_id}`}>See the circle</Pill>
      ) : null}
      <Pill tone="outline" onClick={() => void done()}>
        OK
      </Pill>
    </div>
  );
}

export function CircleNotices({
  mine,
  personId,
  refresh,
}: {
  mine: MyCircles;
  personId: string;
  refresh: () => void;
}): React.ReactElement | null {
  const [problem, setProblem] = useState<string | null>(null);
  if (!mine.notices.length && !problem) return null;
  return (
    <>
      {problem ? <Notice tone="warn">{problem}</Notice> : null}
      {mine.notices.map((n) => (
        <Card key={n.id} tight>
          <p className="text-[11.5px] font-extrabold uppercase tracking-[0.08em] text-sub">
            Family circle
          </p>
          <p className="mt-1 text-[14px] font-bold leading-normal">{n.body}</p>
          <Choices
            n={n}
            mine={mine}
            personId={personId}
            refresh={refresh}
            report={setProblem}
          />
        </Card>
      ))}
    </>
  );
}
