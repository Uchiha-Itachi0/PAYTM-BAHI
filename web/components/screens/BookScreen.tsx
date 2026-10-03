"use client";

import { Mic, Scan } from "@/components/icons";
import { MerchantShell } from "@/components/shell/Shell";
import { Card } from "@/components/ui/Card";
import { Figure } from "@/components/ui/Figure";
import { Dots, Notice } from "@/components/ui/Notice";
import { Row } from "@/components/ui/Row";
import { StickyPill } from "@/components/ui/StickyPill";
import { TileGrid } from "@/components/ui/TileGrid";
import { usePoll } from "@/lib/api/client";
import type { BookLine, ShopBook } from "@/lib/api/types";
import { SHOP_ID } from "@/lib/config";
import { parseShop } from "@/lib/contract";
import { formatPaise } from "@/lib/money";

/**
 * A1 · The book. What the shopkeeper opens every morning, live.
 *
 * Polls the API every two seconds, so a confirmation made on a customer's phone
 * shows here within one tick. Every figure was computed by the backend; this
 * screen formats and places them. The list arrives alphabetical and stays that
 * way: never sorted by who owes most.
 */

function subline(line: BookLine): string {
  const parts = [line.tag, `day ${line.day}`];
  if (line.joined === "name_only") parts.push("name only");
  return parts.filter(Boolean).join(" · ");
}

export function BookScreen(): React.ReactElement {
  const { data, error } = usePoll<ShopBook>(`/shops/${SHOP_ID}/book`);
  const shop = data ? parseShop(data) : undefined;

  return (
    <MerchantShell shopName={shop?.shop.name}>
      {shop ? (
        <>
          <Card>
            <Figure
              label="Udhaar outstanding"
              value={formatPaise(shop.book.outstanding_paise)}
              fine={`${shop.book.owing_count} of ${shop.book.customer_count} customers owe something`}
            />
          </Card>
          <Card>
            <TileGrid
              tiles={[
                { label: "Add udhaar", icon: <Mic />, href: "/m/add?listen=1" },
                { label: "Udhaar QR", icon: <Scan />, href: "/m/qr" },
              ]}
            />
          </Card>
          <Card title="Who owes you">
            {shop.book.lines.map((line) => (
              <Row
                key={line.customer_id}
                name={line.display_name}
                sub={subline(line)}
                amountPaise={line.balance_paise}
                chip={line.chip}
              />
            ))}
          </Card>
        </>
      ) : error ? (
        <Notice tone="warn">Cannot reach the book right now: {error}</Notice>
      ) : (
        <Card>
          <Dots />
        </Card>
      )}
      <StickyPill icon={<Mic />} href="/m/add?listen=1">
        Add udhaar
      </StickyPill>
    </MerchantShell>
  );
}
