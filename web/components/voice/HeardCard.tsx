import { Card } from "@/components/ui/Card";
import type { Heard } from "@/lib/api/types";
import { formatPaise } from "@/lib/money";
import { HOW_LABEL, SOURCE_LABEL, via } from "@/lib/voice";

/**
 * What was heard, and what the rules made of it, each field with where it came
 * from. The shopkeeper can see why the screen picked who it picked.
 */
export function HeardCard({ heard }: { heard: Heard }): React.ReactElement {
  const who = heard.who;
  const said = heard.name ? `“${heard.name}”` : "No name";

  const amount =
    heard.amount_paise !== null
      ? `${formatPaise(heard.amount_paise)} · ${via(heard.source)}: “${heard.amount_words}”`
      : heard.problem === "unclear_amount"
        ? `“${heard.amount_words}” is not one clear amount`
        : "No amount heard";

  const person =
    who.kind === "picked"
      ? who.how === "only_one"
        ? `${who.person.display_name} · ${HOW_LABEL.only_one}`
        : `${who.person.display_name} · ${via(heard.source)}, ${HOW_LABEL[who.how]}`
      : who.why === "who"
        ? "Kiske liye? Several are at the counter"
        : who.why === "nobody"
          ? "Nobody at the counter, and no name said"
          : who.why === "several"
            ? `${said} fits ${who.among.length} people`
            : `${said} is not at the counter or in your book`;

  return (
    <Card title="Heard" tight>
      <p className="text-[15px] font-extrabold tracking-[-0.015em]">“{heard.transcript}”</p>
      <p className="mt-0.5 text-[11.5px] font-semibold text-sub">
        {SOURCE_LABEL[heard.source]}
      </p>
      <dl className="mt-2.5 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1.5 text-[12.5px] leading-snug">
        <dt className="font-semibold text-sub">Amount</dt>
        <dd className="font-bold">{amount}</dd>
        <dt className="font-semibold text-sub">For</dt>
        <dd className="font-bold">{person}</dd>
      </dl>
      <p className="mt-2.5 text-[11px] font-medium text-sub">
        The amount is read from the words by a fixed rule. No model decides it.
      </p>
    </Card>
  );
}
