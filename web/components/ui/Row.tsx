import type { Chip } from "@/lib/chip";
import { formatPaise } from "@/lib/money";

import { StatusChip } from "./StatusChip";

/**
 * A transaction line: coloured avatar, name and a sub-line on the left, the
 * amount right-aligned in tabular figures with an optional status beneath.
 * Rows sit inside a Card and draw their own hairline between them.
 *
 * Given `onSelect`, the row becomes a choice with a radio on the right: how the
 * shopkeeper picks who is at the counter.
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

export function Avatar({
  name,
  size = "md",
}: {
  name: string;
  size?: "md" | "lg";
}): React.ReactElement {
  const dims = size === "lg" ? "size-14 text-[21px]" : "size-[38px] text-[13px]";
  return (
    <div
      aria-hidden="true"
      className={`grid flex-none place-items-center rounded-full font-extrabold ${dims} ${tintFor(name)}`}
    >
      {name.trim().charAt(0).toUpperCase()}
    </div>
  );
}

function Radio({ on }: { on: boolean }): React.ReactElement {
  return (
    <span
      aria-hidden="true"
      className={`size-[18px] flex-none rounded-full ${on ? "border-[5.5px] border-cyan" : "border-2 border-line"}`}
    />
  );
}

export function Row({
  name,
  sub,
  amountPaise,
  chip,
  selected,
  onSelect,
}: {
  name: string;
  sub?: string;
  amountPaise?: number;
  chip?: Chip;
  selected?: boolean;
  onSelect?: () => void;
}): React.ReactElement {
  const body = (
    <>
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
      {onSelect ? <Radio on={Boolean(selected)} /> : null}
    </>
  );
  const cls =
    "flex w-full items-center gap-[11px] border-b border-hair py-[11px] text-left first:pt-0.5 last:border-b-0 last:pb-0.5";
  return onSelect ? (
    <button type="button" onClick={onSelect} aria-pressed={selected} className={cls}>
      {body}
    </button>
  ) : (
    <div className={cls}>{body}</div>
  );
}
