import { CHIP_LABEL, type Chip } from "@/lib/chip";

/**
 * Where someone is in their own rhythm. Takes a `Chip`, never a string, so the
 * words are fixed in lib/chip.ts. No red: "changed" is amber, because it means
 * "look at this", not "this person is bad".
 */
const TONE: Record<Chip, string> = {
  on_rhythm: "bg-ok-bg text-ok",
  changed: "bg-warn-bg text-warn",
  not_confirmed: "bg-quiet-bg text-quiet",
  new: "bg-av-blue text-av-blue-ink",
};

export function StatusChip({ chip }: { chip: Chip }): React.ReactElement {
  return (
    <span
      className={`inline-block rounded-md px-2 py-[3px] text-[10.5px] font-bold ${TONE[chip]}`}
    >
      {CHIP_LABEL[chip]}
    </span>
  );
}
