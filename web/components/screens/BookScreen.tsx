"use client";

import Link from "next/link";

import { Chat, Mic, Moon, Plus, Scan } from "@/components/icons";
import { MerchantShell } from "@/components/shell/Shell";
import { Card } from "@/components/ui/Card";
import { Figure } from "@/components/ui/Figure";
import { Dots, Notice } from "@/components/ui/Notice";
import { Row } from "@/components/ui/Row";
import { StickyPill } from "@/components/ui/StickyPill";
import { TileGrid } from "@/components/ui/TileGrid";
import { usePoll } from "@/lib/api/client";
import type { BookLine, Inbox, ShopBook } from "@/lib/api/types";
import { SHOP_ID } from "@/lib/config";
import { parseShop } from "@/lib/contract";
import { formatPaise } from "@/lib/money";

/**
 * A1 · The book. What the shopkeeper opens every morning, live.
 *
 * Polls the API every two seconds, so a confirmation made on a customer's phone
 * shows here within one tick. Every figure was computed by the backend; this
 * screen formats and places them. The list arrives alphabetical and stays that
 * way: never sorted by who owes most. Each row opens that customer's thread.
 */

function subline(line: BookLine): string {
  const parts = [line.tag, `day ${line.day}`];
  if (line.joined === "name_only") parts.push("name only");
  return parts.filter(Boolean).join(" · ");
}

export function BookScreen(): React.ReactElement {
  const { data, error } = usePoll<ShopBook>(`/shops/${SHOP_ID}/book`);
  const inbox = usePoll<Inbox>(`/shops/${SHOP_ID}/inbox`);
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
                {
                  label: "Messages",
                  icon: <Chat />,
                  href: "/m/messages",
                  badge: inbox.data?.unread,
                },
                { label: "Tomorrow", icon: <Moon />, href: "/m/tonight" },
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
                href={`/m/chat/${line.customer_id}`}
              />
            ))}
            <Link
              href="/m/customers/new"
              className="mt-2.5 flex items-center justify-center gap-1.5 border-t border-hair pt-3 text-[13.5px] font-extrabold text-cyan-text [&_svg]:size-4"
            >
              <Plus />
              Add a customer who can&apos;t scan
            </Link>
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
