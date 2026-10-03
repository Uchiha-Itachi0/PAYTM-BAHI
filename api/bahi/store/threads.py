"""Threads and messages: one conversation per shop and customer.

A thread is made the first time something is said in it, so a customer the shop
has never written to has none. People post text; BAHI posts the entry cards and
the reminders (the table refuses anything else).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from psycopg.rows import class_row

from bahi.store.db import Conn

Author = Literal["shop", "customer", "bahi"]
Kind = Literal["text", "entry", "reminder"]
Side = Literal["shop", "customer"]


@dataclass(frozen=True, slots=True)
class Message:
    id: str
    thread_id: str
    author: str
    kind: str
    body: str
    entry_id: str | None
    sent_at: datetime


@dataclass(frozen=True, slots=True)
class Thread:
    id: str
    customer_id: str
    shop_read_at: datetime | None
    customer_read_at: datetime | None


@dataclass(frozen=True, slots=True)
class Last:
    """A thread as a list shows it: who, the last message, and what is unread."""

    thread_id: str
    customer_id: str
    shop_id: str
    display_name: str
    tag: str | None
    message_id: str
    author: str
    kind: str
    body: str
    entry_id: str | None
    sent_at: datetime
    #: Messages the other side wrote since this side last looked.
    unread: int


MESSAGE = (
    "id::text AS id, thread_id::text AS thread_id, author, kind, body, "
    "entry_id::text AS entry_id, sent_at"
)
THREAD = (
    "id::text AS id, customer_id::text AS customer_id, shop_read_at, customer_read_at"
)


def of_customer(con: Conn, customer_id: str) -> Thread | None:
    with con.cursor(row_factory=class_row(Thread)) as cur:
        return cur.execute(
            f"SELECT {THREAD} FROM threads WHERE customer_id = %s", (customer_id,)
        ).fetchone()


def open_for(con: Conn, customer_id: str, now: datetime) -> Thread:
    """His thread with the shop, made if there isn't one yet."""
    con.execute(
        "INSERT INTO threads (customer_id, created_at) VALUES (%s, %s) "
        "ON CONFLICT (customer_id) DO NOTHING",
        (customer_id, now),
    )
    t = of_customer(con, customer_id)
    assert t is not None
    return t


def post(
    con: Conn,
    customer_id: str,
    author: Author,
    kind: Kind,
    body: str,
    now: datetime,
    *,
    entry_id: str | None = None,
) -> Message:
    """One message in his thread. Whoever posts has read the thread up to it."""
    t = open_for(con, customer_id, now)
    with con.cursor(row_factory=class_row(Message)) as cur:
        row = cur.execute(
            f"""
            INSERT INTO messages (thread_id, author, kind, body, entry_id, sent_at)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING {MESSAGE}
            """,
            (t.id, author, kind, body, entry_id, now),
        ).fetchone()
    assert row is not None
    if author in ("shop", "customer"):
        read(con, t.id, author, now)
    return row


def messages(con: Conn, thread_id: str) -> list[Message]:
    with con.cursor(row_factory=class_row(Message)) as cur:
        return cur.execute(
            f"SELECT {MESSAGE} FROM messages WHERE thread_id = %s ORDER BY sent_at, id",
            (thread_id,),
        ).fetchall()


def read(con: Conn, thread_id: str, side: Side, now: datetime) -> None:
    """This side has seen everything in the thread up to now."""
    column = "shop_read_at" if side == "shop" else "customer_read_at"
    con.execute(
        f"UPDATE threads SET {column} = greatest(coalesce({column}, %s), %s) "
        "WHERE id = %s",
        (now, now, thread_id),
    )


def read_all(con: Conn, shop_id: str, now: datetime) -> None:
    """The shopkeeper's Mark all read."""
    con.execute(
        """
        UPDATE threads t SET shop_read_at = %s
        FROM customers c
        WHERE c.id = t.customer_id AND c.shop_id = %s
          AND (t.shop_read_at IS NULL OR t.shop_read_at < %s)
        """,
        (now, shop_id, now),
    )


LAST = """
SELECT t.id::text AS thread_id, c.id::text AS customer_id, c.shop_id::text AS shop_id,
       c.display_name, c.tag, m.id::text AS message_id,
       m.author, m.kind, m.body, m.entry_id::text AS entry_id, m.sent_at,
       (SELECT count(*) FROM messages u
        WHERE u.thread_id = t.id AND u.author = ANY(%(other)s)
          AND (t.{read} IS NULL OR u.sent_at > t.{read}))::int AS unread
FROM threads t
JOIN customers c ON c.id = t.customer_id
JOIN LATERAL (
    SELECT * FROM messages WHERE thread_id = t.id ORDER BY sent_at DESC, id DESC LIMIT 1
) m ON true
"""


def of_shop(con: Conn, shop_id: str) -> list[Last]:
    """The shop's inbox: every thread, the latest first."""
    sql = LAST.format(read="shop_read_at") + " WHERE c.shop_id = %(key)s"
    with con.cursor(row_factory=class_row(Last)) as cur:
        return cur.execute(
            sql + " ORDER BY m.sent_at DESC", {"other": ["customer"], "key": shop_id}
        ).fetchall()


def of_person(con: Conn, person_id: str) -> list[Last]:
    """His threads with every shop he is in the book of."""
    sql = LAST.format(read="customer_read_at") + " WHERE c.person_id = %(key)s"
    with con.cursor(row_factory=class_row(Last)) as cur:
        return cur.execute(
            sql + " ORDER BY m.sent_at DESC",
            # to him, the shop's words and BAHI's cards and reminders are all news
            {"other": ["shop", "bahi"], "key": person_id},
        ).fetchall()


def cards(con: Conn, entry_ids: list[str]) -> dict[str, str]:
    """Each entry's first message: its card. Later ones about it are lines."""
    if not entry_ids:
        return {}
    rows = con.execute(
        """
        SELECT DISTINCT ON (entry_id) entry_id::text, id::text
        FROM messages WHERE entry_id = ANY(%s::uuid[])
        ORDER BY entry_id, sent_at, id
        """,
        (entry_ids,),
    ).fetchall()
    return {str(e): str(m) for e, m in rows}
