"""The family circle, one function per thing a member can do.

Like the ledger: each takes a connection and the time, checks the rules, and calls
the store, and none of them commits. The ledger calls `on_agreed` when an entry is
agreed, so this module imports nothing from the ledger (or anything that does).

The rules are in `domain/circle.py`. What this layer keeps on top of them:

- Every call names the person acting, and only a member can see or touch a
  circle. Only the debtor can put their entry on a list or take it off.
- Nothing here is ever shown to a shop. A payment by a member reaches the shop's
  thread as the same UPI payment card as any other, against the debtor's entry.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta

from bahi import paytm
from bahi.domain import book as book_domain
from bahi.domain import circle as rules
from bahi.domain import wording
from bahi.domain.lifecycle import move
from bahi.domain.limitation import expired
from bahi.service.errors import Conflict, Forbidden, NotFound
from bahi.store import book as book_store
from bahi.store import circles, customers, entries, threads
from bahi.store.circles import Circle
from bahi.store.db import Conn
from bahi.store.entries import EntryRef

#: Who a person is called when Paytm has no name for them.
SOMEONE = "A member"


def names(con: Conn, person_ids: list[str]) -> dict[str, str]:
    """The name on each person's Paytm account: how the circle knows them."""
    found = paytm.accounts(con, sorted(set(person_ids)))
    return {p: found[p].name if p in found else SOMEONE for p in person_ids}


def is_open(e: EntryRef, today: date) -> bool:
    """Agreed, something left to pay, and still claimable: what a circle can pay."""
    return (
        e.status == "confirmed"
        and e.amount_paise > e.paid_paise
        and not expired(
            e.recorded_at.date(),
            e.acknowledged_at.date() if e.acknowledged_at else None,
            today,
        )
    )


def member_of(con: Conn, circle_id: str, person_id: str) -> Circle:
    """The circle, if this person is in it now."""
    c = circles.get(con, circle_id)
    if c is None:
        raise NotFound(f"no circle {circle_id}")
    if not circles.is_member(con, circle_id, person_id):
        raise Forbidden("you are not in this circle")
    return c


# ── circles ──────────────────────────────────────────────────────────────────


def create(
    con: Conn, person_id: str, name: str, phones: list[str], now: datetime
) -> Circle:
    """A circle, made by this person, with the people behind these mobile numbers.

    Each number must belong to a Paytm account; the number finds it and is not
    kept. The maker is in it too. Everyone added is told on their phone.
    """
    name = " ".join(name.split())
    if not name:
        raise Conflict("give the circle a name")
    if paytm.account(con, person_id) is None:
        raise Conflict("scan a shop's udhaar QR first: that makes your Paytm account")
    people: list[str] = []
    for phone in phones:
        found = _person_by_phone(con, phone)
        if found != person_id and found not in people:
            people.append(found)
    if not people:
        raise Conflict("add at least one other person by their mobile number")
    if len(people) + 1 > rules.MOST_MEMBERS:
        raise Conflict(f"a circle holds at most {rules.MOST_MEMBERS} people")

    circle_id = circles.create(con, name, person_id, now)
    circles.add_member(con, circle_id, person_id, person_id, now)
    maker = names(con, [person_id])[person_id]
    for i, p in enumerate(people, start=1):
        # Just after the maker, in the order given: the members list reads so.
        circles.add_member(con, circle_id, p, person_id, now + timedelta(microseconds=i))
        circles.notify(
            con, p, "added", wording.circle_added(maker, name), now, circle_id=circle_id
        )
    made = circles.get(con, circle_id)
    assert made is not None
    return made


def add_member(
    con: Conn, circle_id: str, person_id: str, phone: str, now: datetime
) -> Circle:
    """Anyone in the circle adds one more person, by their mobile number.

    The same rules as making it: the number must find a Paytm account and is not
    kept, nobody is in it twice, and it holds at most MOST_MEMBERS. The new member
    is told on their phone. Their own setting (or the default) decides where their
    next udhaar goes; nothing they already owe is put on the list for them.
    """
    c = member_of(con, circle_id, person_id)
    found = _person_by_phone(con, phone)
    if circles.is_member(con, circle_id, found):
        who = names(con, [found])[found]
        raise Conflict(f"{who} is already in {c.name}")
    if len(circles.members(con, circle_id)) + 1 > rules.MOST_MEMBERS:
        raise Conflict(f"a circle holds at most {rules.MOST_MEMBERS} people")
    circles.add_member(con, circle_id, found, person_id, now)
    by = names(con, [person_id])[person_id]
    circles.notify(
        con, found, "added", wording.circle_added(by, c.name), now, circle_id=circle_id
    )
    return c


def _person_by_phone(con: Conn, phone: str) -> str:
    """The person behind a mobile number's Paytm account. The number is not kept."""
    a = paytm.by_phone(con, phone)
    if a is None:
        raise Conflict(f"no Paytm account has the number {phone.strip()}")
    return a.person_id


def set_on_udhaar(con: Conn, person_id: str, on_udhaar: str, now: datetime) -> None:
    """What should happen to their next udhaar: to their circle, or kept."""
    if on_udhaar not in ("circle", "self"):
        raise Conflict("choose circle or self")
    circles.choose(con, person_id, on_udhaar, now)


def leave(con: Conn, circle_id: str, person_id: str, now: datetime) -> list[str]:
    """They leave. Their entries come off the list at once, so nobody else can pay
    them; the debt is theirs, as it always was. Returns the entries taken off."""
    member_of(con, circle_id, person_id)
    circles.leave(con, circle_id, person_id, now)
    taken = circles.withdraw_all(con, circle_id, person_id, "left", now)
    circles.done_about(con, taken, now)
    circles.done_in_circle(con, circle_id, person_id, now)
    return taken


# ── the list ─────────────────────────────────────────────────────────────────


def on_agreed(con: Conn, e: EntryRef, now: datetime) -> None:
    """Their yes is in: the entry goes where their setting says. One circle, onto
    its list; several, a note asking which; their setting says keep it, a note
    saying so, with the choice to add it anyway. In no circle, nothing."""
    if e.person_id is None or e.status != "confirmed":
        return
    mine = circles.of_person(con, e.person_id)
    r = rules.route(circles.chosen(con, e.person_id), [c.id for c in mine])
    if r.kind == "share":
        c = next(c for c in mine if c.id == r.circle_id)
        _put_on_list(con, c, e, e.person_id, now)
    elif r.kind == "choose":
        body = wording.circle_choose(e.shop_name, e.amount_paise)
        circles.notify(con, e.person_id, "choose", body, now, entry_id=e.id)
    elif r.kind == "keep":
        body = wording.circle_kept(e.shop_name, e.amount_paise)
        circles.notify(con, e.person_id, "kept", body, now, entry_id=e.id)


def share(
    con: Conn, circle_id: str, entry_id: str, person_id: str, now: datetime
) -> EntryRef:
    """ "Add to circle": the debtor puts one of their open entries on a list."""
    c = member_of(con, circle_id, person_id)
    e = entries.get(con, entry_id)
    if e is None:
        raise NotFound(f"no entry {entry_id}")
    if e.person_id != person_id:
        raise Forbidden("only the person who took this udhaar can add it to a circle")
    if not is_open(e, now.date()):
        raise Conflict("only udhaar you said yes to, with something left to pay, can go")
    already = circles.on_a_list(con, e.id)
    if already is not None:
        on = circles.get(con, already.circle_id)
        raise Conflict(f"this udhaar is already on {on.name if on else 'a'}'s list")
    _put_on_list(con, c, e, person_id, now)
    return e


def take_back(
    con: Conn, circle_id: str, entry_id: str, person_id: str, now: datetime
) -> None:
    """The debtor takes their entry off the list: from now on only they pay it."""
    member_of(con, circle_id, person_id)
    e = entries.get(con, entry_id)
    if e is None:
        raise NotFound(f"no entry {entry_id}")
    if e.person_id != person_id:
        raise Forbidden("only the person who took this udhaar can take it back")
    on = circles.on_a_list(con, e.id)
    if on is None or on.circle_id != circle_id:
        raise Conflict("this udhaar is not on this circle's list")
    circles.withdraw(con, e.id, "taken_back", now)
    circles.done_about(con, [e.id], now)


def _put_on_list(con: Conn, c: Circle, e: EntryRef, by: str, now: datetime) -> None:
    """Onto the list, the debtor told, and everyone else asked."""
    debtor = e.person_id
    assert debtor is not None
    circles.done_about(con, [e.id], now)
    circles.share(con, c.id, e.id, by, now)
    shared = wording.circle_shared(e.shop_name, e.amount_paise, c.name)
    circles.notify(con, debtor, "shared", shared, now, circle_id=c.id, entry_id=e.id)
    who = names(con, [debtor])[debtor]
    help_body = wording.circle_help(who, e.shop_name, e.amount_paise, c.name)
    for m in circles.members(con, c.id):
        if m.person_id != debtor:
            circles.notify(
                con, m.person_id, "help", help_body, now, circle_id=c.id, entry_id=e.id
            )


# ── paying ───────────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class Paid:
    circle: Circle
    entry: EntryRef
    amount_paise: int
    #: Who paid: the member, or the debtor themselves.
    payer_name: str


def pay(
    con: Conn,
    circle_id: str,
    entry_id: str,
    payer: str,
    now: datetime,
    amount_paise: int | None = None,
) -> Paid:
    """A member pays an entry on the list by UPI, all of what is left or a part.

    The money goes to the shop; the payment names the debtor's entry and who paid.
    Nobody owes the payer anything. The shop's thread gets the same payment card
    as any UPI payment, and the debtor a note saying who paid.
    """
    c = circles.get(con, circle_id)
    if c is None:
        raise NotFound(f"no circle {circle_id}")
    member = circles.is_member(con, circle_id, payer)
    circles.lock_entry(con, entry_id)
    e = entries.get(con, entry_id)
    if e is None:
        raise NotFound(f"no entry {entry_id}")
    listed = circles.on_a_list(con, e.id)
    left = e.amount_paise - e.paid_paise
    amount = left if amount_paise is None else amount_paise
    why = rules.why_not_pay(
        payer_is_member=member,
        on_the_list=listed is not None and listed.circle_id == circle_id,
        agreed=is_open(e, now.date()),
        left_paise=left,
        amount_paise=amount,
    )
    if why is not None:
        raise Forbidden(why) if not member else Conflict(why)
    debtor = e.person_id
    assert debtor is not None
    entries.pay(con, e.id, amount, "upi", now, paid_by=rules.paid_by(payer, debtor))
    if amount == left:
        entries.set_status(con, e.id, move(e.status, "settle"))
    _payment_card(con, e, amount, now)
    payer_name = names(con, [payer])[payer]
    if payer != debtor:
        body = wording.circle_paid(payer_name, amount, e.shop_name)
        circles.notify(con, debtor, "paid", body, now, circle_id=c.id, entry_id=e.id)
    after = entries.get(con, e.id)
    assert after is not None
    return Paid(circle=c, entry=after, amount_paise=amount, payer_name=payer_name)


def _payment_card(con: Conn, e: EntryRef, amount_paise: int, now: datetime) -> None:
    """The line in the debtor's thread with the shop, as for any UPI payment: the
    amount and what is still open there. Never who paid, never the circle."""
    c = customers.get(con, e.customer_id)
    if c is None or c.joined != "linked":
        return
    found = book_store.load(con, e.shop_id, e.customer_id)
    ln = book_domain.line(found[0], now.date()) if found else None
    still = ln.balance_paise if ln else 0
    body = wording.paid(amount_paise, "upi", still)
    threads.post(con, e.customer_id, "bahi", "entry", body, now, entry_id=e.id)
