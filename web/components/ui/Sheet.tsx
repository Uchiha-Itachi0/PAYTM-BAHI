/**
 * A bottom sheet over whatever he was doing: how a Paytm notification asks for
 * something. The confirmation lives in one, because it is a moment inside the app
 * he already has open, not a separate product.
 */
export function Sheet({ children }: { children: React.ReactNode }): React.ReactElement {
  return (
    <div className="fixed inset-0 z-10 flex items-end bg-scrim">
      <section
        role="dialog"
        aria-modal="true"
        className="mx-auto w-full max-w-[430px] rounded-t-[20px] bg-card px-4 pb-5 pt-3.5 shadow-sheet"
      >
        <div aria-hidden="true" className="mx-auto mb-3.5 h-1 w-9 rounded-sm bg-hair" />
        {children}
      </section>
    </div>
  );
}
