/**
 * The floating white card: the core Paytm object. Borderless, 16px radius,
 * sitting on the sky ground. Everything on a screen lives in one.
 *
 * `fill`: the card takes the rest of a fixed screen and only its body scrolls,
 * under its title, the way Paytm's lists scroll under a fixed top. The body
 * keeps room at the bottom for the floating pill.
 */
export function Card({
  title,
  tight = false,
  fill = false,
  children,
}: {
  title?: string;
  tight?: boolean;
  fill?: boolean;
  children: React.ReactNode;
}): React.ReactElement {
  return (
    <section
      className={`rounded-card bg-card px-3.5 ${tight ? "py-3" : "py-[15px]"} ${
        fill ? "flex min-h-0 flex-1 flex-col pb-0" : ""
      }`}
    >
      {title ? (
        <h2 className="mb-2.5 text-[14px] font-extrabold tracking-[-0.02em]">
          {title}
        </h2>
      ) : null}
      {fill ? (
        <div className="-mx-3.5 min-h-0 flex-1 overflow-y-auto overscroll-contain px-3.5 pb-20">
          {children}
        </div>
      ) : (
        children
      )}
    </section>
  );
}
