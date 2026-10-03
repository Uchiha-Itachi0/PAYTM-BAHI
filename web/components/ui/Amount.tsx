import { formatPaise } from "@/lib/money";

/**
 * An amount the way Paytm's chat cards write it: a small raised ₹, then the
 * figure, heavy and tight. The figure is the API's, formatted by formatPaise.
 */
export function Amount({
  paise,
  struck = false,
  className = "",
}: {
  paise: number;
  struck?: boolean;
  className?: string;
}): React.ReactElement {
  const text = formatPaise(paise);
  const sign = text.startsWith("-") ? "-" : "";
  return (
    <span
      className={`inline-flex items-start font-extrabold leading-none tracking-[-0.035em] tabular-nums ${
        struck ? "text-sub line-through decoration-2" : ""
      } ${className}`}
    >
      {sign}
      <span className="mr-[0.06em] mt-[0.1em] text-[0.58em]">₹</span>
      {text.replace(/^-?₹/, "")}
    </span>
  );
}
