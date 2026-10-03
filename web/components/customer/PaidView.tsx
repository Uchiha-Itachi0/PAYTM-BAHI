import { Check } from "@/components/icons";
import { CustomerShell } from "@/components/shell/Shell";
import { Card } from "@/components/ui/Card";
import { Pill } from "@/components/ui/Pill";
import type { Paid } from "@/lib/api/types";
import { formatPaise } from "@/lib/money";
import { clockTime, fullDate } from "@/lib/when";

/**
 * B3 · After paying: what he paid, and what is left.
 *
 * Paid in full, it is Cleared: nothing outstanding at this shop, and what is
 * still open elsewhere. Paid in part, it says what is still open here. Either
 * way the shop has been told, in the thread, with what is left.
 */
export function PaidView({
  paid,
  back,
  backLabel,
}: {
  paid: Paid;
  back: string;
  backLabel: string;
}): React.ReactElement {
  const cleared = paid.left_paise === 0;
  return (
    <CustomerShell
      heading={{ title: cleared ? "Cleared" : "Paid", sub: paid.shop.name, back }}
    >
      <Card>
        <div className="py-3 text-center">
          <div className="mx-auto mb-3 grid size-16 place-items-center rounded-full bg-ok-bg text-paid [&_svg]:size-8">
            <Check />
          </div>
          <p className="text-[26px] font-extrabold tracking-[-0.03em]">
            {formatPaise(paid.amount_paise)} paid
          </p>
          <p className="mt-1.5 text-[13px] font-medium leading-normal text-sub">
            {fullDate(paid.paid_at)}, {clockTime(paid.paid_at)} · UPI
            <br />
            {paid.shop.name} has been told.
          </p>
        </div>
      </Card>
      <Card title={paid.shop.name} tight>
        <div className="flex items-start justify-between">
          <div>
            <p className="text-[14.5px] font-extrabold">
              {cleared ? "Nothing outstanding" : "Still open here"}
            </p>
            <p className="mt-0.5 text-[12px] font-medium text-sub">
              {!cleared
                ? "Pay the rest whenever you can. There is no date."
                : paid.settled_in === 0
                  ? "Settled the same day"
                  : `Settled in ${paid.settled_in} ${paid.settled_in === 1 ? "day" : "days"}`}
            </p>
          </div>
          <p className="text-[15px] font-extrabold tabular-nums">
            {formatPaise(paid.left_paise)}
          </p>
        </div>
      </Card>
      {paid.elsewhere.length ? (
        <Card title="Still open elsewhere" tight>
          {paid.elsewhere.map((s) => (
            <div
              key={s.shop.id}
              className="flex items-start justify-between border-b border-hair py-2.5 last:border-b-0"
            >
              <div>
                <p className="text-[14.5px] font-extrabold">{s.shop.name}</p>
                {s.day !== null ? (
                  <p className="mt-0.5 text-[12px] font-medium text-sub">day {s.day}</p>
                ) : null}
              </div>
              <p className="text-[15px] font-extrabold tabular-nums">
                {formatPaise(s.balance_paise)}
              </p>
            </div>
          ))}
        </Card>
      ) : null}
      <Pill tone="outline" href={back}>
        {backLabel}
      </Pill>
    </CustomerShell>
  );
}
