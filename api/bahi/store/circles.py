"""Family circles: who is in them, what is on their lists, and their notes.

No query here is ever made for a shop: the shop does not see the circle.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from psycopg.rows import class_row

from bahi.store.db import Conn


@dataclass(frozen=True, slots=True)
class Circle:
    id: str
    name: str
    created_by: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class Member:
    person_id: str
    added_by: str
    joined_at: datetime


@dataclass(frozen=True, slots=True)
class Share:
    circle_id: str
    entry_id: str
    shared_by: str
    shared_at: datetime


@dataclass(frozen=True, slots=True)
class Notice:
    id: str
    person_id: str
    kind: str
    circle_id: str | None
    entry_id: str | None
    body: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class Paid:
    entry_id: str
    amount_paise: int
    paid_at: datetime
    #: The member who paid; None when the debtor paid it, or cash.
    paid_by: str | None


CIRCLE = (
    "SELECT id::text AS id, name, created_by::text AS created_by, created_at FROM circles"
)


# ── circles and members ──────────────────────────────────────────────────────


def create(con: Conn, name: str, created_by: str, now: datetime) -> str:
    row = con.execute(
        "INSERT INTO circles (name, created_by, created_at) VALUES (%s, %s, %s) "
        "RETURNING id::text",
        (name, created_by, now),
    ).fetchone()
    assert row is not None
    return str(row[0])


def get(con: Conn, circle_id: str) -> Circle | None:
    with con.cursor(row_factory=class_row(Circle)) as cur:
        return cur.execute(CIRCLE + " WHERE id = %s", (circle_id,)).fetchone()


def of_person(con: Conn, person_id: str) -> list[Circle]:
    """The circles this person is in now, oldest first."""
    with con.cursor(row_factory=class_row(Circle)) as cur:
        return cur.execute(
            CIRCLE + " WHERE id IN (SELECT circle_id FROM circle_members "
            "WHERE person_id = %s AND left_at IS NULL) ORDER BY created_at, id",
            (person_id,),
        ).fetchall()


def add_member(
    con: Conn, circle_id: str, person_id: str, added_by: str, now: datetime
) -> None:
    con.execute(
        "INSERT INTO circle_members (circle_id, person_id, added_by, joined_at) "
        "VALUES (%s, %s, %s, %s)",
        (circle_id, person_id, added_by, now),
    )


def members(con: Conn, circle_id: str) -> list[Member]:
    """Who is in it now, in the order they joined."""
    with con.cursor(row_factory=class_row(Member)) as cur:
        return cur.execute(
            "SELECT person_id::text AS person_id, added_by::text AS added_by, joined_at "
            "FROM circle_members WHERE circle_id = %s AND left_at IS NULL "
            "ORDER BY joined_at, person_id",
            (circle_id,),
        ).fetchall()


def is_member(con: Conn, circle_id: str, person_id: str) -> bool:
    row = con.execute(
        "SELECT 1 FROM circle_members "
        "WHERE circle_id = %s AND person_id = %s AND left_at IS NULL",
        (circle_id, person_id),
    ).fetchone()
    return row is not None


def leave(con: Conn, circle_id: str, person_id: str, now: datetime) -> bool:
    row = con.execute(
        "UPDATE circle_members SET left_at = %s "
        "WHERE circle_id = %s AND person_id = %s AND left_at IS NULL RETURNING id",
        (now, circle_id, person_id),
    ).fetchone()
    return row is not None


# ── the setting ──────────────────────────────────────────────────────────────


def chosen(con: Conn, person_id: str) -> str | None:
    """What this person chose to happen to a new udhaar; None if they never did."""
    row = con.execute(
        "SELECT on_udhaar FROM circle_settings WHERE person_id = %s", (person_id,)
    ).fetchone()
    return str(row[0]) if row else None


def choose(con: Conn, person_id: str, on_udhaar: str, now: datetime) -> None:
    con.execute(
        "INSERT INTO circle_settings (person_id, on_udhaar, set_at) VALUES (%s, %s, %s) "
        "ON CONFLICT (person_id) DO UPDATE SET on_udhaar = EXCLUDED.on_udhaar, "
        "set_at = EXCLUDED.set_at",
        (person_id, on_udhaar, now),
    )


# ── the list ─────────────────────────────────────────────────────────────────

SHARE = (
    "SELECT circle_id::text AS circle_id, entry_id::text AS entry_id, "
    "shared_by::text AS shared_by, shared_at FROM circle_shares"
)


def share(
    con: Conn, circle_id: str, entry_id: str, shared_by: str, now: datetime
) -> None:
    """Onto the list. The database refuses an entry that is already on one, or
    one its customer has not said yes to."""
    con.execute(
        "INSERT INTO circle_shares (circle_id, entry_id, shared_by, shared_at) "
        "VALUES (%s, %s, %s, %s)",
        (circle_id, entry_id, shared_by, now),
    )


def on_a_list(con: Conn, entry_id: str) -> Share | None:
    """The list this entry is on now, if any."""
    with con.cursor(row_factory=class_row(Share)) as cur:
        return cur.execute(
            SHARE + " WHERE entry_id = %s AND withdrawn_at IS NULL", (entry_id,)
        ).fetchone()


def listed(con: Conn, circle_id: str) -> list[Share]:
    """Everything on this circle's list now, newest first."""
    with con.cursor(row_factory=class_row(Share)) as cur:
        return cur.execute(
            SHARE + " WHERE circle_id = %s AND withdrawn_at IS NULL "
            "ORDER BY shared_at DESC, entry_id",
            (circle_id,),
        ).fetchall()


def listed_for(con: Conn, person_id: str) -> list[Share]:
    """This person's own entries on any list now."""
    with con.cursor(row_factory=class_row(Share)) as cur:
        return cur.execute(
            SHARE + " s WHERE s.withdrawn_at IS NULL AND s.entry_id IN ("
            "SELECT e.id FROM entries e JOIN customers c ON c.id = e.customer_id "
            "WHERE c.person_id = %s)",
            (person_id,),
        ).fetchall()


def withdraw(con: Conn, entry_id: str, why: str, now: datetime) -> bool:
    row = con.execute(
        "UPDATE circle_shares SET withdrawn_at = %s, withdrawn_why = %s "
        "WHERE entry_id = %s AND withdrawn_at IS NULL RETURNING id",
        (now, why, entry_id),
    ).fetchone()
    return row is not None


def withdraw_all(
    con: Conn, circle_id: str, debtor: str, why: str, now: datetime
) -> list[str]:
    """Take every entry of this debtor's off this circle's list. Returns them."""
    rows = con.execute(
        "UPDATE circle_shares s SET withdrawn_at = %s, withdrawn_why = %s "
        "FROM entries e JOIN customers c ON c.id = e.customer_id "
        "WHERE s.entry_id = e.id AND s.circle_id = %s AND c.person_id = %s "
        "AND s.withdrawn_at IS NULL RETURNING s.entry_id::text",
        (now, why, circle_id, debtor),
    ).fetchall()
    return [str(r[0]) for r in rows]


def lock_entry(con: Conn, entry_id: str) -> None:
    """Hold the entry until the request ends, so two members paying the same bill
    at once are split one after the other: the second pays only what is left."""
    con.execute("SELECT 1 FROM entries WHERE id = %s FOR UPDATE", (entry_id,))


def payments(con: Conn, entry_ids: list[str]) -> list[Paid]:
    """Every payment against these entries, oldest first, with who paid."""
    if not entry_ids:
        return []
    with con.cursor(row_factory=class_row(Paid)) as cur:
        return cur.execute(
            "SELECT entry_id::text AS entry_id, amount_paise, paid_at, "
            "paid_by::text AS paid_by FROM repayments "
            "WHERE entry_id = ANY(%s::uuid[]) ORDER BY paid_at",
            (entry_ids,),
        ).fetchall()


# ── notes to one person ──────────────────────────────────────────────────────

NOTICE = (
    "SELECT id::text AS id, person_id::text AS person_id, kind, "
    "circle_id::text AS circle_id, entry_id::text AS entry_id, body, created_at "
    "FROM circle_notices"
)


def notify(
    con: Conn,
    person_id: str,
    kind: str,
    body: str,
    now: datetime,
    *,
    circle_id: str | None = None,
    entry_id: str | None = None,
) -> None:
    con.execute(
        "INSERT INTO circle_notices "
        "(person_id, kind, circle_id, entry_id, body, created_at) "
        "VALUES (%s, %s, %s, %s, %s, %s)",
        (person_id, kind, circle_id, entry_id, body, now),
    )


def notices(con: Conn, person_id: str) -> list[Notice]:
    """Their notes still waiting, newest first."""
    with con.cursor(row_factory=class_row(Notice)) as cur:
        return cur.execute(
            NOTICE + " WHERE person_id = %s AND done_at IS NULL "
            "ORDER BY created_at DESC, id",
            (person_id,),
        ).fetchall()


def done(con: Conn, notice_id: str, person_id: str, now: datetime) -> bool:
    row = con.execute(
        "UPDATE circle_notices SET done_at = %s "
        "WHERE id = %s AND person_id = %s AND done_at IS NULL RETURNING id",
        (now, notice_id, person_id),
    ).fetchone()
    return row is not None


def done_about(con: Conn, entry_ids: list[str], now: datetime) -> None:
    """Every note still waiting about these entries is settled: the entry went to
    a list, came off one, or its debtor left."""
    if entry_ids:
        con.execute(
            "UPDATE circle_notices SET done_at = %s "
            "WHERE entry_id = ANY(%s::uuid[]) AND done_at IS NULL",
            (now, entry_ids),
        )


def done_in_circle(con: Conn, circle_id: str, person_id: str, now: datetime) -> None:
    """Every note still waiting for this person about this circle is settled:
    they have left it."""
    con.execute(
        "UPDATE circle_notices SET done_at = %s "
        "WHERE circle_id = %s AND person_id = %s AND done_at IS NULL",
        (now, circle_id, person_id),
    )
