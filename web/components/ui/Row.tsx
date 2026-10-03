import type { Chip } from "@/lib/chip";
import { formatPaise } from "@/lib/money";

import { StatusChip } from "./StatusChip";

/**
 * A transaction line: coloured avatar, name and a sub-line on the left, the
 * amount right-aligned in tabular figures with an optional status beneath.
 * Rows sit inside a Card and draw their own hairline between them.
 */
const TINTS = [
  "bg-av-blue text-av-blue-ink",
  "bg-av-yellow text-av-yellow-ink",
  "bg-av-pink text-av-pink-ink",
  "bg-av-mint text-av-mint-ink",
  "bg-av-lilac text-av-lilac-ink",
] as const;

/** A customer keeps the same colour everywhere, because it comes from his name. */
export function tintFor(name: string): string {
  let h = 0;
  for (const ch of name) h = (h * 31 + ch.charCodeAt(0)) >>> 0;
  return TINTS[h % TINTS.length];
}

export function Avatar({ name }: { name: string }): React.ReactElement {
  return (
    <div
      aria-hidden="true"
      className={`grid size-[38px] flex-none place-items-center rounded-full text-[13px] font-extrabold ${tintFor(name)}`}
    >
      {name.trim().charAt(0).toUpperCase()}
    </div>
  );
}

export function Row({
  name,
  sub,
  amountPaise,
  chip,
}: {
  name: string;
  sub?: string;
  amountPaise?: number;
  chip?: Chip;
}): React.ReactElement {
  return (
    <div className="flex items-center gap-[11px] border-b border-hair py-[11px] first:pt-0.5 last:border-b-0 last:pb-0.5">
      <Avatar name={name} />
      <div className="min-w-0 flex-1">
        <p className="truncate text-[14.5px] font-bold tracking-[-0.015em]">{name}</p>
        {sub ? (
          <p className="mt-0.5 truncate text-[11.5px] font-medium text-sub">{sub}</p>
        ) : null}
      </div>
      {amountPaise !== undefined || chip ? (
        <div className="flex flex-none flex-col items-end gap-1.5">
          {amountPaise !== undefined ? (
            <span className="text-[15px] font-extrabold tracking-[-0.02em] tabular-nums">
              {formatPaise(amountPaise)}
            </span>
          ) : null}
          {chip ? <StatusChip chip={chip} /> : null}
        </div>
      ) : null}
    </div>
  );
}
