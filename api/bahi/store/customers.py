"""Customers: a person at one shop, linked, invited, or kept by name only."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from psycopg.rows import class_row

from bahi.domain.book import Joined
from bahi.store.db import Conn


@dataclass(frozen=True, slots=True)
class CustomerRef:
    id: str
    shop_id: str
    person_id: str | None
    display_name: str
    tag: str | None
    linked: bool
    #: The name in Devanagari, from Sarvam's transliterate. None if voice was off.
    name_hi: str | None
    #: The tag in Devanagari, likewise.
    tag_hi: str | None

    @property
    def joined(self) -> Joined:
        if self.person_id is None:
            return "name_only"
        return "linked" if self.linked else "invited"


SELECT = """
SELECT id::text AS id, shop_id::text AS shop_id, person_id::text AS person_id,
       display_name, tag, linked_at IS NOT NULL AS linked, name_hi, tag_hi
FROM customers
"""


def get(con: Conn, customer_id: str) -> CustomerRef | None:
    with con.cursor(row_factory=class_row(CustomerRef)) as cur:
        return cur.execute(SELECT + " WHERE id = %s", (customer_id,)).fetchone()


def at_shop(con: Conn, shop_id: str, person_id: str) -> CustomerRef | None:
    """This person's row at this shop, if he has one."""
    with con.cursor(row_factory=class_row(CustomerRef)) as cur:
        return cur.execute(
            SELECT + " WHERE shop_id = %s AND person_id = %s", (shop_id, person_id)
        ).fetchone()


def of_person(con: Conn, person_id: str) -> list[CustomerRef]:
    """Every shop's row for one person. Only ever shown to that person."""
    with con.cursor(row_factory=class_row(CustomerRef)) as cur:
        return cur.execute(
            SELECT + " WHERE person_id = %s ORDER BY added_at", (person_id,)
        ).fetchall()


def of_shop(con: Conn, shop_id: str) -> list[CustomerRef]:
    with con.cursor(row_factory=class_row(CustomerRef)) as cur:
        return cur.execute(
            SELECT + " WHERE shop_id = %s ORDER BY lower(display_name)", (shop_id,)
        ).fetchall()


def add(
    con: Conn,
    shop_id: str,
    display_name: str,
    now: datetime,
    *,
    person_id: str | None = None,
    tag: str | None = None,
    linked: bool = False,
    name_hi: str | None = None,
    tag_hi: str | None = None,
) -> str:
    """A new customer. Linked (he scanned), invited (a person, not yet linked),
    or name only (no person at all)."""
    row = con.execute(
        """
        INSERT INTO customers (shop_id, person_id, display_name, tag, added_at,
                               linked_at, name_hi, tag_hi)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id::text
        """,
        (
            shop_id,
            person_id,
            display_name,
            tag,
            now,
            now if linked else None,
            name_hi,
            tag_hi,
        ),
    ).fetchone()
    assert row is not None
    return str(row[0])


def link(con: Conn, customer_id: str, now: datetime) -> None:
    """He accepted an invite, or scanned the shop's QR. Either way, he said yes."""
    con.execute(
        "UPDATE customers SET linked_at = %s WHERE id = %s AND linked_at IS NULL",
        (now, customer_id),
    )


def drop_invite(con: Conn, customer_id: str) -> bool:
    """He said no to an invite: the shop's row for him goes. Only an invite that
    was never accepted, so nothing was ever recorded against it."""
    row = con.execute(
        "DELETE FROM customers WHERE id = %s AND person_id IS NOT NULL "
        "AND linked_at IS NULL RETURNING id",
        (customer_id,),
    ).fetchone()
    return row is not None


def added_at(con: Conn, customer_id: str) -> datetime:
    row = con.execute(
        "SELECT added_at FROM customers WHERE id = %s", (customer_id,)
    ).fetchone()
    assert row is not None
    return row[0]  # type: ignore[no-any-return]


@dataclass(frozen=True, slots=True)
class Phone:
    """A person on Paytm who is in some shop's book: linked, or invited."""

    person_id: str
    #: What the first shop to add him calls him, and how it describes him.
    display_name: str
    tag: str | None
    linked: bool
    shops: int


def phones(con: Conn) -> list[Phone]:
    """Everyone with a Paytm account in any shop's book, once each. Only for the
    demo's "whose phone is this?": in Paytm the phone already knows."""
    with con.cursor(row_factory=class_row(Phone)) as cur:
        return cur.execute(
            """
            SELECT DISTINCT ON (person_id)
                   person_id::text AS person_id, display_name, tag,
                   bool_or(linked_at IS NOT NULL) OVER (PARTITION BY person_id) AS linked,
                   count(*) OVER (PARTITION BY person_id)::int AS shops
            FROM customers
            WHERE person_id IS NOT NULL
            ORDER BY person_id, added_at
            """
        ).fetchall()
