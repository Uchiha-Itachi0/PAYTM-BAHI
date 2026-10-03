/**
 * One big number with a label above and a line of context below, the way Paytm
 * shows a balance. The value arrives already formatted; this never computes it.
 */
export function Figure({
  label,
  value,
  fine,
}: {
  label: string;
  value: string;
  fine?: string;
}): React.ReactElement {
  return (
    <div>
      <p className="text-[12.5px] font-semibold text-sub">{label}</p>
      <p className="mt-0.5 text-[31px] font-extrabold leading-tight tracking-[-0.035em] tabular-nums">
        {value}
      </p>
      {fine ? (
        <p className="mt-1 text-[12px] leading-[1.45] text-sub">{fine}</p>
      ) : null}
    </div>
  );
}
