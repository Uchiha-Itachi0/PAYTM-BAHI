import { Card } from "@/components/ui/Card";
import type { Heard } from "@/lib/api/types";
import { formatPaise } from "@/lib/money";
import { HOW_LABEL, INTENT_LABEL, READER_LABEL, SOURCE_LABEL } from "@/lib/voice";

/**
 * What was heard, what read it, and every check our code made on that reading.
 * The shopkeeper can see why the screen picked who it picked, or why it asks.
 */
export function HeardCard({ heard }: { heard: Heard }): React.ReactElement {
  const who = heard.who;
  const said = heard.name ? `“${heard.name}”` : "No name";

  const amount =
    heard.amount_paise !== null
      ? `${formatPaise(heard.amount_paise)} · ${INTENT_LABEL[heard.intent]}`
      : heard.amount_words
        ? `“${heard.amount_words}”, not sent`
        : "No amount heard";

  const person =
    who.kind === "picked"
      ? [who.person.display_name, who.person.tag, HOW_LABEL[who.how]].filter(Boolean).join(" · ")
      : who.why === "who"
        ? "Kiske liye? Several are at the counter"
        : who.why === "nobody"
          ? "Nobody at the counter, and no name said"
          : who.why === "several"
            ? `${said} fits ${who.among.length} people: Kaunse?`
            : who.why === "maybe"
              ? `${said} only sounds a little like someone`
              : who.why === "not_said"
                ? `${said} was not in the words`
                : `${said} is not in your book`;

  return (
    <Card title="Heard" tight>
      <p className="text-[15px] font-extrabold tracking-[-0.015em]">“{heard.transcript}”</p>
      <p className="mt-0.5 text-[11.5px] font-semibold text-sub">
        {SOURCE_LABEL[heard.source]} · {READER_LABEL[heard.fallback ?? heard.reader]}
      </p>
      <dl className="mt-2.5 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1.5 text-[12.5px] leading-snug">
        <dt className="font-semibold text-sub">Amount</dt>
        <dd className="font-bold">{amount}</dd>
        <dt className="font-semibold text-sub">For</dt>
        <dd className="font-bold">{person}</dd>
      </dl>
      {heard.checks.length ? (
        <div className="mt-2.5 border-t border-hair pt-2">
          <p className="text-[11px] font-bold uppercase tracking-[0.04em] text-sub">Our checks</p>
          <ul className="mt-1 space-y-0.5 text-[12px] font-semibold leading-snug">
            {heard.checks.map((c) => (
              <li key={c.kind} className="flex gap-1.5">
                <span aria-hidden="true" className={c.ok ? "text-ok" : "text-warn"}>
                  {c.ok ? "✓" : "?"}
                </span>
                <span className={c.ok ? "" : "text-warn"}>
                  <span className="sr-only">{c.ok ? "Passed: " : "Did not pass: "}</span>
                  {c.says}
                </span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
      <p className="mt-2.5 text-[11px] font-medium text-sub">
        {heard.reader === "sarvam"
          ? "Sarvam-105B reads the words. The amount it quotes must be in them, and our own parser must read the same number."
          : "Our parser read the amount from the words by a fixed rule. No model decides it."}
      </p>
    </Card>
  );
}
