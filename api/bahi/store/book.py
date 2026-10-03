"""Loads one shop's book from Postgres into domain objects.

SQL in, frozen dataclasses out, no decisions. Rows are read by column name, never
by position. Every date is taken in IST: a payment at 11:30 pm in Kurla belongs to
that day, not to the next UTC day, and a gap measured in the wrong timezone is a
gap the customer never had.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import Any

import psycopg
from psycopg.rows import dict_row

from bahi.domain.book import Customer, Entry, Joined

Conn = psycopg.Connection[Any]

CUSTOMERS = """
SELECT id::text                AS id,
       display_name,
       tag,
       person_id IS NOT NULL   AS has_person,
       linked_at IS NOT NULL   AS has_linked
FROM customers
WHERE shop_id = %(shop)s
"""

ENTRIES = """
SELECT e.id::text                                              AS id,
       e.customer_id::text                                     AS customer_id,
       e.amount_paise,
       coalesce(sum(r.amount_paise), 0)::bigint                AS paid_paise,
       e.status,
       (e.recorded_at AT TIME ZONE 'Asia/Kolkata')::date       AS recorded_on,
       (a.acknowledged_at AT TIME ZONE 'Asia/Kolkata')::date   AS acknowledged_on
FROM entries e
JOIN customers c ON c.id = e.customer_id
LEFT JOIN acknowledgments a ON a.entry_id = e.id
LEFT JOIN repayments r ON r.entry_id = e.id
WHERE c.shop_id = %(shop)s
GROUP BY e.id, a.acknowledged_at
ORDER BY e.recorded_at
"""

PAID_ON = """
SELECT DISTINCT e.customer_id::text                        AS customer_id,
       (r.paid_at AT TIME ZONE 'Asia/Kolkata')::date       AS paid_on
FROM repayments r
JOIN entries e ON e.id = r.entry_id
JOIN customers c ON c.id = e.customer_id
WHERE c.shop_id = %(shop)s
"""


def joined(has_person: bool, has_linked: bool) -> Joined:
    if not has_person:
        return "name_only"
    return "linked" if has_linked else "invited"


def load(con: Conn, shop_id: str) -> list[Customer]:
    args = {"shop": shop_id}
    entries: dict[str, list[Entry]] = defaultdict(list)
    paid_on: dict[str, list[date]] = defaultdict(list)

    with con.cursor(row_factory=dict_row) as cur:
        for r in cur.execute(ENTRIES, args):
            entries[r["customer_id"]].append(
                Entry(
                    id=r["id"],
                    amount_paise=r["amount_paise"],
                    paid_paise=r["paid_paise"],
                    status=r["status"],
                    recorded_on=r["recorded_on"],
                    acknowledged_on=r["acknowledged_on"],
                )
            )

        for r in cur.execute(PAID_ON, args):
            paid_on[r["customer_id"]].append(r["paid_on"])

        return [
            Customer(
                id=r["id"],
                display_name=r["display_name"],
                tag=r["tag"],
                joined=joined(r["has_person"], r["has_linked"]),
                entries=tuple(entries[r["id"]]),
                paid_on=tuple(sorted(paid_on[r["id"]])),
            )
            for r in cur.execute(CUSTOMERS, args).fetchall()
        ]
