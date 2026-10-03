"use client";

import { useEffect, useState } from "react";

import { Bank, Book, Mobile, Scan } from "@/components/icons";
import { CustomerShell } from "@/components/shell/Shell";
import { Card } from "@/components/ui/Card";
import { Field } from "@/components/ui/Field";
import { Row } from "@/components/ui/Row";
import { StickyPill } from "@/components/ui/StickyPill";
import { TileGrid } from "@/components/ui/TileGrid";
import { api, usePoll } from "@/lib/api/client";
import type { DemoPhone, MyUdhaar, PaytmAccount } from "@/lib/api/types";
import { forgetPerson, usePerson, becomePerson } from "@/lib/person";

/**
 * The customer's side: the Paytm app home, with one new tile.
 *
 * Nobody downloads anything. Udhaar sits beside Scan & Pay and To Mobile in the
 * app already on his phone, which is the whole answer to cold start.
 *
 * In Paytm the phone knows whose it is. In the demo it doesn't, so this screen
 * asks: be any customer with a phone in the book (Sharma owes three shops),
 * someone invited who hasn't said yes yet, or someone on Paytm in no book at all.
 * Someone kept by name only has no phone, so isn't listed.
 */

function about(p: DemoPhone): string {
  if (p.state === "paytm") return "On Paytm · in no shop's book yet";
  if (p.state === "invited") return "Invited · hasn't said yes yet";
  const shops = p.shops > 1 ? `in ${p.shops} shops' books` : "";
  return [p.tag, shops].filter(Boolean).join(" · ");
}
/**
 * His Paytm account, as Paytm shows it: the name on it, its UPI ID and its
 * number. Fixed. Shops see the name and UPI ID, never the number.
 */
function Account({ account }: { account: PaytmAccount }): React.ReactElement {
  return (
    <div className="mt-3 rounded-[12px] bg-tile px-3 py-2.5">
      <p className="text-[14px] font-extrabold">{account.name}</p>
      <p className="text-[12.5px] font-semibold text-sub">
        {account.upi} · +91 {account.phone.slice(0, 5)} {account.phone.slice(5)}
      </p>
    </div>
  );
}

export function CustomerHome(): React.ReactElement {
  const person = usePerson();
  const [phones, setPhones] = useState<DemoPhone[]>([]);
  const [search, setSearch] = useState("");
  const q = search.trim().toLowerCase();
  const shown = phones.filter(
    (p) => !q || p.name.toLowerCase().includes(q) || (p.tag ?? "").toLowerCase().includes(q),
  );
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
        ) : null}
        {person && mine.data?.account ? (
          <Account account={mine.data.account} />
        ) : null}
        {person ? null : (
          <>
            <p className="mb-3 text-[12px] font-medium leading-normal text-sub">
              In Paytm this is your account. Pick any of the {phones.length} customers with a
              phone, or scan a shop&apos;s udhaar QR as someone new.
            </p>
            <Field
              label="Find a customer"
              value={search}
              onChange={setSearch}
              placeholder="Name, room or work"
              inputMode="search"
            />
            <div className="mt-2">
              {shown.map((p) => (
                <Row
                  key={p.person_id}
                  name={p.name}
                  sub={about(p)}
                  onSelect={() => becomePerson({ id: p.person_id, name: p.name })}
                />
              ))}
              {q && !shown.length ? (
                <p className="py-3 text-[12.5px] font-medium text-sub">Nobody by that name.</p>
              ) : null}
            </div>
          </>
        )}
      </Card>
      <StickyPill icon={<Scan />}>Scan QR</StickyPill>
    </CustomerShell>
  );
}
