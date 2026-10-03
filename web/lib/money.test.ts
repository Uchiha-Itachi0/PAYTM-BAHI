import { describe, expect, it } from "vitest";

import { formatPaise, inWords } from "./money";

describe("formatPaise", () => {
  // The same cases as the backend's rupees(), so both sides print money alike.
  it.each([
    [0, "₹0"],
    [20000, "₹200"],
    [124000, "₹1,240"],
    [12400000, "₹1,24,000"],
    [1000000000, "₹1,00,00,000"],
    [1250, "₹12.50"],
    [5, "₹0.05"],
    [-20000, "-₹200"],
  ])("%i paise reads %s", (paise, text) => {
    expect(formatPaise(paise)).toBe(text);
  });

  it("refuses anything that is not whole paise", () => {
    expect(() => formatPaise(199.5)).toThrow(/whole paise/);
  });
});

describe("inWords", () => {
  it.each([
    [0, ""],
    [10000, "Rupees One Hundred Only"],
    [25050, "Rupees Two Hundred Fifty Only"],
    [2700000, "Rupees Twenty Seven Thousand Only"],
    [12345600, "Rupees One Lakh Twenty Three Thousand Four Hundred Fifty Six Only"],
  ])("%i paise is %s", (paise, words) => {
    expect(inWords(paise)).toBe(words);
  });
});
