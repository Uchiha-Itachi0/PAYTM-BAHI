"""What the product does, one function per action.

Each takes a connection and the time, checks the rules, and calls the store. None
of them commits: the request does, once, at the end. So an action happens
completely or not at all. If a scan turns out to be taken after the entry was
written, the entry goes too.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from uuid import UUID

from bahi import voice
from bahi.domain import book as book_domain
from bahi.domain import wording
from bahi.domain.book import OPEN
from bahi.domain.check import Checked
from bahi.domain.lifecycle import move
from bahi.domain.limitation import expired
from bahi.domain.money import rupees
from bahi.domain.who import Ask, Person, Picked, who
from bahi.domain.wording import acknowledgment
from bahi.service.errors import Conflict, Forbidden, NotFound
from bahi.store import book as book_store
from bahi.store import customers, entries, scans, shops, threads
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
    e = entry(con, eid)
    _card(con, e, wording.recorded(e.shop_name, amount_paise), now)
    return e


def _card(con: Conn, e: EntryRef, body: str, now: datetime) -> None:
    """BAHI's line about an entry, in his thread with the shop. The first one for
    an entry is its card; the screens draw it with the entry's current state.
    Someone kept by name only has no phone and no thread: nobody would read it."""
    c = customers.get(con, e.customer_id)
    if c is None or c.joined != "linked":
        return
    threads.post(con, e.customer_id, "bahi", "entry", body, now, entry_id=e.id)


def correct(
    con: Conn,
    shop_id: str,
    entry_id: str,
    amount_paise: int,
    now: datetime,
    *,
    spoken_text: str | None = None,
) -> EntryRef:
    """The right amount for an entry, as a new entry.

    The shopkeeper's, whether the customer said it was wrong or he found it
    himself. The old entry is kept, marked corrected, and counts for nothing.
    The correction points at it, is recorded like any entry, and needs the
    customer's own yes. Nothing is rubbed out: the thread shows both. Refused for
    an entry anything has been paid against (the payment names it), or one past
    the limitation line.
    """
    old = entry(con, entry_id)
    if old.shop_id != shop_id:
        raise NotFound(f"no entry {entry_id} at this shop")
    if old.paid_paise > 0:
        raise Conflict(
            "part of this entry is already paid, so it can't be corrected; "
            "record the difference as a new entry instead"
        )
    if expired(
        old.recorded_at.date(),
        old.acknowledged_at.date() if old.acknowledged_at else None,
        now.date(),
    ):
        raise Conflict("this entry is past the limitation line; it claims nothing")
    if amount_paise == old.amount_paise:
        raise Conflict("that is the amount it already says")
    status = move(old.status, "correct")
    new_id = entries.record(
        con,
        old.customer_id,
        amount_paise,
        now,
        note=old.note,
        spoken_text=spoken_text,
        corrects=old.id,
    )
    entries.set_status(con, old.id, status)
    new = entry(con, new_id)
    _card(con, new, wording.corrected(new.shop_name, amount_paise), now)
    return new


def balance(con: Conn, shop_id: str, customer_id: str, today: date) -> int:
    """What he owes this shop, as the book counts it."""
    found = book_store.load(con, shop_id, customer_id)
    ln = book_domain.line(found[0], today) if found else None
    return ln.balance_paise if ln else 0


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


def pay_cash(con: Conn, customer_id: str, amount_paise: int, now: datetime) -> list[str]:
    """Cash he handed over at the counter, split across his open entries oldest
    first. An expired entry is skipped, so a payment never quietly revives a dead
    debt; an entry paid in full is settled. Refused if it is more than he owes.
    Returns the entries it paid, in order."""
    today = now.date()
    open_entries = [
        e
        for e in entries.of_customer(con, customer_id)
        # a disputed entry isn't agreed yet, so cash does not go to it
        if e.status in OPEN - {"disputed"}
        and e.amount_paise > e.paid_paise
        and not expired(
            e.recorded_at.date(),
            e.acknowledged_at.date() if e.acknowledged_at else None,
            today,
        )
    ]
    owed = sum(e.amount_paise - e.paid_paise for e in open_entries)
    if amount_paise > owed:
        raise Conflict(f"that is more than the ₹{owed // 100} he owes")
    left, paid = amount_paise, []
    for e in open_entries:
        if left == 0:
            break
        take = min(left, e.amount_paise - e.paid_paise)
        entries.pay(con, e.id, take, "cash", now)
        if take == e.amount_paise - e.paid_paise:
            entries.set_status(con, e.id, move(e.status, "settle"))
        left -= take
        paid.append(e.id)
    if paid:
        last = entry(con, paid[-1])
        left = balance(con, last.shop_id, customer_id, today)
        _card(con, last, wording.paid(amount_paise, "cash", left), now)
    return paid


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
    move(e.status, "dispute")  # refuses anything but a recorded entry
    entries.dispute(con, e.id, now)
    _card(con, e, wording.disputed(e.display_name, e.amount_paise), now)
    if reason and reason.strip():
        # His reason is his own words in the thread, just after BAHI's line.
        threads.post(
            con,
            e.customer_id,
            "customer",
            "text",
            reason.strip(),
            now + timedelta(microseconds=1),
        )
    return entry(con, e.id)


@dataclass(frozen=True, slots=True)
class Paid:
    shop: Shop
    customer_id: str
    amount_paise: int
    #: The entries it paid, oldest first. Those paid in full are settled.
    entry_ids: list[str]
    #: What he still owes this shop after it.
    left_paise: int
    #: From the oldest entry it paid to today, in days.
    settled_in: int


def payable(con: Conn, customer_id: str, today: date) -> list[EntryRef]:
    """What he can pay now: his open entries that are still claimable, oldest
    first. Not a disputed one (nothing is agreed yet), and not an expired one (a
    payment must never quietly revive a dead debt)."""
    return [
        e
        for e in entries.of_customer(con, customer_id)
        if e.status in OPEN - {"disputed"}
        and e.amount_paise > e.paid_paise
        and not expired(
            e.recorded_at.date(),
            e.acknowledged_at.date() if e.acknowledged_at else None,
            today,
        )
    ]


def pay_upi(
    con: Conn,
    person_id: UUID,
    shop_id: str,
    now: datetime,
    amount_paise: int | None = None,
) -> Paid:
    """He paid in his own app, by UPI: everything he owes this shop, or the part
    he chose. Split across his entries oldest first, each one named; an entry paid
    in full is settled. Paytm moves the money; the book records which entries it
    paid, and the shop is told in the thread with what is still open."""
    s = shop(con, shop_id)
    c = customers.at_shop(con, shop_id, str(person_id))
    if c is None or not c.linked:
        raise NotFound("you are not in this shop's book")
    owed = payable(con, c.id, now.date())
    most = sum(e.amount_paise - e.paid_paise for e in owed)
    if most == 0:
        raise Conflict(f"you owe {s.name} nothing you can pay right now")
    amount = most if amount_paise is None else amount_paise
    if amount > most:
        raise Conflict(f"that is more than the {rupees(most)} you owe {s.name}")
    left, paid = amount, []
    for e in owed:
        if left == 0:
            break
        take = min(left, e.amount_paise - e.paid_paise)
        entries.pay(con, e.id, take, "upi", now)
        if take == e.amount_paise - e.paid_paise:
            entries.set_status(con, e.id, move(e.status, "settle"))
        left -= take
        paid.append(e)
    still = balance(con, shop_id, c.id, now.date())
    _card(con, entry(con, paid[-1].id), wording.paid(amount, "upi", still), now)
    oldest = min(e.recorded_at for e in paid)
    return Paid(
        shop=s,
        customer_id=c.id,
        amount_paise=amount,
        entry_ids=[e.id for e in paid],
        left_paise=still,
        settled_in=max(0, (now.date() - oldest.date()).days),
    )


# ── adding someone who can't scan ────────────────────────────────────────────


def add_by_name(
    con: Conn,
    shop_id: str,
    name: str,
    tag: str | None,
    now: datetime,
    hindi: Callable[[str], str | None] = lambda _: None,
) -> CustomerRef:
    """Someone with no phone, kept by name like the notebook. His book works; he
    never sees it, and nothing is ever sent to him."""
    shop(con, shop_id)
    name, tag = name.strip(), (tag or "").strip() or None
    if not name:
        raise Conflict("a name is needed")
    cid = customers.add(
        con,
        shop_id,
        name,
        now,
        tag=tag,
        name_hi=hindi(name),
        tag_hi=hindi(tag) if tag else None,
    )
    c = customers.get(con, cid)
    assert c is not None
    return c


def invite(
    con: Conn,
    shop_id: str,
    person_id: str,
    name: str,
    tag: str | None,
    now: datetime,
    hindi: Callable[[str], str | None] = lambda _: None,
) -> CustomerRef:
    """An invitation to his Paytm account. Nothing can be recorded against him
    until he accepts on his own phone."""
    shop(con, shop_id)
    here = customers.at_shop(con, shop_id, person_id)
    if here is not None:
        raise Conflict(
            f"{here.display_name} is already in your book"
            if here.linked
            else f"{here.display_name} is already invited; waiting for their yes"
        )
    tag = (tag or "").strip() or None
    cid = customers.add(
        con,
        shop_id,
        name,
        now,
        person_id=person_id,
        tag=tag,
        name_hi=hindi(name),
        tag_hi=hindi(tag) if tag else None,
    )
    c = customers.get(con, cid)
    assert c is not None
    return c


def _invited(con: Conn, shop_id: str, person_id: UUID) -> CustomerRef:
    c = customers.at_shop(con, shop_id, str(person_id))
    if c is None or c.linked:
        raise NotFound("no invitation from this shop")
    return c


def accept(con: Conn, shop_id: str, person_id: UUID, now: datetime) -> CustomerRef:
    """He said yes to the shop's invite: from now on it can record against him."""
    c = _invited(con, shop_id, person_id)
    customers.link(con, c.id, now)
    out = customers.get(con, c.id)
    assert out is not None
    return out


def decline(con: Conn, shop_id: str, person_id: UUID) -> None:
    """He said no. The shop's row for him goes; nothing was ever recorded on it."""
    c = _invited(con, shop_id, person_id)
    customers.drop_invite(con, c.id)
