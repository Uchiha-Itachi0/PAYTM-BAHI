import Link from "next/link";

/**
 * The floating navy pill at the bottom of the screen: Paytm's "Scan QR", and
 * our "Add udhaar". It stays in reach of a thumb while the list scrolls.
 *
 * `floating`: on a fixed screen it hovers over the list, as Paytm's does,
 * instead of taking a line of its own.
 */
export function StickyPill({
  icon,
  href,
  floating = false,
  onTap,
  children,
}: {
  icon: React.ReactNode;
  href?: string;
  floating?: boolean;
  /** Runs inside the tap, before the link opens. */
  onTap?: () => void;
  children: React.ReactNode;
}): React.ReactElement {
  const cls =
    "flex items-center gap-[9px] rounded-full bg-navy px-[26px] py-3 text-[14.5px] font-extrabold text-white shadow-pill [&_svg]:size-[19px]";
  return (
    <div
      className={
        floating
          ? "pointer-events-none absolute inset-x-0 bottom-4 flex justify-center [&>*]:pointer-events-auto"
          : "sticky bottom-3 mt-auto flex justify-center pt-2"
      }
    >
      {href ? (
        <Link href={href} onClick={onTap} className={cls}>
          {icon}
          {children}
        </Link>
      ) : (
        <button type="button" className={cls}>
          {icon}
          {children}
        </button>
      )}
    </div>
  );
}
