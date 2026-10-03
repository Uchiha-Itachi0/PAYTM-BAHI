import { describe, expect, it } from "vitest";

import { CHIP_LABEL, CHIPS, type Chip } from "./chip";

describe("status chips", () => {
  it("has words for every status and only those", () => {
    expect(Object.keys(CHIP_LABEL).sort()).toEqual([...CHIPS].sort());
  });

  it("cannot be written as a verdict", () => {
    // Checked by `tsc`, not at runtime: if "overdue" ever becomes a valid Chip,
    // this @ts-expect-error has nothing to expect and the type check fails.
    // @ts-expect-error "overdue" is not a status
    const verdict: Chip = "overdue";
    expect(CHIPS).not.toContain(verdict);
  });
});
