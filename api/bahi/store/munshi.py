"""The munshi's conversations: every turn, and the draft on the card."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from psycopg.rows import class_row
from psycopg.types.json import Jsonb

from bahi.store.db import Conn

TURN = (
    "id::text AS id, conversation_id::text AS conversation_id, seq, role, message, "
    "heard, ms"
)


@dataclass(frozen=True, slots=True)
class Turn:
    id: str
    conversation_id: str
    seq: int
    role: str
    message: dict[str, Any]
    heard: str | None
    ms: int | None


@dataclass(frozen=True, slots=True)
class Draft:
    id: str
    conversation_id: str
    #: None for someone not in the book yet, until his yes adds him.
    customer_id: str | None
    #: udhaar, payment, or customer (only adds someone; no amount).
    kind: str
    amount_paise: int | None
    spoken_text: str | None
    reasons: list[str]
    status: str
    shown_seq: int
    entry_id: str | None
    #: Someone the munshi would add to the book: name and description.
    new_name: str | None
    new_tag: str | None


def start(con: Conn, shop_id: str, now: datetime) -> str:
    with con.cursor() as cur:
        row = cur.execute(
            "INSERT INTO conversations (shop_id, started_at) VALUES (%s, %s) "
            "RETURNING id::text",
            (shop_id, now),
        ).fetchone()
    assert row is not None
    return str(row[0])


def shop_of(con: Conn, conversation_id: str) -> str | None:
    with con.cursor() as cur:
        row = cur.execute(
            "SELECT shop_id::text FROM conversations WHERE id = %s", (conversation_id,)
        ).fetchone()
    return str(row[0]) if row else None


def turns(con: Conn, conversation_id: str) -> list[Turn]:
    with con.cursor(row_factory=class_row(Turn)) as cur:
        return cur.execute(
            f"SELECT {TURN} FROM turns WHERE conversation_id = %s ORDER BY seq",
            (conversation_id,),
        ).fetchall()


def turn(con: Conn, turn_id: str) -> Turn | None:
    with con.cursor(row_factory=class_row(Turn)) as cur:
        return cur.execute(
            f"SELECT {TURN} FROM turns WHERE id = %s",
            (turn_id,),
        ).fetchone()


def add_turn(
    con: Conn,
    conversation_id: str,
    message: dict[str, Any],
    now: datetime,
    *,
    heard: str | None = None,
    ms: int | None = None,
) -> Turn:
    """Appends one message. The next seq is taken under the conversation's row
    lock, so two requests on one conversation cannot interleave their turns."""
    with con.cursor(row_factory=class_row(Turn)) as cur:
        cur.execute(
            "SELECT 1 FROM conversations WHERE id = %s FOR UPDATE", (conversation_id,)
        )
        row = cur.execute(
            f"""
            INSERT INTO turns
                (conversation_id, seq, role, message, heard, ms, created_at)
            VALUES (%s,
                    (SELECT coalesce(max(seq) + 1, 0) FROM turns
                     WHERE conversation_id = %s),
                    %s, %s, %s, %s, %s)
            RETURNING {TURN}
            """,
            (
                conversation_id,
                conversation_id,
                message["role"],
                Jsonb(message),
                heard,
                ms,
                now,
            ),
        ).fetchone()
    assert row is not None
    return row


COLUMNS = """id::text AS id, conversation_id::text AS conversation_id,
       customer_id::text AS customer_id, kind, amount_paise, spoken_text, reasons,
       status, shown_seq, entry_id::text AS entry_id, new_name, new_tag"""
DRAFT = f"SELECT {COLUMNS} FROM drafts"


def draft(con: Conn, draft_id: str) -> Draft | None:
    with con.cursor(row_factory=class_row(Draft)) as cur:
        return cur.execute(DRAFT + " WHERE id = %s", (draft_id,)).fetchone()


def latest_draft(con: Conn, conversation_id: str) -> Draft | None:
    with con.cursor(row_factory=class_row(Draft)) as cur:
        return cur.execute(
            DRAFT + " WHERE conversation_id = %s "
            "ORDER BY created_at DESC, shown_seq DESC LIMIT 1",
            (conversation_id,),
        ).fetchone()


def show(
    con: Conn,
    conversation_id: str,
    customer_id: str | None,
    kind: str,
    amount_paise: int | None,
    spoken_text: str | None,
    reasons: list[str],
    shown_seq: int,
    now: datetime,
    *,
    new_name: str | None = None,
    new_tag: str | None = None,
) -> Draft:
    """The new card. A card already waiting in this conversation is replaced."""
    with con.cursor(row_factory=class_row(Draft)) as cur:
        cur.execute(
            "UPDATE drafts SET status = 'replaced' "
            "WHERE conversation_id = %s AND status = 'shown'",
            (conversation_id,),
        )
        row = cur.execute(
            f"""
            INSERT INTO drafts (conversation_id, customer_id, kind, amount_paise,
                                spoken_text, reasons, shown_seq, created_at,
                                new_name, new_tag)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING {COLUMNS}
            """,
            (
                conversation_id,
                customer_id,
                kind,
                amount_paise,
                spoken_text,
                reasons,
                shown_seq,
                now,
                new_name,
                new_tag,
            ),
        ).fetchone()
    assert row is not None
    return row


def decide(
    con: Conn,
    draft_id: str,
    status: str,
    now: datetime,
    entry_id: str | None = None,
    customer_id: str | None = None,
) -> bool:
    """Moves a waiting card to saved or cancelled, once. False if it was not
    waiting any more: a second tap, or a card already replaced. `customer_id` is
    the customer a new-customer card added."""
    with con.cursor() as cur:
        row = cur.execute(
            "UPDATE drafts SET status = %s, decided_at = %s, entry_id = %s, "
            "customer_id = coalesce(%s, customer_id) "
            "WHERE id = %s AND status = 'shown' RETURNING id",
            (status, now, entry_id, customer_id, draft_id),
        ).fetchone()
    return row is not None


def claim(con: Conn, draft_id: str) -> Draft | None:
    """The waiting card, locked until the request ends, or None if it is not
    waiting. Two taps racing on one card: the second waits, then finds it saved."""
    with con.cursor(row_factory=class_row(Draft)) as cur:
        return cur.execute(
            DRAFT + " WHERE id = %s AND status = 'shown' FOR UPDATE", (draft_id,)
        ).fetchone()
