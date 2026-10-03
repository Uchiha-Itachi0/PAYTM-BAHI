"use client";

import { Munshi } from "@/components/munshi/Munshi";
import { MerchantShell } from "@/components/shell/Shell";

/**
 * A6 · Paytm Assistant, for the shopkeeper.
 *
 * The same munshi as on Add udhaar (the same tools over the real book, the same
 * memory, voice and cards), on a page of its own, for when he wants to ask rather
 * than write: who is likely to pay this week, what Patil's account looks like,
 * who gets a reminder tomorrow, how something in the app works. It can still
 * write: an entry is a card that waits for his yes, as everywhere.
 */

/** What he might ask, offered before the first question. Tapping one asks it. */
const STARTERS = [
  "इस हफ़्ते कौन पैसे देगा?",
  "कल किसको याद दिलाना है?",
  "Sharma ka hisaab batao",
  "How do I stop a reminder?",
];

export function AssistantScreen(): React.ReactElement {
  return (
    <MerchantShell
      heading={{ title: "Paytm Assistant", sub: "Ask anything about your book", back: "/m" }}
    >
      <Munshi full listen={false} starters={STARTERS} onWritten={() => undefined} />
    </MerchantShell>
  );
}
