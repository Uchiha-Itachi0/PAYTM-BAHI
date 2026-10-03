import { Amount } from "@/components/ui/Amount";
import { formatPaise } from "@/lib/money";

/**
 * What stands now, at the top of a thread: the figure every card's passbook line
 * leads up to. Agreed only; what waits for a yes, or is questioned, is named
 * beside it and not added (as on the book).
 */
export function Owes({
  label,
  owed,
  waiting,
  disputed,
}: {
  label: string;
  owed: number;
  waiting: number;
  disputed: number;
}): React.ReactElement {
  const apart = [
    waiting > 0 ? `${formatPaise(waiting)} waiting for a yes` : null,
    disputed > 0 ? `${formatPaise(disputed)} questioned` : null,
  ].filter(Boolean);
  return (
    <div className="flex items-center justify-between gap-3 rounded-card bg-card px-3.5 py-2.5">
      <div className="min-w-0">
        <p className="text-[12px] font-semibold text-sub">{label}</p>
        {apart.length ? (
          <p className="mt-0.5 truncate text-[11.5px] font-semibold text-sub">
            Not counted: {apart.join(" · ")}
          </p>
        ) : null}
      </div>
      {owed > 0 ? (
        <Amount paise={owed} className="flex-none text-[22px]" />
      ) : (
        <span className="flex-none text-[14px] font-extrabold text-ok">All clear</span>
      )}
    </div>
  );
}
