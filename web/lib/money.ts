/**
 * Money arrives as integer paise and is only ever turned into text here.
 *
 * The same rule as the backend's `rupees()`: Indian grouping, whole rupees
 * without ".00", a paise remainder always to two digits. The frontend never
 * adds, subtracts or rounds money; every figure it shows was computed by the API.
 */

const grouped = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 0 });

export function formatPaise(paise: number): string {
  if (!Number.isInteger(paise)) {
    throw new Error(`money must be whole paise, got ${paise}`);
  }
  const sign = paise < 0 ? "-" : "";
  const abs = Math.abs(paise);
  const whole = Math.floor(abs / 100);
  const frac = abs % 100;
  const text = `${sign}₹${grouped.format(whole)}`;
  return frac ? `${text}.${String(frac).padStart(2, "0")}` : text;
}
