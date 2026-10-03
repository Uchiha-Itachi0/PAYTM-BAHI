"""Loads one shop's book from Postgres into domain objects.

SQL in, frozen dataclasses out, no decisions. Every date is taken in IST: a
payment at 11:30 pm in Kurla belongs to that day, not to the next UTC day, and a
gap measured in the wrong timezone is a gap the customer never had.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import Any

import psycopg

from bahi.domain.book import Customer, Entry, Joined

Conn = psycopg.Connection[Any]

CUSTOMERS = """
SELECT id::text, display_name, tag, person_id IS NOT NULL, linked_at IS NOT NULL
FROM customers
WHERE shop_id = %(shop)s
"""

ENTRIES = """
SELECT e.id::text,
       e.customer_id::text,
       e.amount_paise,
       coalesce(sum(r.amount_paise), 0)::bigint AS paid_paise,
       e.status,
       (e.recorded_at AT TIME ZONE 'Asia/Kolkata')::date,
       (a.acknowledged_at AT TIME ZONE 'Asia/Kolkata')::date
FROM entries e
JOIN customers c ON c.id = e.customer_id
LEFT JOIN acknowledgments a ON a.entry_id = e.id
LEFT JOIN repayments r ON r.entry_id = e.id
WHERE c.shop_id = %(shop)s
GROUP BY e.id, a.acknowledged_at
ORDER BY e.recorded_at
"""

PAID_ON = """
SELECT DISTINCT e.customer_id::text, (r.paid_at AT TIME ZONE 'Asia/Kolkata')::date
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

    with con.cursor() as cur:
        cur.execute(ENTRIES, args)
        for eid, cid, amount, paid, status, recorded_on, acked_on in cur.fetchall():
            entries[cid].append(Entry(eid, amount, paid, status, recorded_on, acked_on))

        cur.execute(PAID_ON, args)
        for cid, day in cur.fetchall():
            paid_on[cid].append(day)

        cur.execute(CUSTOMERS, args)
        return [
            Customer(
                id=cid,
                display_name=name,
                tag=tag,
                joined=joined(has_person, has_linked),
                entries=tuple(entries[cid]),
                paid_on=tuple(sorted(paid_on[cid])),
            )
            for cid, name, tag, has_person, has_linked in cur.fetchall()
        ]
