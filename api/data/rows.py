"""One dataclass per table, with fields named exactly like its columns.

The seed builds these rather than tuples, so a reader sees
`display_name="Sharma"` instead of counting commas, and `insert()` writes each
field to the column of the same name. Add a column to a table and you add a field
here; nothing else has to line up by position.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import asdict, dataclass, fields
from datetime import datetime
from typing import Any
from uuid import UUID

import psycopg
from psycopg import sql


@dataclass(frozen=True, slots=True)
class ShopRow:
    id: UUID
    name: str
    locality: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class CustomerRow:
    id: UUID
    shop_id: UUID
    person_id: UUID | None
    display_name: str
    tag: str | None
    added_at: datetime
    linked_at: datetime | None
    name_hi: str | None
    tag_hi: str | None


@dataclass(frozen=True, slots=True)
class EntryRow:
    id: UUID
    customer_id: UUID
    amount_paise: int
    status: str
    recorded_at: datetime
    note: str | None = None
    spoken_text: str | None = None
    corrects_entry_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class AcknowledgmentRow:
    id: UUID
    entry_id: UUID
    wording: str
    acknowledged_at: datetime


@dataclass(frozen=True, slots=True)
class RepaymentRow:
    id: UUID
    entry_id: UUID
    amount_paise: int
    method: str
    paid_at: datetime


@dataclass(frozen=True, slots=True)
class ThreadRow:
    id: UUID
    customer_id: UUID
    created_at: datetime
    shop_read_at: datetime | None = None
    customer_read_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class MessageRow:
    id: UUID
    thread_id: UUID
    author: str
    kind: str
    body: str
    sent_at: datetime
    entry_id: UUID | None = None


def insert(cur: psycopg.Cursor[Any], table: str, rows: Sequence[Any]) -> int:
    """INSERT every row, matching each field to the column of the same name."""
    if not rows:
        return 0
    names = [f.name for f in fields(rows[0])]
    query = sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
        sql.Identifier(table),
        sql.SQL(", ").join(map(sql.Identifier, names)),
        sql.SQL(", ").join(map(sql.Placeholder, names)),
    )
    cur.executemany(query, [asdict(r) for r in rows])
    return len(rows)
