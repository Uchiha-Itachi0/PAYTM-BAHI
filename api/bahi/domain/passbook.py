"""The thread as a passbook: what he owed just before something happened, and
just after. Arithmetic only, over the book's own history, like book.py.

Ganesh owed ₹80; ₹100 more was written and he said yes, so ₹180; he paid ₹80
by UPI, so ₹100; then ₹100 in cash, so nothing. Each of those moments shows
both figures, so the chat reads like a passbook instead of a list of events.

What counts is what book.py counts: what he agreed to.

- An entry counts from the moment it is agreed: his yes, or the moment it is
  written for someone kept by name only, who has no phone to say it on. Paying
  it before saying yes counts as agreeing to it.
- It stops counting when it is corrected (the correction is written) or taken
  back. A correction counts on its own, from its own yes.
- Each payment counts from when it was made, against the entry it names.

An entry waiting for his yes, or one he says is wrong, is never in it.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class Line:
    entry_id: str
    amount_paise: int
    #: When it started to count. None: it never has.
    agreed_at: datetime | None
    #: When it stopped counting: corrected or taken back. None: it still does.
    gone_at: datetime | None


@dataclass(frozen=True, slots=True)
class Payment:
    entry_id: str
    amount_paise: int
    paid_at: datetime


@dataclass(frozen=True, slots=True)
class Moment:
    """What he owed just before a moment, and just after it."""

    before_paise: int
    after_paise: int


def agreed_at(
    *,
    acknowledged_at: datetime | None,
    recorded_at: datetime,
    name_only: bool,
    first_paid_at: datetime | None,
) -> datetime | None:
    """When an entry started to count: the earliest of his yes, a payment
    against it, and (for someone kept by name only) its writing."""
    times = [t for t in (acknowledged_at, first_paid_at) if t is not None]
    if name_only:
        times.append(recorded_at)
    return min(times) if times else None


def owed(
    lines: Iterable[Line], payments: Iterable[Payment], at: datetime, *, before: bool
) -> int:
    """What he owed at `at`: just before it, or just after it."""

    def by(t: datetime) -> bool:
        return t < at if before else t <= at

    paid: dict[str, int] = {}
    for p in payments:
        if by(p.paid_at):
            paid[p.entry_id] = paid.get(p.entry_id, 0) + p.amount_paise
    total = 0
    for ln in lines:
        if ln.agreed_at is None or not by(ln.agreed_at):
            continue
        if ln.gone_at is not None and by(ln.gone_at):
            continue
        total += max(0, ln.amount_paise - paid.get(ln.entry_id, 0))
    return total


def moment(lines: list[Line], payments: list[Payment], at: datetime) -> Moment:
    return Moment(
        before_paise=owed(lines, payments, at, before=True),
        after_paise=owed(lines, payments, at, before=False),
    )
