"""The shopkeeper's book: who owes him, how much, and where each person is in
their own rhythm.

What someone owes is what he has agreed to: an entry counts once he has said yes
on his phone, or straight away for someone kept by name only, who has no phone to
say it on. An entry on his phone he hasn't answered is *waiting*; one he said is
wrong is *disputed*. Both are shown, apart, and neither is in the total.

Pure. The store layer loads rows into the dataclasses below; this file does the
arithmetic; the contract and the API only ever serialise what comes out. No
figure a screen shows is worked out anywhere else.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from typing import Literal

from bahi.domain.limitation import expired
from bahi.domain.rhythm import Rhythm, rhythm

Joined = Literal["linked", "invited", "name_only"]

#: The only words a status may use. A type, so "Overdue" or "Defaulter" cannot
#: be written anywhere downstream without failing the type check.
#:   on_rhythm      inside his own usual gap, whatever that gap is
#:   changed        past the longest gap he has ever had
#:   not_confirmed  he has an entry he has not said yes to
#:   new            not enough history to know his rhythm yet
Chip = Literal["on_rhythm", "changed", "not_confirmed", "new"]

#: Entries that still carry a claim. Corrected entries count for nothing, and
#: settled ones are paid.
OPEN = frozenset({"recorded", "confirmed", "disputed"})


@dataclass(frozen=True, slots=True)
class Entry:
    id: str
    amount_paise: int
    paid_paise: int
    status: str
    recorded_on: date
    acknowledged_on: date | None

    @property
    def owed_paise(self) -> int:
        return self.amount_paise - self.paid_paise

    def claimable(self, today: date) -> bool:
        """Still owed, and not past the limitation line."""
        return (
            self.status in OPEN
            and self.owed_paise > 0
            and not expired(self.recorded_on, self.acknowledged_on, today)
        )


@dataclass(frozen=True, slots=True)
class Customer:
    id: str
    display_name: str
    tag: str | None
    joined: Joined
    entries: tuple[Entry, ...]
    #: Every day he paid anything, at this shop.
    paid_on: tuple[date, ...]


@dataclass(frozen=True, slots=True)
class Standing:
    """What he owes, split by what he has said about it. Claimable entries only."""

    #: He said yes to it, or he is kept by name only and can't be asked.
    accepted_paise: int
    #: On his phone, not answered yet.
    waiting_paise: int
    #: He said it is wrong.
    disputed_paise: int

    @property
    def any_paise(self) -> int:
        return self.accepted_paise + self.waiting_paise + self.disputed_paise


def standing(customer: Customer, today: date) -> Standing:
    accepted = waiting = disputed = 0
    for e in customer.entries:
        if not e.claimable(today):
            continue
        if e.status == "disputed":
            disputed += e.owed_paise
        elif e.status == "recorded" and customer.joined == "linked":
            waiting += e.owed_paise
        else:
            accepted += e.owed_paise
    return Standing(accepted, waiting, disputed)


@dataclass(frozen=True, slots=True)
class Line:
    customer_id: str
    display_name: str
    tag: str | None
    joined: Joined
    #: What he has agreed he owes (Standing.accepted_paise).
    balance_paise: int
    #: Written and on his phone, not answered yet; not in the balance.
    waiting_paise: int
    #: He said it is wrong; not in the balance.
    disputed_paise: int
    #: Days since he last paid, or since his oldest open entry if he never has.
    day: int
    chip: Chip
    rhythm: Rhythm


@dataclass(frozen=True, slots=True)
class Book:
    today: date
    #: Everyone in the book: linked or kept by name. Invitations not yet accepted
    #: are not in anyone's book.
    customer_count: int
    invited_count: int
    #: Customers who owe something they have agreed to.
    owing_count: int
    #: What customers have agreed they owe. Entries waiting for a yes, or said to
    #: be wrong, are not in it: they are counted apart below, so the shopkeeper
    #: still sees his own record.
    outstanding_paise: int
    waiting_paise: int
    disputed_paise: int
    #: Owing customers only, alphabetical. Never sorted by how much anyone owes.
    lines: tuple[Line, ...]


def chip(customer: Customer, open_entries: list[Entry], r: Rhythm, day: int) -> Chip:
    unanswered = any(e.status in ("recorded", "disputed") for e in open_entries)
    if customer.joined == "linked" and unanswered:
        return "not_confirmed"
    if not r.enough or r.max_gap is None:
        return "new"
    if day > r.max_gap:
        return "changed"
    return "on_rhythm"


def line(customer: Customer, today: date) -> Line | None:
    """His line in the book, or None if nothing claimable is open: agreed,
    waiting or disputed."""
    open_entries = [e for e in customer.entries if e.claimable(today)]
    s = standing(customer, today)
    if s.any_paise == 0:
        return None

    r = rhythm(customer.paid_on, today)
    oldest = min(e.recorded_on for e in open_entries)
    day = r.day if r.day is not None else (today - oldest).days
    return Line(
        customer_id=customer.id,
        display_name=customer.display_name,
        tag=customer.tag,
        joined=customer.joined,
        balance_paise=s.accepted_paise,
        waiting_paise=s.waiting_paise,
        disputed_paise=s.disputed_paise,
        day=day,
        chip=chip(customer, open_entries, r, day),
        rhythm=r,
    )


def book(customers: Iterable[Customer], today: date) -> Book:
    everyone = list(customers)
    lines = sorted(
        (ln for c in everyone if (ln := line(c, today)) is not None),
        key=lambda ln: ln.display_name.casefold(),
    )
    return Book(
        today=today,
        customer_count=sum(1 for c in everyone if c.joined != "invited"),
        invited_count=sum(1 for c in everyone if c.joined == "invited"),
        owing_count=sum(1 for ln in lines if ln.balance_paise > 0),
        outstanding_paise=sum(ln.balance_paise for ln in lines),
        waiting_paise=sum(ln.waiting_paise for ln in lines),
        disputed_paise=sum(ln.disputed_paise for ln in lines),
        lines=tuple(lines),
    )
