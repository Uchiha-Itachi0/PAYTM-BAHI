/**
 * A number pad for typing an amount in rupees. The fallback to voice, and the
 * choice when he would rather not say someone's udhaar out loud at the counter.
 */
const KEYS = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "00", "0", "⌫"] as const;
export type Key = (typeof KEYS)[number];

export function Keypad({ onKey }: { onKey: (k: Key) => void }): React.ReactElement {
  return (
    <div className="grid grid-cols-3 gap-2">
      {KEYS.map((k) => (
        <button
          key={k}
          type="button"
          onClick={() => onKey(k)}
          aria-label={k === "⌫" ? "Delete" : k}
          className="h-12 rounded-tile bg-tile text-[19px] font-bold tabular-nums active:bg-hair"
        >
          {k}
        </button>
      ))}
    </div>
  );
}

/** The next amount string after a key, capped so nobody types a lakh by accident. */
export function press(current: string, k: Key, max = 6): string {
  if (k === "⌫") return current.slice(0, -1);
  const next = (current + k).replace(/^0+/, "");
  return next.length > max ? current : next;
}
