/**
 * The floating white card: the core Paytm object. Borderless, 16px radius,
 * sitting on the sky ground. Everything on a screen lives in one.
 */
export function Card({
  title,
  tight = false,
  children,
}: {
  title?: string;
  tight?: boolean;
  children: React.ReactNode;
}): React.ReactElement {
  return (
    <section
      className={`rounded-card bg-card px-3.5 ${tight ? "py-3" : "py-[15px]"}`}
    >
      {title ? (
        <h2 className="mb-2.5 text-[14px] font-extrabold tracking-[-0.02em]">
          {title}
        </h2>
      ) : null}
      {children}
    </section>
  );
}
