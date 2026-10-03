"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { Plus, Search } from "@/components/icons";
import { MerchantShell } from "@/components/shell/Shell";
import { Card } from "@/components/ui/Card";
import { Dots } from "@/components/ui/Notice";
import { Pill } from "@/components/ui/Pill";
import { Avatar } from "@/components/ui/Row";
import { api } from "@/lib/api/client";
import type { Customer } from "@/lib/api/types";
import { SHOP_ID } from "@/lib/config";
import { formatPaise } from "@/lib/money";

/**
 * Customers: everyone in the book, whether they owe or not, and whether they are
 * on BAHI. Someone kept by name only has no phone yet; their page is where his
 * number is added and the invite sent.
 */

type Filter = "all" | "linked" | "name_only" | "invited";

const FILTERS: [Filter, string][] = [
  ["all", "All"],
  ["linked", "On BAHI"],
  ["name_only", "Name only"],
  ["invited", "Invited"],
];

function state(c: Customer): { label: string; tone: string } {
  if (c.joined === "linked") return { label: "On BAHI", tone: "bg-ok-bg text-ok" };
  if (c.joined === "invited" || c.invite_pending)
    return { label: "Invited", tone: "bg-av-blue text-av-blue-ink" };
  return { label: "Name only", tone: "bg-quiet-bg text-quiet" };
}

function fits(c: Customer, f: Filter): boolean {
  if (f === "all") return true;
  if (f === "invited") return c.joined === "invited" || c.invite_pending;
  if (f === "name_only") return c.joined === "name_only" && !c.invite_pending;
  return c.joined === "linked";
}

export function CustomersScreen(): React.ReactElement {
  const [book, setBook] = useState<Customer[] | null>(null);
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState<Filter>("all");

  useEffect(() => {
    void api<Customer[]>(`/shops/${SHOP_ID}/customers`).then(setBook);
  }, []);

  const q = search.trim().toLowerCase();
  const shown = (book ?? [])
    .filter((c) => fits(c, filter))
    .filter(
      (c) => !q || c.display_name.toLowerCase().includes(q) || (c.tag ?? "").toLowerCase().includes(q),
    );
  const count = (f: Filter): number => (book ?? []).filter((c) => fits(c, f)).length;

  return (
    <MerchantShell heading={{ title: "Customers", sub: book ? `${book.length} in your book` : undefined, back: "/m" }}>
      <Pill href="/m/customers/new">
        <span className="inline-flex items-center gap-2 [&_svg]:size-[18px]">
          <Plus />
          Add a customer
        </span>
      </Pill>
      <Card tight>
        <label className="flex items-center gap-2 rounded-[11px] border-[1.5px] border-line bg-white px-3 py-2 focus-within:border-cyan">
          <Search className="size-[18px] text-sub" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Name, room or work"
            aria-label="Search your customers"
            className="min-w-0 flex-1 bg-transparent text-[14px] font-semibold outline-none placeholder:font-medium placeholder:text-sub"
          />
        </label>
        <div className="mt-3 flex gap-1.5 overflow-x-auto [scrollbar-width:none]">
          {FILTERS.map(([f, label]) => (
            <button
              key={f}
              type="button"
              onClick={() => setFilter(f)}
              aria-pressed={filter === f}
              className={`flex-none rounded-pill px-3 py-1.5 text-[12.5px] font-extrabold ${filter === f ? "bg-navy text-white" : "bg-tile text-sub"}`}
            >
              {label} {book ? count(f) : ""}
            </button>
          ))}
        </div>
        {!book ? (
          <div className="py-6">
            <Dots />
          </div>
        ) : shown.length ? (
          <div className="mt-2">
            {shown.map((c) => {
              const s = state(c);
              return (
                <Link
                  key={c.id}
                  href={`/m/customers/${c.id}`}
                  className="flex items-center gap-[11px] border-b border-hair py-[11px] last:border-b-0"
                >
                  <Avatar name={c.display_name} />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-[14.5px] font-bold tracking-[-0.015em]">
                      {c.display_name}
                    </p>
                    {c.tag ? (
                      <p className="mt-0.5 truncate text-[11.5px] font-medium text-sub">{c.tag}</p>
                    ) : null}
                  </div>
                  <div className="flex flex-none flex-col items-end gap-1.5">
                    {c.balance_paise ? (
                      <span className="text-[14.5px] font-extrabold tabular-nums">
                        {formatPaise(c.balance_paise)}
                      </span>
                    ) : null}
                    <span className={`rounded-md px-2 py-[3px] text-[10.5px] font-bold ${s.tone}`}>
                      {s.label}
                    </span>
                  </div>
                </Link>
              );
            })}
          </div>
        ) : (
          <p className="py-6 text-center text-[12.5px] font-medium text-sub">
            Nobody here{q ? " by that name" : ""}.
          </p>
        )}
      </Card>
    </MerchantShell>
  );
}
