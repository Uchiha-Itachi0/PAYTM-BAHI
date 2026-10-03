"use client";

import Link from "next/link";

import { Chat, Mic, Moon, Person, Plus, Scan, Spark } from "@/components/icons";
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
import { warmMic } from "@/lib/useRecorder";

/**
 * A1 · The book. What the shopkeeper opens every morning, live.
 *
 * Polls the API every two seconds, so a confirmation made on a customer's phone
 * shows here within one tick. Every figure was computed by the backend; this
 * screen formats and places them. The list arrives alphabetical and stays that
 * way: never sorted by who owes most. Each row opens that customer's thread, or
 * for someone not on BAHI, their page, where their phone can be added.
 */

function subline(line: BookLine): string {
  const parts = [line.tag, `day ${line.day}`];
  if (line.joined === "name_only") parts.push("name only");
  // What isn't agreed yet is named, not added: the amount shown is what they
  // said yes to, or, owing nothing agreed, what waits on them.
  const waiting = line.waiting_paise ?? 0;
  const disputed = line.disputed_paise ?? 0;
  if (line.balance_paise > 0 && waiting > 0) parts.push(`+${formatPaise(waiting)} waiting`);
  if (line.balance_paise === 0 && waiting > 0) parts.push("waiting for their yes");
  if (disputed > 0) parts.push(`says ${formatPaise(disputed)} is wrong`);
  return parts.filter(Boolean).join(" · ");
}

/** The amount on his row: agreed; with nothing agreed, what waits on them. */
function shown(line: BookLine): number {
  if (line.balance_paise > 0) return line.balance_paise;
  return (line.waiting_paise ?? 0) + (line.disputed_paise ?? 0);
}

function apart(waiting: number, disputed: number): string | null {
  const parts = [
    waiting > 0 ? `${formatPaise(waiting)} waiting for customers' yes` : null,
    disputed > 0 ? `${formatPaise(disputed)} customers say is wrong` : null,
  ].filter(Boolean);
  return parts.length ? `Not counted: ${parts.join(" · ")}` : null;
}

export function BookScreen(): React.ReactElement {
  const { data, error } = usePoll<ShopBook>(`/shops/${SHOP_ID}/book`);
  const inbox = usePoll<Inbox>(`/shops/${SHOP_ID}/inbox`);
  const shop = data ? parseShop(data) : undefined;

  return (
    <MerchantShell shopName={shop?.shop.name} fixed>
      {shop ? (
        <>
          <Card>
            <Figure
              label="Udhaar outstanding · agreed"
              value={formatPaise(shop.book.outstanding_paise)}
              fine={`${shop.book.owing_count} of ${shop.book.customer_count} customers owe something they said yes to`}
            />
            {apart(shop.book.waiting_paise ?? 0, shop.book.disputed_paise ?? 0) ? (
              <p className="mt-1 text-[12px] font-semibold leading-[1.45] text-sub">
                {apart(shop.book.waiting_paise ?? 0, shop.book.disputed_paise ?? 0)}
              </p>
            ) : null}
          </Card>
          <Card>
            <TileGrid
              tiles={[
                { label: "Add udhaar", icon: <Mic />, href: "/m/add?listen=1", onTap: warmMic },
                { label: "Udhaar QR", icon: <Scan />, href: "/m/qr" },
                {
                  label: "Messages",
                  icon: <Chat />,
                  href: "/m/messages",
                  badge: inbox.data?.unread,
                },
                { label: "Tomorrow", icon: <Moon />, href: "/m/tonight" },
                { label: "Customers", icon: <Person />, href: "/m/customers" },
                { label: "Add customer", icon: <Plus />, href: "/m/customers/new" },
                { label: "Assistant", icon: <Spark />, href: "/m/assistant" },
              ]}
            />
          </Card>
          <Card title="Who owes you" fill>
            {shop.book.lines.map((line) => (
              <Row
                key={line.customer_id}
                name={line.display_name}
                sub={subline(line)}
                amountPaise={shown(line)}
                chip={line.chip}
                href={
                  line.joined === "linked"
                    ? `/m/chat/${line.customer_id}`
                    : `/m/customers/${line.customer_id}`
                }
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
      <StickyPill icon={<Mic />} href="/m/add?listen=1" floating onTap={warmMic}>
        Add udhaar
      </StickyPill>
    </MerchantShell>
  );
}
