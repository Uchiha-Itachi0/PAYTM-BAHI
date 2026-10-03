/**
 * The shape of contract/shop.json: the shopkeeper's book.
 *
 * Written by hand for now, because the read API does not exist yet. When it
 * lands (BIT-8 B8) these types are generated from its OpenAPI spec and this file
 * shrinks to the parser below.
 *
 * `parseShop` checks the file instead of trusting it. A status the UI does not
 * know, or money that is not whole paise, fails loudly at load rather than
 * rendering something nobody designed.
 */

import { CHIPS, type Chip } from "./chip";

export type Joined = "linked" | "invited" | "name_only";

export interface Rhythm {
  n: number;
  median_gap: number | null;
  max_gap: number | null;
  last_paid: string | null;
}

export interface BookLine {
  customer_id: string;
  display_name: string;
  tag: string | null;
  joined: Joined;
  balance_paise: number;
  day: number;
  chip: Chip;
  rhythm: Rhythm;
}

export interface Book {
  customer_count: number;
  invited_count: number;
  owing_count: number;
  outstanding_paise: number;
  lines: BookLine[];
}

export interface Shop {
  synthetic: boolean;
  today: string;
  shop: { id: string; name: string; locality: string };
  book: Book;
}

const JOINED: readonly Joined[] = ["linked", "invited", "name_only"];

function fail(what: string): never {
  throw new Error(`contract/shop.json: ${what}`);
}

function count(v: unknown, what: string): number {
  if (typeof v !== "number" || !Number.isInteger(v) || v < 0) {
    fail(`${what} must be a whole number, got ${JSON.stringify(v)}`);
  }
  return v;
}

export function parseShop(raw: unknown): Shop {
  const data = raw as Shop;
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
