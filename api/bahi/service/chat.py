"""Threads as the screens show them, and the customer's own book.

Formatting and gathering only. Every figure comes from the ledger through
domain/book.py; a card is drawn from the entry as it is now, so a card posted
when ₹200 was recorded shows ✓ the moment he confirms, and "paid" when he pays.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from bahi.domain import book as book_domain
from bahi.domain.limitation import expired
from bahi.domain.wording import button
from bahi.service import ledger, memory, views
from bahi.service.errors import Conflict, NotFound
from bahi.service.models import (
    CustomerDetailOut,
    InboxOut,
    InboxRowOut,
    InviteOut,
    MessageOut,
    MyShopOut,
    MyUdhaarOut,
    ThreadEntryOut,
    ThreadOut,
)
from bahi.store import book as book_store
from bahi.store import customers, entries, memories, reminders, shops, threads
from bahi.store.customers import CustomerRef
from bahi.store.db import Conn
from bahi.store.entries import EntryRef

#: Settled entries the customer's own book lists, per shop.
PAID_SHOWN = 4


def card(e: EntryRef, today: date, corrects: EntryRef | None = None) -> ThreadEntryOut:
    return ThreadEntryOut(
        id=e.id,
        amount_paise=e.amount_paise,
        paid_paise=e.paid_paise,
        status=e.status,  # type: ignore[arg-type]
        recorded_at=e.recorded_at,
        note=e.note,
        corrects_entry_id=e.corrects_entry_id,
        corrects_amount_paise=corrects.amount_paise if corrects else None,
        disputed_at=e.disputed_at,
        acknowledged_at=e.acknowledged_at,
        last_paid_at=e.last_paid_at,
        last_method=e.last_method,  # type: ignore[arg-type]
        expired=e.status in book_domain.OPEN
        and expired(
            e.recorded_at.date(),
            e.acknowledged_at.date() if e.acknowledged_at else None,
            today,
        ),
        button=button(e.amount_paise),
    )


def _cards(con: Conn, customer_id: str, today: date) -> dict[str, ThreadEntryOut]:
    mine = {e.id: e for e in entries.of_customer(con, customer_id)}
    return {
        e.id: card(e, today, mine.get(e.corrects_entry_id or "")) for e in mine.values()
    }


def _standing(con: Conn, c: CustomerRef, today: date) -> tuple[int, int | None]:
    """(what he owes, days since he last paid) at this shop, from the book."""
    found = book_store.load(con, c.shop_id, c.id)
    ln = book_domain.line(found[0], today) if found else None
    return (ln.balance_paise, ln.day) if ln else (0, None)


def _reminder_at(con: Conn, c: CustomerRef, today: date) -> datetime | None:
    r = reminders.for_day(con, c.shop_id, today + timedelta(days=1)).get(c.id)
    return r.send_at if r is not None and r.status == "planned" else None


def thread(con: Conn, c: CustomerRef, today: date, *, for_shop: bool) -> ThreadOut:
    s = ledger.shop(con, c.shop_id)
    t = threads.of_customer(con, c.id)
    said = threads.messages(con, t.id) if t else []
    cards = _cards(con, c.id, today)
    seen: set[str] = set()
    out: list[MessageOut] = []
    for m in said:
        first = m.entry_id is not None and m.entry_id not in seen
        if m.entry_id:
            seen.add(m.entry_id)
        out.append(
            MessageOut(
                id=m.id,
                author=m.author,  # type: ignore[arg-type]
                kind=m.kind,  # type: ignore[arg-type]
                body=m.body,
                sent_at=m.sent_at,
                entry=cards.get(m.entry_id) if m.entry_id else None,
                card=first,
            )
        )
    owed, day = _standing(con, c, today)
    return ThreadOut(
        today=today,
        thread_id=t.id if t else None,
        customer_id=c.id,
        shop=views.shop_out(s),
        display_name=c.display_name,
        tag=c.tag,
        joined=c.joined,
        balance_paise=owed,
        day=day,
        messages=out,
        reminder_at=_reminder_at(con, c, today) if for_shop else None,
    )


def customer_at(con: Conn, shop_id: str, customer_id: str) -> CustomerRef:
    c = customers.get(con, customer_id)
    if c is None or c.shop_id != shop_id:
        raise NotFound(f"no customer {customer_id} at this shop")
    return c


def person_at(con: Conn, person_id: str, shop_id: str) -> CustomerRef:
    c = customers.at_shop(con, shop_id, person_id)
    if c is None or not c.linked:
        raise NotFound("you are not in this shop's book")
    return c


def shop_says(
    con: Conn, shop_id: str, customer_id: str, text: str, now: datetime
) -> None:
    c = customer_at(con, shop_id, customer_id)
    if c.joined != "linked":
        raise Conflict(
            f"{c.display_name} isn't on BAHI, so nothing reaches them"
            if c.joined == "name_only"
            else f"{c.display_name} hasn't accepted your invite yet"
        )
    threads.post(con, c.id, "shop", "text", text.strip(), now)


def inbox(con: Conn, shop_id: str, today: date) -> InboxOut:
    ledger.shop(con, shop_id)
    rows = threads.of_shop(con, shop_id)
    ids = [r.entry_id for r in rows if r.entry_id]
    by_id = entries.by_ids(con, ids)
    first = threads.cards(con, ids)
    disputed = entries.disputed_at_shop(con, shop_id)
    planned = {
        cid: r.send_at
        for cid, r in reminders.for_day(con, shop_id, today + timedelta(days=1)).items()
        if r.status == "planned"
    }
    who = {c.id: c for c in customers.of_shop(con, shop_id)}
    out = [
        InboxRowOut(
            customer_id=r.customer_id,
            display_name=r.display_name,
            tag=r.tag,
            joined=who[r.customer_id].joined,
            author=r.author,  # type: ignore[arg-type]
            kind=r.kind,  # type: ignore[arg-type]
            body=r.body,
            sent_at=r.sent_at,
            entry=card(by_id[r.entry_id], today) if r.entry_id in by_id else None,
            card=r.entry_id is not None and first.get(r.entry_id) == r.message_id,
            unread=r.unread,
            needs_reply=r.author == "customer" or r.customer_id in disputed,
            reminder_at=planned.get(r.customer_id),
        )
        for r in rows
    ]
    return InboxOut(today=today, rows=out, unread=sum(r.unread for r in out))


def customer_detail(con: Conn, c: CustomerRef, today: date) -> CustomerDetailOut:
    owed, day = _standing(con, c, today)
    cards = sorted(
        _cards(con, c.id, today).values(), key=lambda e: e.recorded_at, reverse=True
    )
    live = [e for e in cards if e.status != "settled"]
    paid = [e for e in cards if e.status == "settled"][:PAID_SHOWN]
    return CustomerDetailOut(
        id=c.id,
        display_name=c.display_name,
        tag=c.tag,
        joined=c.joined,
        invite_pending=c.invite_person_id is not None,
        invited_at=c.invited_at,
        balance_paise=owed,
        day=day,
        entries=sorted(live + paid, key=lambda e: e.recorded_at, reverse=True),
        memories=[memory.out(m) for m in memories.of_customer(con, c.id)],
    )


def _my_shop(con: Conn, c: CustomerRef, today: date, unread: int) -> MyShopOut:
    s = ledger.shop(con, c.shop_id)
    owed, day = _standing(con, c, today)
    cards = sorted(
        _cards(con, c.id, today).values(), key=lambda e: e.recorded_at, reverse=True
    )
    live = [e for e in cards if e.status != "settled"]
    paid = [e for e in cards if e.status == "settled"][:PAID_SHOWN]
    return MyShopOut(
        shop=views.shop_out(s),
        customer_id=c.id,
        display_name=c.display_name,
        balance_paise=owed,
        payable_paise=sum(
            e.amount_paise - e.paid_paise for e in ledger.payable(con, c.id, today)
        ),
        day=day,
        entries=sorted(live + paid, key=lambda e: e.recorded_at, reverse=True),
        unread=unread,
    )


def my_udhaar(con: Conn, person_id: str, today: date) -> MyUdhaarOut:
    """His book: every shop he is in the book of, and invitations waiting."""
    rows = customers.of_person(con, person_id)
    unread = {r.customer_id: r.unread for r in threads.of_person(con, person_id)}
    mine = [_my_shop(con, c, today, unread.get(c.id, 0)) for c in rows if c.linked]
    # Shops he owes first, the one with the latest entry first.
    mine.sort(
        key=lambda m: (
            m.balance_paise == 0,
            -max((e.recorded_at.timestamp() for e in m.entries), default=0),
        )
    )
    invites = []
    waiting = [c for c in rows if not c.linked]
    for c in waiting + customers.invites_for(con, person_id):
        s = shops.get(con, c.shop_id)
        assert s is not None
        invites.append(
            InviteOut(
                shop=views.shop_out(s),
                display_name=c.display_name,
                invited_at=c.invited_at or customers.added_at(con, c.id),
                kept_by_name=c.invite_person_id is not None,
            )
        )
    return MyUdhaarOut(
        today=today,
        person_id=person_id,
        total_paise=sum(m.balance_paise for m in mine),
        shops=mine,
        invites=invites,
    )
