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

const ONES = [
  "", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten",
  "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen", "Seventeen",
  "Eighteen", "Nineteen",
];
const TENS = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"];

function belowHundred(n: number): string {
  if (n < 20) return ONES[n];
  return [TENS[Math.floor(n / 10)], ONES[n % 10]].filter(Boolean).join(" ");
}

function belowThousand(n: number): string {
  const hundreds = Math.floor(n / 100);
  return [hundreds ? `${ONES[hundreds]} Hundred` : "", belowHundred(n % 100)]
    .filter(Boolean)
    .join(" ");
}

/**
 * Whole rupees in words, the way Paytm writes them under an amount: 10000 paise
 * is "Rupees One Hundred Only". Indian grouping (thousand, lakh, crore). Paise
 * are left out: what is entered here is whole rupees.
 */
export function inWords(paise: number): string {
  let n = Math.floor(Math.abs(paise) / 100);
  if (n === 0) return "";
  const parts: string[] = [];
  for (const [size, word] of [
    [10_000_000, "Crore"],
    [100_000, "Lakh"],
    [1_000, "Thousand"],
  ] as const) {
    const count = Math.floor(n / size);
    if (count) parts.push(`${belowThousand(count)} ${word}`);
    n %= size;
  }
  if (n) parts.push(belowThousand(n));
  return `Rupees ${parts.join(" ")} Only`;
}
