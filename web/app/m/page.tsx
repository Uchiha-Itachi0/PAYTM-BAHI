import { Mic } from "@/components/icons";
import { MerchantShell } from "@/components/shell/Shell";
import { Card } from "@/components/ui/Card";
import { Figure } from "@/components/ui/Figure";
import { Row } from "@/components/ui/Row";
import { StickyPill } from "@/components/ui/StickyPill";
import type { BookLine } from "@/lib/contract";
import { formatPaise } from "@/lib/money";
import { readShop } from "@/lib/shop";

/**
 * A1 · The book. What the shopkeeper opens every morning.
 *
 * Assembled only from components/ui, with no styling of its own. Every figure
 * comes from contract/shop.json, which the backend computed; this page formats
 * and places them. The list arrives alphabetical and is shown that way: never
 * sorted by who owes most.
 */

function subline(line: BookLine): string {
  const parts = [line.tag, `day ${line.day}`];
  if (line.joined === "name_only") parts.push("name only");
  return parts.filter(Boolean).join(" · ");
}

export default async function Book(): Promise<React.ReactElement> {
  const { shop, book } = await readShop();
  return (
    <MerchantShell shopName={shop.name}>
      <Card>
        <Figure
          label="Udhaar outstanding"
          value={formatPaise(book.outstanding_paise)}
          fine={`${book.owing_count} of ${book.customer_count} customers owe something`}
        />
      </Card>
      <Card title="Who owes you">
        {book.lines.map((line) => (
          <Row
            key={line.customer_id}
            name={line.display_name}
            sub={subline(line)}
            amountPaise={line.balance_paise}
            chip={line.chip}
          />
        ))}
      </Card>
      <StickyPill icon={<Mic />}>Add udhaar</StickyPill>
    </MerchantShell>
  );
}
