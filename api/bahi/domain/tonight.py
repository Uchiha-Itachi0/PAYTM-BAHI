"""Tonight: who gets a reminder tomorrow, and why everyone else is left alone.

Pure arithmetic over each customer's own history, the same figures the book
shows. A reminder goes only to someone who is past the longest gap he has ever
had between payments: that is when something has changed, and a message that
asks is worth sending. Everyone else is held, and the reason is named, because
the screen that says who is *not* being messaged is the point of the product.

    past his longest gap          send, at the hour he usually pays
    inside his own gap            hold
    an entry he hasn't said yes to, or one he says is wrong
                                  hold: the chat comes first
    too little history to read    hold
    kept by name only             hold: there is no phone to send to
    reminded within his usual gap hold: one reminder a gap, never a stream

No model decides anything here. The munshi only writes the words of a reminder
this file has already decided to send.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, time, timedelta
from statistics import median_low
from typing import Literal

from bahi.domain.book import Customer, Line, line
from bahi.domain.rhythm import Rhythm

Why = Literal[
    "past_longest_gap",
    "inside_gap",
    "not_confirmed",
    "disputed",
    "too_new",
    "no_phone",
    "reminded",
]

#: A reminder never arrives before this or after LATEST.
EARLIEST = time(9, 0)
LATEST = time(20, 0)
#: When he has never paid, or never at a known time.
USUAL = time(10, 0)
#: A reminder a gap: after one, the next waits at least his usual gap, and at
#: least this many days when his gap is shorter or unknown.
FEWEST_DAYS_BETWEEN = 7


@dataclass(frozen=True, slots=True)
class Plan:
    customer_id: str
    display_name: str
    tag: str | None
    balance_paise: int
    #: Days since he last paid, as the book shows it.
    day: int
    rhythm: Rhythm
    send: bool
    why: Why
    #: The hour a reminder goes out; None when he is held.
    send_at: time | None
    #: When he was last reminded, if ever.
    reminded_on: date | None


@dataclass(frozen=True, slots=True)
class Tonight:
    #: The day the reminders go out.
    for_day: date
    owing_count: int
    #: Everyone who owes something, the ones to send first, then alphabetical.
    plans: tuple[Plan, ...]

    @property
    def sending(self) -> tuple[Plan, ...]:
        return tuple(p for p in self.plans if p.send)


def send_hour(paid_at: Sequence[time]) -> time:
    """The hour he usually pays: the median time of day of his payments, down to
    the half hour, kept between EARLIEST and LATEST. A reminder that arrives when
    he usually has money in hand asks at the right moment; one at midnight chases.
    """
    if not paid_at:
        return USUAL
    minutes = median_low(t.hour * 60 + t.minute for t in paid_at)
    minutes -= minutes % 30
    at = time(minutes // 60, minutes % 60)
    return min(max(at, EARLIEST), LATEST)


def _hold_or_send(
    c: Customer, ln: Line, today: date, reminded_on: date | None
) -> tuple[bool, Why]:
    open_statuses = {e.status for e in c.entries if e.claimable(today)}
    if "disputed" in open_statuses:
        return False, "disputed"
    if c.joined == "linked" and "recorded" in open_statuses:
        return False, "not_confirmed"
    if ln.chip == "new":
        return False, "too_new"
    if ln.chip != "changed":
        return False, "inside_gap"
    if c.joined != "linked":
        return False, "no_phone"
    if reminded_on is not None:
        wait = max(ln.rhythm.median_gap or 0, FEWEST_DAYS_BETWEEN)
        if today - reminded_on < timedelta(days=wait):
            return False, "reminded"
    return True, "past_longest_gap"


def tonight(
    customers: Iterable[Customer],
    today: date,
    paid_at: Mapping[str, Sequence[time]],
    reminded_on: Mapping[str, date],
) -> Tonight:
    """Tomorrow's reminders, decided tonight from the book as it stands today.

    `paid_at`: the time of day of each of his payments, by customer id.
    `reminded_on`: the day each customer was last sent a reminder.
    """
    plans: list[Plan] = []
    for c in customers:
        ln = line(c, today)
        if ln is None:
            continue
        last = reminded_on.get(c.id)
        send, why = _hold_or_send(c, ln, today, last)
        plans.append(
            Plan(
                customer_id=c.id,
                display_name=c.display_name,
                tag=c.tag,
                balance_paise=ln.balance_paise,
                day=ln.day,
                rhythm=ln.rhythm,
                send=send,
                why=why,
                send_at=send_hour(paid_at.get(c.id, ())) if send else None,
                reminded_on=last,
            )
        )
    plans.sort(key=lambda p: (not p.send, p.display_name.casefold()))
    return Tonight(
        for_day=today + timedelta(days=1),
        owing_count=len(plans),
        plans=tuple(plans),
    )
