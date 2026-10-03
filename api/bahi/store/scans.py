"""Scans: someone at the counter.

A scan records no debt. It says "I'm here" for three minutes, and the shopkeeper
may attach one amount to it. Whether a scan is still waiting is computed from the
clock the caller passes in, never stored, so there is no job to expire them.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal

from psycopg.rows import class_row

from bahi.store.db import Conn

#: How long a scan stays on the shopkeeper's screen.
WINDOW = timedelta(minutes=3)

State = Literal["waiting", "recorded", "left", "expired"]


@dataclass(frozen=True, slots=True)
class Waiting:
    scan_id: str
    customer_id: str
    display_name: str
    tag: str | None
    scanned_at: datetime
    #: No entries at this shop yet: the shopkeeper does not know his name.
    first_time: bool


@dataclass(frozen=True, slots=True)
class Scan:
    id: str
    customer_id: str
    shop_id: str
    scanned_at: datetime
    entry_id: str | None
    left_at: datetime | None

    def state(self, now: datetime) -> State:
        if self.entry_id:
            return "recorded"
        if self.left_at:
            return "left"
        if self.scanned_at <= now - WINDOW:
            return "expired"
        return "waiting"


def add(con: Conn, customer_id: str, now: datetime) -> str:
    row = con.execute(
        "INSERT INTO scans (customer_id, scanned_at) VALUES (%s, %s) RETURNING id::text",
        (customer_id, now),
    ).fetchone()
    assert row is not None
    return str(row[0])


def get(con: Conn, scan_id: str) -> Scan | None:
    with con.cursor(row_factory=class_row(Scan)) as cur:
        return cur.execute(
            """
            SELECT s.id::text AS id, s.customer_id::text AS customer_id,
                   c.shop_id::text AS shop_id, s.scanned_at,
                   s.entry_id::text AS entry_id, s.left_at
            FROM scans s JOIN customers c ON c.id = s.customer_id
            WHERE s.id = %s
            """,
            (scan_id,),
        ).fetchone()


def waiting(con: Conn, shop_id: str, now: datetime) -> list[Waiting]:
    """Everyone at the counter right now, oldest scan first."""
    with con.cursor(row_factory=class_row(Waiting)) as cur:
        return cur.execute(
            """
            SELECT s.id::text AS scan_id, c.id::text AS customer_id, c.display_name,
                   c.tag, s.scanned_at,
                   NOT EXISTS (SELECT 1 FROM entries e WHERE e.customer_id = c.id)
                       AS first_time
            FROM scans s JOIN customers c ON c.id = s.customer_id
            WHERE c.shop_id = %(shop)s
              AND s.entry_id IS NULL AND s.left_at IS NULL
              AND s.scanned_at > %(since)s AND s.scanned_at <= %(now)s
            ORDER BY s.scanned_at
            """,
            {"shop": shop_id, "since": now - WINDOW, "now": now},
        ).fetchall()


def claim(con: Conn, scan_id: str, entry_id: str, now: datetime) -> bool:
    """Attach an entry to a waiting scan. True if this call won it.

    One conditional UPDATE, so if two requests race for the same scan exactly one
    gets a row back. No lock, no read-then-write gap.
    """
    row = con.execute(
        """
        UPDATE scans SET entry_id = %(entry)s
        WHERE id = %(scan)s AND entry_id IS NULL AND left_at IS NULL
          AND scanned_at > %(since)s
        RETURNING id
        """,
        {"entry": entry_id, "scan": scan_id, "since": now - WINDOW},
    ).fetchone()
    return row is not None


def leave(con: Conn, scan_id: str, now: datetime) -> bool:
    """He tapped Cancel. True if he was still waiting."""
    row = con.execute(
        "UPDATE scans SET left_at = %s WHERE id = %s AND entry_id IS NULL "
        "AND left_at IS NULL RETURNING id",
        (now, scan_id),
    ).fetchone()
    return row is not None
