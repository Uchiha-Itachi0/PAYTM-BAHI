/**
 * The shop the demo runs in. Its id is a uuid5 from the seed (data/world.py),
 * so it is the same on every machine and every rebuild, and it can live here.
 */
/** How long the shop's description of someone can be: the API's TAG_CHARS. */
export const TAG_CHARS = 80;
/** How long a name can be, as the API checks it. */
export const NAME_CHARS = 40;

export const SHOP_ID =
  process.env.NEXT_PUBLIC_SHOP_ID ?? "ed694cd0-1e58-53b6-aa92-b49d5d0974d1";
