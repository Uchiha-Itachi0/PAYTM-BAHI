"""What the product does, one function per action.

Each takes a connection and the time, checks the rules, and calls the store. None
of them commits: the request does, once, at the end. So an action happens
completely or not at all. If a scan turns out to be taken after the entry was
written, the entry goes too.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from bahi import voice
from bahi.domain.check import Checked
from bahi.domain.lifecycle import move
from bahi.domain.who import Ask, Person, Picked, who
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


@dataclass(frozen=True, slots=True)
class Hearing:
    checked: Checked
    #: Why our parser read it instead of Sarvam-105B, if it did.
    fallback: voice.Fallback | None
    #: customer id -> his waiting scan, for everyone at the counter.
    scans: dict[str, str]


def counter_and_book(
    con: Conn, shop_id: str, now: datetime
) -> tuple[list[Person], list[Person], dict[str, str]]:
    """Who could this be: the people waiting, and everyone who can be recorded against.

    Invited customers are left out of the book: nothing is recorded against them
    until they say yes. A Person's ref is the customer id; his scan is looked up.
    """
    book = [
        Person(c.id, c.display_name, c.tag, c.name_hi, c.tag_hi)
        for c in customers.of_shop(con, shop_id)
        if c.joined != "invited"
    ]
    by_id = {p.ref: p for p in book}
    waiting = {w.customer_id: w for w in scans.waiting(con, shop_id, now)}
    at_counter = [
        by_id.get(cid) or Person(cid, w.display_name) for cid, w in waiting.items()
    ]
    return at_counter, book, {cid: w.scan_id for cid, w in waiting.items()}


def hear(con: Conn, shop_id: str, transcript: str, now: datetime) -> Hearing:
    """What was said, and who it is for. Reads only: the entry is still a POST.

    Sarvam-105B reads the words (our parser, offline) and `domain.check` holds
    that reading to them: the amount must be in the words, and who it is for is
    decided by code from the words that name him, or asked.
    """
    shop(con, shop_id)
    at_counter, book, waiting_scans = counter_and_book(con, shop_id, now)
    checked, fallback = voice.understand(transcript, at_counter, book)
    return Hearing(checked, fallback, waiting_scans)


@dataclass(frozen=True, slots=True)
class Answer:
    who: Picked | Ask
    scans: dict[str, str]


def answer(
    con: Conn, shop_id: str, transcript: str, among: list[str], now: datetime
) -> Answer:
    """His answer to "किसके लिए?": who the words name, and nothing else.

    `among` is who the screen offered ("Kaunse Anubhav?"): the answer is looked
    for only there, so "Shukla" or "204 wala" picks one of them. Empty, it is the
    counter and the book. The whole answer is the words that name him, and the
    same rules decide as for a sentence: by sound, a room number narrows it, a
    weak match is only offered. The amount is not read again.
    """
    shop(con, shop_id)
    at_counter, book, waiting_scans = counter_and_book(con, shop_id, now)
    known = book  # which words tell customers apart is a question for the whole book
    if among:
        wanted = set(among)
        book = [p for p in book if p.ref in wanted]
        at_counter = [p for p in at_counter if p.ref in wanted]
    if not transcript.strip():
        return Answer(Ask("not_found", ()), waiting_scans)
    return Answer(who(transcript, at_counter, book, known=known), waiting_scans)


# ── the customer ─────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class Joined:
    customer: CustomerRef
    scan_id: str
    first_time: bool


def join(
    con: Conn,
    shop_id: str,
    person_id: UUID,
    name: str | None,
    now: datetime,
    hindi: Callable[[str], str | None] = lambda _: None,
) -> Joined:
    """He scanned the shop's udhaar QR.

    First time at this shop: he joins its book under the name he gave. Invited
    earlier: scanning is saying yes. Either way he is now at the counter, once: a
    second scan while he is still waiting (his phone reloaded the page) is the same
    visit, so the counter never lists him twice.

    `hindi` writes a new customer's name in Devanagari, so a transcript in either
    script finds him. It may say None; the roman name still matches.
    """
    shop(con, shop_id)
    pid = str(person_id)
    c = customers.at_shop(con, shop_id, pid)
    created = False
    if c is None:
        if not name:
            raise Conflict("first visit to this shop: tell us the name to use")
        customers.add(
            con,
            shop_id,
            name.strip(),
            now,
            person_id=pid,
            linked=True,
            name_hi=hindi(name.strip()),
        )
        created = True
    elif not c.linked:
        customers.link(con, c.id, now)

    c = customers.at_shop(con, shop_id, pid)
    assert c is not None
    first = created or not entries.of_customer(con, c.id)
    scan_id = scans.waiting_for(con, c.id, now) or scans.add(con, c.id, now)
    return Joined(customer=c, scan_id=scan_id, first_time=first)


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
