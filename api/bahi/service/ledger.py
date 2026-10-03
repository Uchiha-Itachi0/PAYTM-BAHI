"""What the product does, one function per action.

Each takes a connection and the time, checks the rules, and calls the store. None
of them commits: the request does, once, at the end. So an action happens
completely or not at all. If a scan turns out to be taken after the entry was
written, the entry goes too.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from bahi.domain.lifecycle import move
from bahi.domain.wording import acknowledgment
from bahi.service.errors import Conflict, Forbidden, NotFound
from bahi.store import customers, entries, scans, shops
from bahi.store.customers import CustomerRef
from bahi.store.db import Conn
from bahi.store.entries import EntryRef
from bahi.store.scans import Scan
from bahi.store.shops import Shop


def shop(con: Conn, shop_id: str) -> Shop:
    s = shops.get(con, shop_id)
    if s is None:
        raise NotFound(f"no shop {shop_id}")
    return s


def entry(con: Conn, entry_id: str) -> EntryRef:
    e = entries.get(con, entry_id)
    if e is None:
        raise NotFound(f"no entry {entry_id}")
    return e


def scan(con: Conn, scan_id: str) -> Scan:
    s = scans.get(con, scan_id)
    if s is None:
        raise NotFound(f"no scan {scan_id}")
    return s


# ── the shopkeeper ───────────────────────────────────────────────────────────


def record(
    con: Conn,
    shop_id: str,
    amount_paise: int,
    now: datetime,
    *,
    scan_id: UUID | None = None,
    customer_id: UUID | None = None,
    note: str | None = None,
    spoken_text: str | None = None,
) -> EntryRef:
    """An udhaar entry, for someone at the counter or someone in the book.

    Refused for an invited customer who has not said yes: nothing is recorded
    against a Paytm account until its owner accepts.
    """
    shop(con, shop_id)
    sc: Scan | None = None
    if scan_id is not None:
        sc = scan(con, str(scan_id))
        if sc.shop_id != shop_id:
            raise NotFound(f"no scan {scan_id} at this shop")
        cid = sc.customer_id
    elif customer_id is not None:
        cid = str(customer_id)
    else:
        raise Conflict("say who: a scan or a customer")

    c = customers.get(con, cid)
    if c is None or c.shop_id != shop_id:
        raise NotFound(f"no customer {cid} at this shop")
    if c.joined == "invited":
        raise Conflict(f"{c.display_name} has not accepted your invite yet")

    eid = entries.record(con, cid, amount_paise, now, note=note, spoken_text=spoken_text)
    if sc is not None and not scans.claim(con, sc.id, eid, now):
        raise Conflict("that scan was already used, or has expired")
    return entry(con, eid)


# ── the customer ─────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class Joined:
    customer: CustomerRef
    scan_id: str
    first_time: bool


def join(
    con: Conn, shop_id: str, person_id: UUID, name: str | None, now: datetime
) -> Joined:
    """He scanned the shop's udhaar QR.

    First time at this shop: he joins its book under the name he gave. Invited
    earlier: scanning is saying yes. Either way he is now at the counter.
    """
    shop(con, shop_id)
    pid = str(person_id)
    c = customers.at_shop(con, shop_id, pid)
    created = False
    if c is None:
        if not name:
            raise Conflict("first visit to this shop: tell us the name to use")
        customers.add(con, shop_id, name.strip(), now, person_id=pid, linked=True)
        created = True
    elif not c.linked:
        customers.link(con, c.id, now)

    c = customers.at_shop(con, shop_id, pid)
    assert c is not None
    first = created or not entries.of_customer(con, c.id)
    return Joined(customer=c, scan_id=scans.add(con, c.id, now), first_time=first)


def leave(con: Conn, scan_id: str, now: datetime) -> None:
    scan(con, scan_id)
    if not scans.leave(con, scan_id, now):
        raise Conflict("that scan is no longer waiting")


def mine(con: Conn, entry_id: str, person_id: UUID) -> EntryRef:
    """The entry, if it is recorded against this person."""
    e = entry(con, entry_id)
    if e.person_id != str(person_id):
        raise Forbidden("this entry is recorded against someone else")
    return e


def confirm(con: Conn, entry_id: str, person_id: UUID, now: datetime) -> EntryRef:
    """He tapped "Yes, I owe ₹200". Stored with the exact words he saw."""
    e = mine(con, entry_id, person_id)
    status = move(e.status, "confirm")
    entries.acknowledge(con, e.id, acknowledgment(e.amount_paise, e.shop_name), now)
    entries.set_status(con, e.id, status)
    return entry(con, e.id)


def dispute(
    con: Conn, entry_id: str, person_id: UUID, reason: str | None, now: datetime
) -> EntryRef:
    """He tapped "That's not right". The entry stays, marked disputed."""
    e = mine(con, entry_id, person_id)
    entries.set_status(con, e.id, move(e.status, "dispute"))
    return entry(con, e.id)
