import { formatPaise } from "@/lib/money";

/**
 * "₹250 for Sharma", sending in three seconds unless he cancels.
 *
 * The bar is a CSS animation and its end is what sends: no timer that could drift
 * from what the screen shows. A wrong amount in the customer's favour is the one
 * mistake the customer won't catch, so the shopkeeper gets this moment to catch it.
 */
export function Countdown({
  name,
  paise,
  onDone,
  onCancel,
}: {
  name: string;
  paise: number;
  onDone: () => void;
  onCancel: () => void;
}): React.ReactElement {
  return (
    <section className="rounded-card bg-navy px-3.5 py-3 text-white" aria-live="polite">
      <p className="text-[12.5px] font-semibold opacity-80">Sending in 3 seconds</p>
      <p className="mt-0.5 text-[21px] font-extrabold tracking-[-0.03em]">
        {formatPaise(paise)} for {name}
      </p>
      <div className="mt-2.5 h-1.5 overflow-hidden rounded-full bg-white/20">
        <div
          className="h-full origin-left animate-countdown rounded-full bg-cyan"
          onAnimationEnd={onDone}
        />
      </div>
      <button
        type="button"
        onClick={onCancel}
        className="mt-3 block w-full rounded-pill bg-white p-[11px] text-center text-[15px] font-extrabold text-navy"
      >
        Cancel
      </button>
    </section>
  );
}
