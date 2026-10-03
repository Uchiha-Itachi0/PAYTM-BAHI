import Link from "next/link";

/**
 * The rounded button. Navy for the primary action, cyan for money going out,
 * outline for the way back ("Say it again", "That's not right").
 *
 * Renders a link when given `href`, a button otherwise. The copy is the caller's,
 * and the four rules decide it: "Yes, I owe ₹200", never "I'll pay by Friday".
 */
type Tone = "navy" | "cyan" | "outline";

const TONE: Record<Tone, string> = {
  navy: "bg-navy text-white",
  cyan: "bg-cyan text-white",
  outline: "border-[1.5px] border-line bg-white text-ink text-[14px] font-bold",
};

export function Pill({
  tone = "navy",
  href,
  onClick,
  disabled = false,
  children,
}: {
  tone?: Tone;
  href?: string;
  onClick?: () => void;
  disabled?: boolean;
  children: React.ReactNode;
}): React.ReactElement {
  const cls = `block w-full rounded-pill p-[13px] text-center text-[15px] font-extrabold tracking-[-0.015em] disabled:opacity-40 ${TONE[tone]}`;
  return href ? (
    <Link href={href} className={cls}>
      {children}
    </Link>
  ) : (
    <button type="button" className={cls} onClick={onClick} disabled={disabled}>
      {children}
    </button>
  );
}
