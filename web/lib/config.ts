/**
 * The shop the demo runs in. Its id is a uuid5 from the seed (data/world.py),
 * so it is the same on every machine and every rebuild, and it can live here.
 */
export const SHOP_ID =
  process.env.NEXT_PUBLIC_SHOP_ID ?? "ed694cd0-1e58-53b6-aa92-b49d5d0974d1";
