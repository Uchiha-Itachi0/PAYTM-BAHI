import "server-only";

import { networkInterfaces } from "node:os";

/**
 * The laptop's address on the wifi, for a link a phone can open.
 *
 * On the laptop the shop's screens run on localhost: the browser only allows the
 * mic there (or on https). A phone can't open localhost, so the udhaar QR uses
 * this address instead, and the laptop stays where its mic works.
 *
 * Private ranges only, the same ones next.config.ts lets a phone load the dev
 * server from: home wifi (192.168.x.x), an office (10.x.x.x), a phone's hotspot
 * (172.20.10.x).
 */
const PRIVATE = [/^192\.168\./, /^10\./, /^172\.20\.10\./];

export function wifiAddress(): string | null {
  for (const nets of Object.values(networkInterfaces())) {
    for (const net of nets ?? []) {
      if (net.family === "IPv4" && !net.internal && PRIVATE.some((r) => r.test(net.address)))
        return net.address;
    }
  }
  return null;
}

/** "localhost:3000" or "127.0.0.1:3000": only this machine can open it. */
export function onlyHere(host: string): boolean {
  return /^(localhost|127\.0\.0\.1|\[::1\])(:\d+)?$/.test(host);
}
