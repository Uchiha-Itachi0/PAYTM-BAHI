"""Scans: someone at the counter.

A scan records no debt. It says "I'm here" for three minutes, and the shopkeeper
may attach one amount to it. Whether a scan is still waiting is computed from the
clock the caller passes in, never stored, so there is no job to expire them.

She may also ask for an amount herself ("₹200, atta and oil"). The ask waits on
the scan, which then stays open for ten minutes, until the shopkeeper answers:
yes (that amount is written, agreed by both), no (nothing is written), or a
different amount (an ordinary entry, which she confirms).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal

from psycopg.rows import class_row

from bahi.store.db import Conn

#: How long a scan stays on the shopkeeper's screen.
WINDOW = timedelta(minutes=3)
#: How long an ask waits for his answer.
ASK_WINDOW = timedelta(minutes=10)

State = Literal["waiting", "recorded", "left", "expired", "declined"]
Answer = Literal["yes", "no", "changed"]

#: Still waiting: nothing attached, not left, not refused, and either scanned
#: in the last three minutes or asking for an amount that has no answer yet.
OPEN = """
    s.entry_id IS NULL AND s.left_at IS NULL AND s.answer IS DISTINCT FROM 'no'
    AND (s.scanned_at > %(since)s
         OR (s.asked_at > %(ask_since)s AND s.answer IS NULL))
"""


def _window(now: datetime) -> dict[str, datetime]:
    return {"since": now - WINDOW, "ask_since": now - ASK_WINDOW, "now": now}


@dataclass(frozen=True, slots=True)
class Waiting:
    scan_id: str
    customer_id: str
    display_name: str
    tag: str | None
    scanned_at: datetime
    #: No entries at this shop yet: the shopkeeper does not know his name.
    first_time: bool
    #: What she asked for, if she did, and what for.
    asked_paise: int | None = None
    asked_note: str | None = None


@dataclass(frozen=True, slots=True)
class Scan:
    id: str
    customer_id: str
    shop_id: str
    scanned_at: datetime
    entry_id: str | None
    left_at: datetime | None
    asked_paise: int | None = None
    asked_note: str | None = None
    asked_at: datetime | None = None
    answer: str | None = None

    @property
    def asking(self) -> bool:
        """She asked for an amount, and he hasn't answered."""
        return self.asked_at is not None and self.answer is None

    def state(self, now: datetime) -> State:
        if self.entry_id:
            return "recorded"
        if self.answer == "no":
            return "declined"
        if self.left_at:
            return "left"
        if self.asking and self.asked_at and self.asked_at > now - ASK_WINDOW:
            return "waiting"
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
                   s.entry_id::text AS entry_id, s.left_at, s.asked_paise,
                   s.asked_note, s.asked_at, s.answer
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
                       AS first_time,
                   CASE WHEN s.answer IS NULL THEN s.asked_paise END AS asked_paise,
                   CASE WHEN s.answer IS NULL THEN s.asked_note END AS asked_note
            FROM scans s JOIN customers c ON c.id = s.customer_id
            WHERE c.shop_id = %(shop)s AND s.scanned_at <= %(now)s AND """
            + OPEN
            + """
            ORDER BY s.scanned_at
            """,
            {"shop": shop_id, **_window(now)},
        ).fetchall()


def waiting_for(con: Conn, customer_id: str, now: datetime) -> str | None:
    """His scan that is still waiting, if he has one."""
    row = con.execute(
        """
        SELECT s.id::text FROM scans s
        WHERE s.customer_id = %(customer)s AND s.scanned_at <= %(now)s AND """
        + OPEN
        + """
        ORDER BY s.scanned_at DESC LIMIT 1
        """,
        {"customer": customer_id, **_window(now)},
    ).fetchone()
    return None if row is None else str(row[0])


def claim(con: Conn, scan_id: str, entry_id: str, now: datetime) -> bool:
    """Attach an entry to a waiting scan. True if this call won it.

    One conditional UPDATE, so if two requests race for the same scan exactly one
    gets a row back. No lock, no read-then-write gap.
    """
    row = con.execute(
        """
        UPDATE scans s SET entry_id = %(entry)s
        WHERE s.id = %(scan)s AND """
        + OPEN
        + """
        RETURNING id
        """,
        {"entry": entry_id, "scan": scan_id, **_window(now)},
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


def ask(con: Conn, scan_id: str, paise: int, note: str | None, now: datetime) -> bool:
    """She asks for an amount on her waiting scan. Asking again before he answers
    replaces it. True if the scan was still open and unanswered."""
    row = con.execute(
        """
        UPDATE scans s SET asked_paise = %(paise)s, asked_note = %(note)s,
                           asked_at = %(now)s
        WHERE s.id = %(scan)s AND s.answer IS NULL AND """
        + OPEN
        + """
        RETURNING id
        """,
        {"paise": paise, "note": note, "scan": scan_id, **_window(now)},
    ).fetchone()
    return row is not None


def answer(con: Conn, scan_id: str, said: Answer, now: datetime) -> bool:
    """His answer to her ask, once. True if this call gave it."""
    row = con.execute(
        "UPDATE scans SET answer = %s, answered_at = %s "
        "WHERE id = %s AND asked_at IS NOT NULL AND answer IS NULL RETURNING id",
        (said, now, scan_id),
    ).fetchone()
    return row is not None
