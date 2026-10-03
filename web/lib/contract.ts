/**
 * Checks a shop book before the UI draws it.
 *
 * The types are generated from the API (lib/api/types.ts). This checks the values
 * the types cannot: a status the UI has no words for, or money that is not whole
 * paise, fails loudly here rather than rendering something nobody designed.
 */

import type { ShopBook } from "./api/types";
import { CHIPS } from "./chip";

const JOINED = ["linked", "invited", "name_only"] as const;

function fail(what: string): never {
  throw new Error(`shop book: ${what}`);
}

function count(v: unknown, what: string): number {
  if (typeof v !== "number" || !Number.isInteger(v) || v < 0) {
    fail(`${what} must be a whole number, got ${JSON.stringify(v)}`);
  }
  return v;
}

export function parseShop(raw: unknown): ShopBook {
  const data = raw as ShopBook;
  if (!data?.book || !Array.isArray(data.book.lines)) fail("no book");
  if (data.synthetic !== true) fail("demo data must be marked synthetic");

  count(data.book.outstanding_paise, "outstanding_paise");
  count(data.book.owing_count, "owing_count");
  count(data.book.customer_count, "customer_count");

  for (const line of data.book.lines) {
    const who = line.display_name;
    if (!CHIPS.includes(line.chip)) fail(`${who} has unknown status "${line.chip}"`);
    if (!JOINED.includes(line.joined)) fail(`${who} has unknown join "${line.joined}"`);
    count(line.balance_paise, `${who}'s balance_paise`);
    count(line.day, `${who}'s day`);
  }
  return data;
}
