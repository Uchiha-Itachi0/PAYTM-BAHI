/**
 * A random (version 4) UUID, on any page.
 *
 * `crypto.randomUUID` exists only on https and localhost. A phone opening the
 * laptop over plain http on the same wifi has `getRandomValues` but not
 * `randomUUID`, so the id is built from sixteen random bytes instead.
 */

export function uuid4(bytes: Uint8Array): string {
  if (bytes.length !== 16) throw new Error(`a UUID is 16 bytes, got ${bytes.length}`);
  const b = Uint8Array.from(bytes);
  b[6] = (b[6]! & 0x0f) | 0x40; // version 4
  b[8] = (b[8]! & 0x3f) | 0x80; // RFC 4122 variant
  const hex = Array.from(b, (x) => x.toString(16).padStart(2, "0")).join("");
  return [
    hex.slice(0, 8),
    hex.slice(8, 12),
    hex.slice(12, 16),
    hex.slice(16, 20),
    hex.slice(20),
  ].join("-");
}

export function newId(): string {
  return uuid4(crypto.getRandomValues(new Uint8Array(16)));
}
