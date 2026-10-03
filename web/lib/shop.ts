import "server-only";

import { readFile } from "node:fs/promises";
import path from "node:path";

import { parseShop, type Shop } from "./contract";

/**
 * The shopkeeper's book, from contract/shop.json at the repo root.
 *
 * Read on the server, never shipped to the browser as a module, which is what
 * `server-only` enforces. `make db` regenerates the file from the database.
 * When the read API lands this is the one function that changes: it will fetch
 * instead of read, and return the same Shop.
 */
export async function readShop(): Promise<Shop> {
  const file = path.join(process.cwd(), "..", "contract", "shop.json");
  return parseShop(JSON.parse(await readFile(file, "utf-8")));
}
