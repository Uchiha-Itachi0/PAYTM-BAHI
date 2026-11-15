"use client";

import { useState } from "react";

import { Pill } from "@/components/ui/Pill";
import { Sheet } from "@/components/ui/Sheet";
import { api, ApiError } from "@/lib/api/client";
import type { CircleSummary } from "@/lib/api/types";
import { formatPaise } from "@/lib/money";

/**
 * "Add to circle": one of his own agreed entries onto a family circle's list, so
 * anyone in it can pay it. In one circle it goes straight there; in several, a
 * sheet asks which. It stays his udhaar either way.
 */

/** Put an entry on a circle's list. Returns why not, or null. */
export async function addToCircle(
  circleId: string,
  entryId: string,
  personId: string,
): Promise<string | null> {
  try {
    await api(`/circles/${circleId}/share`, { person_id: personId, entry_id: entryId });
    return null;
  } catch (e) {
    return e instanceof ApiError ? e.message : "That didn't go through.";
  }
}

export function CirclePicker({
  circles,
  onPick,
  onClose,
}: {
  circles: CircleSummary[];
  onPick: (circleId: string) => void;
  onClose: () => void;
}): React.ReactElement {
  return (
    <Sheet>
      <p className="text-[16px] font-extrabold tracking-[-0.02em]">Which circle?</p>
      <p className="mt-1 text-[12.5px] font-medium leading-normal text-sub">
        Anyone in it can pay this. It stays your udhaar; nobody there will owe it.
      </p>
      <div className="mt-3 flex flex-col gap-2">
        {circles.map((c) => (
          <button
            key={c.id}
            type="button"
            onClick={() => onPick(c.id)}
            className="rounded-[12px] bg-tile px-3.5 py-3 text-left"
          >
            <p className="text-[14.5px] font-extrabold">{c.name}</p>
            <p className="mt-0.5 text-[12px] font-medium text-sub">
              {c.members.join(", ")}
              {c.open_count ? ` · ${formatPaise(c.open_paise)} on its list` : ""}
            </p>
          </button>
        ))}
      </div>
      <div className="mt-3">
        <Pill tone="outline" onClick={onClose}>
          Not now
        </Pill>
      </div>
    </Sheet>
  );
}

export function AddToCircle({
  entryId,
  personId,
  circles,
  onDone,
  tone = "outline",
  compact = false,
}: {
  entryId: string;
  personId: string;
  circles: CircleSummary[];
  /** After it went on a list, or with why it could not. */
  onDone: (problem: string | null) => void;
  tone?: "outline" | "navy";
  /** A small text button, for a line in a list. */
  compact?: boolean;
}): React.ReactElement | null {
  const [picking, setPicking] = useState(false);
  const [busy, setBusy] = useState(false);
  if (!circles.length) return null;

  async function to(circleId: string): Promise<void> {
    setPicking(false);
    setBusy(true);
    onDone(await addToCircle(circleId, entryId, personId));
    setBusy(false);
  }

  function start(): void {
    if (circles.length === 1) void to(circles[0].id);
    else setPicking(true);
  }

  return (
    <>
      {compact ? (
        <button
          type="button"
          disabled={busy}
          onClick={start}
          className="text-[12px] font-extrabold text-cyan-text disabled:opacity-40"
        >
          Add to circle
        </button>
      ) : (
        <Pill tone={tone} disabled={busy} onClick={start}>
          Add to circle
        </Pill>
      )}
      {picking ? (
        <CirclePicker
          circles={circles}
          onPick={(id) => void to(id)}
          onClose={() => setPicking(false)}
        />
      ) : null}
    </>
  );
}
