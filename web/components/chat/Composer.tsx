"use client";

import { useState } from "react";

/**
 * The line at the bottom of a thread: type, send. Words only, because a message
 * has nowhere to carry an amount; entries come from the book.
 */
export function Composer({
  placeholder,
  disabled,
  why,
  onSend,
}: {
  placeholder: string;
  disabled?: boolean;
  /** Why it is off, shown in its place. */
  why?: string;
  onSend: (text: string) => Promise<void>;
}): React.ReactElement {
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);

  if (disabled) {
    return (
      <p className="mt-auto rounded-card bg-quiet-bg px-3.5 py-3 text-center text-[12.5px] font-semibold text-quiet">
        {why}
      </p>
    );
  }
  return (
    <form
      className="sticky bottom-2 mt-auto flex items-center gap-2 rounded-pill bg-card p-1.5 pl-4 shadow-sheet"
      onSubmit={(e) => {
        e.preventDefault();
        const words = text.trim();
        if (!words || busy) return;
        setBusy(true);
        void onSend(words)
          .then(() => setText(""))
          .finally(() => setBusy(false));
      }}
    >
      <input
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder={placeholder}
        aria-label={placeholder}
        maxLength={500}
        className="min-w-0 flex-1 bg-transparent text-[14.5px] font-semibold outline-none placeholder:font-medium placeholder:text-sub"
      />
      <button
        type="submit"
        disabled={!text.trim() || busy}
        className="rounded-pill bg-navy px-4 py-2 text-[13.5px] font-extrabold text-white disabled:opacity-40"
      >
        Send
      </button>
    </form>
  );
}
