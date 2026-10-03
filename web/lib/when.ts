/**
 * Times as Kurla reads them. Every timestamp from the API is shown in IST,
 * whatever the phone's own timezone, and "Today" is the product's today (the
 * API sends it: the demo pins the date), never the phone's.
 */

const IST = "Asia/Kolkata";

const TIME = new Intl.DateTimeFormat("en-IN", {
  timeZone: IST,
  hour: "numeric",
  minute: "2-digit",
  hour12: true,
});
const MONTH = new Intl.DateTimeFormat("en-US", { timeZone: IST, month: "short" });
const DATE = new Intl.DateTimeFormat("en-US", { timeZone: IST, day: "numeric" });
const LONG = new Intl.DateTimeFormat("en-IN", { timeZone: IST, day: "numeric", month: "long" });
const YEAR = new Intl.DateTimeFormat("en-US", { timeZone: IST, year: "numeric" });

/** "10 Sep": day first, the way Kurla writes it, and "Sep" not "Sept". */
function dayMonth(d: Date): string {
  return `${DATE.format(d)} ${MONTH.format(d)}`;
}
const DAY = new Intl.DateTimeFormat("en-CA", { timeZone: IST });

/** "10:34 am". */
export function clockTime(iso: string): string {
  return TIME.format(new Date(iso)).replace(/\s?([ap])\.?m\.?/i, " $1m").toLowerCase();
}

/** The IST calendar day of a timestamp, as "2026-10-03". */
export function dayOf(iso: string): string {
  return DAY.format(new Date(iso));
}

function yesterday(today: string): string {
  const d = new Date(`${today}T12:00:00+05:30`);
  d.setUTCDate(d.getUTCDate() - 1);
  return DAY.format(d);
}

/** A thread's date separator: "Today", "Yesterday", "22 September". */
export function dayLabel(iso: string, today: string): string {
  const day = dayOf(iso);
  if (day === today) return "Today";
  if (day === yesterday(today)) return "Yesterday";
  return LONG.format(new Date(iso));
}

/** An inbox row's time: "10:34 am" today, else "20 Sep". */
export function shortWhen(iso: string, today: string): string {
  return dayOf(iso) === today ? clockTime(iso) : dayMonth(new Date(iso));
}

/** "20 Sep". */
export function shortDate(iso: string): string {
  return dayMonth(new Date(iso.length === 10 ? `${iso}T12:00:00+05:30` : iso));
}

/** "14 Jul 2023". */
export function fullDate(iso: string): string {
  const d = new Date(iso);
  return `${dayMonth(d)} ${YEAR.format(d)}`;
}
