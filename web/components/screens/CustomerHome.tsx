"use client";

import { useEffect, useState } from "react";

import { Bank, Book, Mobile, Scan } from "@/components/icons";
import { CustomerShell } from "@/components/shell/Shell";
import { Card } from "@/components/ui/Card";
import { Row } from "@/components/ui/Row";
import { StickyPill } from "@/components/ui/StickyPill";
import { TileGrid } from "@/components/ui/TileGrid";
import { api, usePoll } from "@/lib/api/client";
import type { DemoPhone, MyUdhaar } from "@/lib/api/types";
import { forgetPerson, usePerson, becomePerson } from "@/lib/person";

/**
 * The customer's side: the Paytm app home, with one new tile.
 *
 * Nobody downloads anything. Udhaar sits beside Scan & Pay and To Mobile in the
 * app already on his phone, which is the whole answer to cold start.
 *
 * In Paytm the phone knows whose it is. In the demo it doesn't, so this screen
 * asks: be one of the seeded customers (Sharma owes three shops), or someone
 * invited who hasn't said yes yet.
 */
export function CustomerHome(): React.ReactElement {
  const person = usePerson();
  const [phones, setPhones] = useState<DemoPhone[]>([]);
  const mine = usePoll<MyUdhaar>(person ? `/people/${person.id}/udhaar` : null, 4000);
  const waiting =
    (mine.data?.invites.length ?? 0) + (mine.data?.shops.reduce((n, s) => n + s.unread, 0) ?? 0);

  useEffect(() => {
    void api<DemoPhone[]>("/demo/phones").then(setPhones);
  }, []);

  return (
    <CustomerShell>
      <Card title="Money Transfer">
        <TileGrid
          tiles={[
            { label: "Scan & Pay", icon: <Scan /> },
            { label: "To Mobile", icon: <Mobile /> },
            { label: "To Bank", icon: <Bank /> },
            { label: "Udhaar", icon: <Book />, href: "/c/udhaar", badge: waiting || undefined },
          ]}
        />
      </Card>

      <Card title="Demo · whose phone is this?" tight>
        {person ? (
          <div className="flex items-center justify-between gap-3">
            <p className="text-[13.5px] font-semibold">
              This phone is <b className="font-extrabold">{person.name}</b>&apos;s.
            </p>
            <button
              type="button"
              onClick={forgetPerson}
              className="text-[12.5px] font-extrabold text-cyan-text"
            >
              Change
            </button>
          </div>
        ) : (
          <>
            <p className="mb-1 text-[12px] font-medium leading-normal text-sub">
              In Paytm this is your account. Pick someone from the demo, or scan a shop&apos;s
              udhaar QR as someone new.
            </p>
            {phones.map((p) => (
              <Row
                key={p.person_id}
                name={p.name}
                onSelect={() => becomePerson({ id: p.person_id, name: p.name })}
              />
            ))}
          </>
        )}
      </Card>
      <StickyPill icon={<Scan />}>Scan QR</StickyPill>
    </CustomerShell>
  );
}
