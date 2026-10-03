"""How each customer pays, as the sentence Cognee keeps (migration 009)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from psycopg.rows import class_row

from bahi.store.db import Conn


@dataclass(frozen=True, slots=True)
class Profile:
    customer_id: str
    shop_id: str
    body: str
    written_at: datetime
    stored_at: datetime | None
    cognee_id: str | None
    stale_cognee_id: str | None


SELECT = """
SELECT customer_id::text AS customer_id, shop_id::text AS shop_id, body, written_at,
       stored_at, cognee_id::text AS cognee_id, stale_cognee_id::text AS stale_cognee_id
FROM profiles
"""


def get(con: Conn, customer_id: str) -> Profile | None:
    with con.cursor(row_factory=class_row(Profile)) as cur:
        return cur.execute(SELECT + " WHERE customer_id = %s", (customer_id,)).fetchone()


def write(con: Conn, shop_id: str, customer_id: str, body: str, now: datetime) -> bool:
    """His sentence, if it changed: to be stored again, and Cognee's copy of the
    old one to be taken out. True when it changed."""
    row = con.execute(
        """
        INSERT INTO profiles (customer_id, shop_id, body, written_at)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (customer_id) DO UPDATE SET
            body = excluded.body,
            written_at = excluded.written_at,
            stored_at = NULL,
            stale_cognee_id = coalesce(profiles.stale_cognee_id, profiles.cognee_id),
            cognee_id = NULL
        WHERE profiles.body <> excluded.body
        RETURNING customer_id
        """,
        (customer_id, shop_id, body, now),
    ).fetchone()
    return row is not None


def to_store(con: Conn, limit: int) -> list[Profile]:
    with con.cursor(row_factory=class_row(Profile)) as cur:
        return cur.execute(
            SELECT + " WHERE stored_at IS NULL ORDER BY written_at LIMIT %s"
            " FOR UPDATE SKIP LOCKED",
            (limit,),
        ).fetchall()


def stored(con: Conn, customer_id: str, cognee_id: str | None, now: datetime) -> None:
    con.execute(
        "UPDATE profiles SET stored_at = %s, cognee_id = %s, stale_cognee_id = NULL"
        " WHERE customer_id = %s",
        (now, cognee_id, customer_id),
    )
