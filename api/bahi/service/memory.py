"""M3 · What BAHI remembers: the rules for keeping and forgetting it.

A note comes from the shopkeeper (the munshi, or typed on the customer's page),
a promise from the customer's own chat (bahi.memory reads it), a nickname from
an entry he confirmed. All of them are the shop's own: never shown to the
customer, never put in a reminder. A wait can only hold Tonight's reminder.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from bahi.service import ledger
from bahi.service.errors import Conflict, NotFound
from bahi.service.models import MemoryOut
from bahi.store import customers, memories
from bahi.store.db import Conn
from bahi.store.memories import Kind, Memory, SaidBy

#: Nobody is left alone longer than this on one thing said.
FARTHEST_WAIT = timedelta(days=90)


def out(m: Memory) -> MemoryOut:
    return MemoryOut(
        id=m.id,
        kind=m.kind,  # type: ignore[arg-type]
        body=m.body,
        said_by=m.said_by,  # type: ignore[arg-type]
        until=m.until,
        remembered_at=m.remembered_at,
        message_id=m.message_id,
    )


def wait_problem(until: date | None, today: date) -> str | None:
    """Why this date can't be a wait, or None. It is today or later, and within
    FARTHEST_WAIT."""
    if until is None:
        return None
    if until < today:
        return "that day has already passed"
    if until > today + FARTHEST_WAIT:
        return "that is more than three months away"
    return None


def keep(
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
) -> Memory:
    """Keeps it for a customer of this shop. NotFound for anyone else's, Conflict
    for a wait that can't be one."""
    ledger.shop(con, shop_id)
    c = customers.get(con, customer_id)
    if c is None or c.shop_id != shop_id:
        raise NotFound(f"no customer {customer_id} at this shop")
    problem = wait_problem(until, now.date())
    if problem is not None:
        raise Conflict(f"Can't wait until {until}: {problem}.")
    m = memories.add(
        con,
        shop_id,
        customer_id,
        kind,
        body,
        said_by,
        now,
        until=until,
        message_id=message_id,
    )
    if m is None:  # the same chat message, read twice
        raise Conflict("That message was already remembered.")
    return m


def forget(con: Conn, shop_id: str, memory_id: str, now: datetime) -> Memory:
    ledger.shop(con, shop_id)
    m = memories.forget(con, memory_id, shop_id, now)
    if m is None:
        raise NotFound(f"nothing remembered as {memory_id} at this shop")
    return m
