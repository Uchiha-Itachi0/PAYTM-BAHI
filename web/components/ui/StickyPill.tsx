/**
 * The floating navy pill at the bottom of the screen: Paytm's "Scan QR", and
 * our "Add udhaar". It stays in reach of a thumb while the list scrolls.
 */
export function StickyPill({
  icon,
  children,
}: {
  icon: React.ReactNode;
  children: React.ReactNode;
}): React.ReactElement {
  return (
    <div className="sticky bottom-3 mt-auto flex justify-center pt-2">
      <button
        type="button"
        className="flex items-center gap-[9px] rounded-full bg-navy px-[26px] py-3 text-[14.5px] font-extrabold text-white shadow-pill [&_svg]:size-[19px]"
      >
        {icon}
        {children}
      </button>
    </div>
  );
}
