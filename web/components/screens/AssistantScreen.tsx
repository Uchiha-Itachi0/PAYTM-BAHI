"use client";

import { useState } from "react";

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
 *
 * The conversation carries on between visits, like a chat. New chat starts
 * another; the old one stays on the server with every other turn.
 */

/** What he might ask, offered before the first question. Tapping one asks it. */
const STARTERS = [
  "इस हफ़्ते कौन पैसे देगा?",
  "कल किसको याद दिलाना है?",
  "Sharma ka hisaab batao",
  "How do I stop a reminder?",
];

/** Where this browser keeps the assistant's conversation. */
const KEPT = "bahi.assistant.conversation";

export function AssistantScreen(): React.ReactElement {
  // A new chat is a fresh Munshi: nothing of the old one stays on screen.
  const [chat, setChat] = useState(0);

  return (
    <MerchantShell
      heading={{
        title: "Paytm Assistant",
        sub: "Ask anything about your book",
        back: "/m",
        action: (
          <button
            type="button"
            onClick={() => {
              try {
                localStorage.removeItem(KEPT);
              } catch {
                // Storage off: there was nothing kept.
              }
              setChat((n) => n + 1);
            }}
            className="text-[13px] font-extrabold text-cyan-text"
          >
            New chat
          </button>
        ),
      }}
    >
      <Munshi
        key={chat}
        full
        keep={KEPT}
        listen={false}
        starters={STARTERS}
        onWritten={() => undefined}
      />
    </MerchantShell>
  );
}
