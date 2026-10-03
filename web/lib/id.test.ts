import { describe, expect, it } from "vitest";

import { newId, uuid4 } from "./id";

// What the API's `person_id: UUID` accepts, narrowed to version 4.
const V4 = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;

describe("uuid4", () => {
  it("sets the version and variant bits whatever the bytes", () => {
    expect(uuid4(new Uint8Array(16))).toBe("00000000-0000-4000-8000-000000000000");
    expect(uuid4(new Uint8Array(16).fill(0xff))).toBe(
      "ffffffff-ffff-4fff-bfff-ffffffffffff",
    );
  });

  it("does not change the bytes it was given", () => {
    const bytes = new Uint8Array(16).fill(0xff);
    uuid4(bytes);
    expect(bytes[6]).toBe(0xff);
  });

  it("refuses anything but sixteen bytes", () => {
    expect(() => uuid4(new Uint8Array(15))).toThrow(/16 bytes/);
  });
});

describe("newId", () => {
  it("is a version 4 UUID, and a new one each time", () => {
    const a = newId();
    expect(a).toMatch(V4);
    expect(newId()).not.toBe(a);
  });
});
