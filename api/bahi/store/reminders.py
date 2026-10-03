"""Tonight's reminders: the words drafted, the shopkeeper's Stop, and what was sent."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal

from psycopg.rows import class_row

from bahi.store.db import Conn

Status = Literal["planned", "stopped", "sent"]
Written = Literal["munshi", "words"]


@dataclass(frozen=True, slots=True)
class Reminder:
    id: str
    customer_id: str
    for_day: date
    send_at: datetime
    body: str
    written: str
    status: str
    message_id: str | None


SELECT = """
SELECT r.id::text AS id, r.customer_id::text AS customer_id, r.for_day, r.send_at,
       r.body, r.written, r.status, r.message_id::text AS message_id
FROM reminders r JOIN customers c ON c.id = r.customer_id
"""


def get(con: Conn, reminder_id: str, shop_id: str) -> Reminder | None:
    with con.cursor(row_factory=class_row(Reminder)) as cur:
        return cur.execute(
            SELECT + " WHERE r.id = %s AND c.shop_id = %s", (reminder_id, shop_id)
        ).fetchone()


def for_day(con: Conn, shop_id: str, day: date) -> dict[str, Reminder]:
    """The day's reminders at this shop, by customer."""
    with con.cursor(row_factory=class_row(Reminder)) as cur:
        rows = cur.execute(
            SELECT + " WHERE c.shop_id = %s AND r.for_day = %s", (shop_id, day)
        ).fetchall()
    return {r.customer_id: r for r in rows}


def last_sent(con: Conn, shop_id: str) -> dict[str, date]:
    """The day each customer was last sent a reminder, in IST."""
    rows = con.execute(
        """
        SELECT r.customer_id::text,
               max((m.sent_at AT TIME ZONE 'Asia/Kolkata')::date)
        FROM reminders r
        JOIN customers c ON c.id = r.customer_id
        JOIN messages m ON m.id = r.message_id
        WHERE c.shop_id = %s AND r.status = 'sent'
        GROUP BY r.customer_id
        """,
        (shop_id,),
    ).fetchall()
    return {str(cid): day for cid, day in rows}


def add(
    con: Conn,
    customer_id: str,
    day: date,
    send_at: datetime,
    body: str,
    written: Written,
    now: datetime,
) -> None:
    """The drafted reminder. Drafting twice keeps the first."""
    con.execute(
        """
        INSERT INTO reminders (customer_id, for_day, send_at, body, written, created_at)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (customer_id, for_day) DO NOTHING
        """,
        (customer_id, day, send_at, body, written, now),
    )


def set_status(
    con: Conn, reminder_id: str, status: Literal["planned", "stopped"]
) -> bool:
    """Stop it, or let it go again. False once it has been sent."""
    row = con.execute(
        "UPDATE reminders SET status = %s "
        "WHERE id = %s AND status <> 'sent' RETURNING id",
        (status, reminder_id),
    ).fetchone()
    return row is not None


def mark_sent(con: Conn, reminder_id: str, message_id: str) -> bool:
    """It went out as this message. Once: a second send finds it sent."""
    row = con.execute(
        "UPDATE reminders SET status = 'sent', message_id = %s "
        "WHERE id = %s AND status = 'planned' RETURNING id",
        (message_id, reminder_id),
    ).fetchone()
    return row is not None


def claim(con: Conn, reminder_id: str) -> Reminder | None:
    """The reminder, locked until the request ends, if it is still planned. Two
    sends racing: the second waits, then finds it sent."""
    with con.cursor(row_factory=class_row(Reminder)) as cur:
        return cur.execute(
            SELECT + " WHERE r.id = %s AND r.status = 'planned' FOR UPDATE OF r",
            (reminder_id,),
        ).fetchone()
