import { readFileSync } from "node:fs";
import path from "node:path";

import { describe, expect, it } from "vitest";

import type { Chip } from "./chip";
import { parseShop } from "./contract";

const raw = JSON.parse(
  readFileSync(path.resolve(__dirname, "../../contract/shop.json"), "utf-8"),
) as ReturnType<typeof parseShop>;

describe("contract/shop.json", () => {
  it("parses: the file make db wrote is one the UI can draw", () => {
    const shop = parseShop(raw);
    expect(shop.book.lines.length).toBe(shop.book.owing_count);
  });

  it("is never sorted by how much anyone owes", () => {
    const names = raw.book.lines.map((l) => l.display_name.toLowerCase());
    expect(names).toEqual([...names].sort());
  });

  it("rejects a status the UI has no words for", () => {
    const bad = structuredClone(raw);
    bad.book.lines[0].chip = "overdue" as Chip;
    expect(() => parseShop(bad)).toThrow(/unknown status/);
  });

  it("rejects money that is not whole paise", () => {
    const bad = structuredClone(raw);
    bad.book.lines[0].balance_paise = 199.5;
    expect(() => parseShop(bad)).toThrow(/whole number/);
  });

  it("rejects demo data that is not marked synthetic", () => {
    const bad = { ...structuredClone(raw), synthetic: false };
    expect(() => parseShop(bad)).toThrow(/synthetic/);
  });
});
