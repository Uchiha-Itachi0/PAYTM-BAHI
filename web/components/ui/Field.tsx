/** A labelled text input, Paytm's rounded search-box style. */
export function Field({
  label,
  value,
  onChange,
  placeholder,
  autoFocus = false,
  inputMode,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  autoFocus?: boolean;
  inputMode?: "text" | "tel" | "search";
}): React.ReactElement {
  return (
    <label className="block">
      <span className="text-[12.5px] font-semibold text-sub">{label}</span>
      <input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        autoFocus={autoFocus}
        inputMode={inputMode}
        className="mt-2 block w-full rounded-[11px] border-[1.5px] border-line bg-white px-3 py-2.5 text-[15px] font-bold outline-none placeholder:font-medium placeholder:text-sub focus:border-cyan"
      />
    </label>
  );
}
