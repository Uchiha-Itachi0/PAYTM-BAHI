/**
 * A short line of news on a tinted strip: sent, confirmed, or something to fix.
 * Amber at worst. There is no red.
 */
type Tone = "ok" | "warn" | "quiet";

const TONE: Record<Tone, string> = {
  ok: "bg-ok-bg text-ok",
  warn: "bg-warn-bg text-warn",
  quiet: "bg-quiet-bg text-quiet",
};

export function Notice({
  tone = "quiet",
  children,
}: {
  tone?: Tone;
  children: React.ReactNode;
}): React.ReactElement {
  return (
    <p
      role="status"
      className={`rounded-card px-3.5 py-3 text-[12.5px] font-semibold leading-normal ${TONE[tone]}`}
    >
      {children}
    </p>
  );
}

/** Three dots that breathe: someone is on the other side of this. */
export function Dots(): React.ReactElement {
  return (
    <span aria-label="waiting" className="flex justify-center gap-1.5">
      {[0, 200, 400].map((d) => (
        <i
          key={d}
          className="block size-2 animate-pulse rounded-full bg-cyan"
          style={{ animationDelay: `${d}ms` }}
        />
      ))}
    </span>
  );
}
