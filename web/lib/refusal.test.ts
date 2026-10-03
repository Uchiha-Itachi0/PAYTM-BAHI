import { describe, expect, it } from "vitest";

import { refusal } from "./api/client";

describe("refusal", () => {
  it("says which field failed, in the screen's words", () => {
    const detail = [{ loc: ["body", "tag"], msg: "String should have at most 80 characters" }];
    expect(refusal(422, detail)).toBe("Where they live or work: String should have at most 80 characters");
  });

  it("keeps the API's own sentence", () => {
    expect(refusal(409, "that is more than the ₹100 you owe")).toBe("that is more than the ₹100 you owe");
  });

  it("is never empty, even with nothing from the server", () => {
    expect(refusal(502, undefined)).toMatch(/isn't answering/);
    expect(refusal(500, undefined)).toBe("Something went wrong (500).");
  });
});
