"""What BAHI remembers about a customer, and what memory still has to do.

The record (migration 008): what the screen lists, what Tonight reads, what
Forget removes. Cognee's searchable copy is made from it later (bahi.memory),
so saving here never waits on Cognee, and Tonight works without it.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal

from psycopg.rows import class_row

from bahi.store.db import Conn

Kind = Literal["note", "promise", "nickname", "said"]
SaidBy = Literal["shop", "customer"]


@dataclass(frozen=True, slots=True)
class Memory:
    id: str
    shop_id: str
    customer_id: str
    display_name: str
    name_hi: str | None
    tag: str | None
    kind: str
    body: str
    said_by: str
    until: date | None
    message_id: str | None
    remembered_at: datetime
    forgotten_at: datetime | None
    stored_at: datetime | None
    cognee_id: str | None


SELECT = """
SELECT m.id::text AS id, m.shop_id::text AS shop_id,
       m.customer_id::text AS customer_id, c.display_name, c.name_hi, c.tag,
       m.kind, m.body, m.said_by, m.until, m.message_id::text AS message_id,
       m.remembered_at, m.forgotten_at, m.stored_at, m.cognee_id::text AS cognee_id
FROM memories m JOIN customers c ON c.id = m.customer_id
"""


def add(
    con: Conn,
    shop_id: str,
    customer_id: str,
    kind: Kind,
    body: str,
    said_by: SaidBy,
    now: datetime,
    *,
    until: date | None = None,
    message_id: str | None = None,
) -> Memory | None:
    """Keeps it, only for a customer of this shop (None otherwise). A chat
    message gives at most one of each kind: read again, it is the same memory."""
    row = con.execute(
        """
        INSERT INTO memories (shop_id, customer_id, kind, body, said_by, until,
                              message_id, remembered_at)
        SELECT c.shop_id, c.id, %s, %s, %s, %s, %s, %s
        FROM customers c WHERE c.id = %s AND c.shop_id = %s
        ON CONFLICT (message_id, kind) WHERE message_id IS NOT NULL DO NOTHING
        RETURNING id::text
        """,
        (kind, body.strip(), said_by, until, message_id, now, customer_id, shop_id),
    ).fetchone()
    return get(con, str(row[0]), shop_id) if row else None


def get(con: Conn, memory_id: str, shop_id: str) -> Memory | None:
    with con.cursor(row_factory=class_row(Memory)) as cur:
        return cur.execute(
            SELECT + " WHERE m.id = %s AND m.shop_id = %s", (memory_id, shop_id)
        ).fetchone()


def of_customer(con: Conn, customer_id: str) -> list[Memory]:
    """Everything remembered about him and not forgotten, newest first."""
    with con.cursor(row_factory=class_row(Memory)) as cur:
        return cur.execute(
            SELECT + " WHERE m.customer_id = %s AND m.forgotten_at IS NULL"
            " ORDER BY m.remembered_at DESC, m.id",
            (customer_id,),
        ).fetchall()


def of_shop(con: Conn, shop_id: str, kind: Kind | None = None) -> list[Memory]:
    with con.cursor(row_factory=class_row(Memory)) as cur:
        return cur.execute(
            SELECT + " WHERE m.shop_id = %s AND m.forgotten_at IS NULL"
            " AND (%s::text IS NULL OR m.kind = %s)"
            " ORDER BY m.remembered_at DESC, m.id",
            (shop_id, kind, kind),
        ).fetchall()


def waits(con: Conn, shop_id: str, day: date) -> dict[str, Memory]:
    """Who BAHI stays quiet for on `day`, by customer: a note or promise whose
    `until` is `day` or later. The one that waits longest, if several."""
    with con.cursor(row_factory=class_row(Memory)) as cur:
        rows = cur.execute(
            SELECT + " WHERE m.shop_id = %s AND m.forgotten_at IS NULL"
            " AND m.until >= %s ORDER BY m.until, m.remembered_at",
            (shop_id, day),
        ).fetchall()
    return {m.customer_id: m for m in rows}


def forget(con: Conn, memory_id: str, shop_id: str, now: datetime) -> Memory | None:
    """Forgotten at once here, so the screen and Tonight drop it; Cognee's copy
    is removed after (`to_unstore`)."""
    row = con.execute(
        "UPDATE memories SET forgotten_at = %s"
        " WHERE id = %s AND shop_id = %s AND forgotten_at IS NULL RETURNING id",
        (now, memory_id, shop_id),
    ).fetchone()
    return get(con, memory_id, shop_id) if row else None


# ── what the memory worker does next ─────────────────────────────────────────


def to_store(con: Conn, limit: int = 10) -> list[Memory]:
    """Remembered, not yet in Cognee. Locked, so two workers never both store it."""
    with con.cursor(row_factory=class_row(Memory)) as cur:
        return cur.execute(
            SELECT + " WHERE m.stored_at IS NULL AND m.forgotten_at IS NULL"
            " ORDER BY m.remembered_at LIMIT %s FOR UPDATE OF m SKIP LOCKED",
            (limit,),
        ).fetchall()


def stored(con: Conn, memory_id: str, cognee_id: str | None, now: datetime) -> None:
    con.execute(
        "UPDATE memories SET stored_at = %s, cognee_id = %s WHERE id = %s",
        (now, cognee_id, memory_id),
    )


def to_unstore(con: Conn, limit: int = 10) -> list[Memory]:
    """Forgotten, but Cognee still has its copy."""
    with con.cursor(row_factory=class_row(Memory)) as cur:
        return cur.execute(
            SELECT + " WHERE m.forgotten_at IS NOT NULL AND m.cognee_id IS NOT NULL"
            " ORDER BY m.forgotten_at LIMIT %s FOR UPDATE OF m SKIP LOCKED",
            (limit,),
        ).fetchall()


def unstored(con: Conn, memory_id: str) -> None:
    con.execute("UPDATE memories SET cognee_id = NULL WHERE id = %s", (memory_id,))


@dataclass(frozen=True, slots=True)
class Unread:
    """A customer's chat message memory hasn't read yet."""

    message_id: str
    shop_id: str
    customer_id: str
    display_name: str
    body: str
    sent_at: datetime


def unread(con: Conn, limit: int = 10) -> list[Unread]:
    with con.cursor(row_factory=class_row(Unread)) as cur:
        return cur.execute(
            """
            SELECT m.id::text AS message_id, c.shop_id::text AS shop_id,
                   c.id::text AS customer_id, c.display_name, m.body, m.sent_at
            FROM messages m
            JOIN threads t ON t.id = m.thread_id
            JOIN customers c ON c.id = t.customer_id
            WHERE m.read_for_memory_at IS NULL AND m.author = 'customer'
            ORDER BY m.sent_at LIMIT %s FOR UPDATE OF m SKIP LOCKED
            """,
            (limit,),
        ).fetchall()


def read(con: Conn, message_id: str, now: datetime) -> None:
    con.execute(
        "UPDATE messages SET read_for_memory_at = %s WHERE id = %s", (now, message_id)
    )
