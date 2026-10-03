"""Entries, their acknowledgments and their payments."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from psycopg.rows import class_row

from bahi.store.db import Conn


@dataclass(frozen=True, slots=True)
class EntryRef:
    id: str
    customer_id: str
    display_name: str
    person_id: str | None
    shop_id: str
    shop_name: str
    amount_paise: int
    paid_paise: int
    status: str
    recorded_at: datetime
    note: str | None
    spoken_text: str | None
    corrects_entry_id: str | None
    acknowledged_at: datetime | None
    disputed_at: datetime | None
    #: The last payment against it, and how it was paid.
    last_paid_at: datetime | None
    last_method: str | None


SELECT = """
SELECT e.id::text AS id, c.id::text AS customer_id, c.display_name,
       c.person_id::text AS person_id, s.id::text AS shop_id, s.name AS shop_name,
       e.amount_paise,
       coalesce((SELECT sum(r.amount_paise) FROM repayments r WHERE r.entry_id = e.id),
                0)::bigint AS paid_paise,
       e.status, e.recorded_at, e.note, e.spoken_text,
       e.corrects_entry_id::text AS corrects_entry_id,
       a.acknowledged_at, e.disputed_at,
       p.paid_at AS last_paid_at, p.method AS last_method
FROM entries e
JOIN customers c ON c.id = e.customer_id
JOIN shops s ON s.id = c.shop_id
LEFT JOIN acknowledgments a ON a.entry_id = e.id
LEFT JOIN LATERAL (
    SELECT r.paid_at, r.method FROM repayments r
    WHERE r.entry_id = e.id ORDER BY r.paid_at DESC LIMIT 1
) p ON true
"""


def get(con: Conn, entry_id: str) -> EntryRef | None:
    with con.cursor(row_factory=class_row(EntryRef)) as cur:
        return cur.execute(SELECT + " WHERE e.id = %s", (entry_id,)).fetchone()


def of_customer(con: Conn, customer_id: str) -> list[EntryRef]:
    with con.cursor(row_factory=class_row(EntryRef)) as cur:
        return cur.execute(
            SELECT + " WHERE c.id = %s ORDER BY e.recorded_at", (customer_id,)
        ).fetchall()


def recent(con: Conn, shop_id: str, since: datetime) -> list[EntryRef]:
    """Entries recorded at this shop since `since`, newest first."""
    with con.cursor(row_factory=class_row(EntryRef)) as cur:
        return cur.execute(
            SELECT
            + " WHERE s.id = %s AND e.recorded_at >= %s ORDER BY e.recorded_at DESC",
            (shop_id, since),
        ).fetchall()


def record(
    con: Conn,
    customer_id: str,
    amount_paise: int,
    now: datetime,
    *,
    note: str | None = None,
    spoken_text: str | None = None,
    corrects: str | None = None,
) -> str:
    row = con.execute(
        """
        INSERT INTO entries (customer_id, amount_paise, note, spoken_text,
                             corrects_entry_id, recorded_at)
        VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING id::text
        """,
        (customer_id, amount_paise, note, spoken_text, corrects, now),
    ).fetchone()
    assert row is not None
    return str(row[0])


def set_status(con: Conn, entry_id: str, status: str) -> None:
    con.execute("UPDATE entries SET status = %s WHERE id = %s", (status, entry_id))


def dispute(con: Conn, entry_id: str, now: datetime) -> None:
    """He said it's not right, now."""
    con.execute(
        "UPDATE entries SET status = 'disputed', disputed_at = %s WHERE id = %s",
        (now, entry_id),
    )


def acknowledge(con: Conn, entry_id: str, wording: str, now: datetime) -> None:
    """His "Yes, I owe". The database refuses a second one for the same entry."""
    con.execute(
        "INSERT INTO acknowledgments (entry_id, wording, acknowledged_at) "
        "VALUES (%s, %s, %s)",
        (entry_id, wording, now),
    )


def pay(con: Conn, entry_id: str, amount_paise: int, method: str, now: datetime) -> None:
    con.execute(
        "INSERT INTO repayments (entry_id, amount_paise, method, paid_at) "
        "VALUES (%s, %s, %s, %s)",
        (entry_id, amount_paise, method, now),
    )


def by_ids(con: Conn, entry_ids: list[str]) -> dict[str, EntryRef]:
    if not entry_ids:
        return {}
    with con.cursor(row_factory=class_row(EntryRef)) as cur:
        rows = cur.execute(
            SELECT + " WHERE e.id = ANY(%s::uuid[])", (entry_ids,)
        ).fetchall()
    return {e.id: e for e in rows}


def disputed_at_shop(con: Conn, shop_id: str) -> set[str]:
    """Customers with an entry they say is wrong, still waiting for a correction."""
    rows = con.execute(
        "SELECT DISTINCT e.customer_id::text FROM entries e "
        "JOIN customers c ON c.id = e.customer_id "
        "WHERE c.shop_id = %s AND e.status = 'disputed'",
        (shop_id,),
    ).fetchall()
    return {str(r[0]) for r in rows}
