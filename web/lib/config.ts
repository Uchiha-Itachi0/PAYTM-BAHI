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

/**
 * Where the project lives, shown on the start page. A link left empty is not
 * shown, so the page never offers a dead one.
 */
export const LINKS: { label: string; note: string; url: string }[] = [
  {
    label: "Code on GitHub",
    note: "Uchiha-Itachi0/PAYTM-BAHI",
    url: "https://github.com/Uchiha-Itachi0/PAYTM-BAHI",
  },
  {
    label: "Demo video",
    note: "The whole flow, start to end",
    url: "https://drive.google.com/file/d/1UZOw8tcfHFTYClp9S92xpVZdtaBiOi_l/view?usp=drive_link",
  },
  {
    label: "Pitch deck (PDF)",
    note: "The problem, the build and the numbers",
    url: "https://drive.google.com/file/d/1ylEn8Cx-0x96Xr9wXf0pHjXX57AK_As0/view?usp=sharing",
  },
];
