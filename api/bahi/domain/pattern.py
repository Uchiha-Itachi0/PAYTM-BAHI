"""How a customer pays, from his own book: when he is likely to pay next, and how
he has kept his word. Arithmetic only, like rhythm.py: every figure can be checked
by hand against his ledger.

    usual gap        the median of the gaps between the days he paid
    usually within   8 in 10 of his gaps were this long or shorter
    likely next      his last payment + his usual gap, and nearly always by his
                     last payment + usually within
    now              early (before that), due (inside it), late (past it)
    promises kept    a promise to pay by a day, whose day has passed, with a
                     payment between the day he said it and that day
    disputed         entries he said were wrong, of all the entries written for him

The munshi turns this into a guess in words ("मेरे हिसाब से 7-9 तारीख के बीच");
Cognee keeps it as a sentence to find by meaning. Neither works anything out.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date, time, timedelta
from itertools import pairwise
from math import ceil
from statistics import median_low
from typing import Literal

from bahi.domain.rhythm import Rhythm, rhythm

Now = Literal["early", "due", "late", "unknown"]

#: "Usually within": the gap this share of his gaps were at or under.
USUALLY = 0.8
#: How many of his latest gaps are shown, to see if he is slowing down.
RECENT = 4


@dataclass(frozen=True, slots=True)
class Pattern:
    rhythm: Rhythm
    usually_within: int | None
    #: His latest gaps, oldest first.
    recent_gaps: tuple[int, ...]
    expect_from: date | None
    expect_by: date | None
    now: Now
    #: The time of day he usually pays, to the half hour; None if unknown.
    usual_time: time | None
    #: The day of a promise still ahead of him, if any.
    promised: date | None
    promises_due: int
    promises_kept: int
    entries: int
    disputed: int


def usual_time(paid_at: Sequence[time]) -> time | None:
    if not paid_at:
        return None
    minutes = median_low(t.hour * 60 + t.minute for t in paid_at)
    minutes -= minutes % 30
    return time(minutes // 60, minutes % 60)


def pattern(
    paid_on: Iterable[date],
    paid_at: Sequence[time],
    today: date,
    *,
    promises: Iterable[tuple[date, date]] = (),
    entries: int = 0,
    disputed: int = 0,
) -> Pattern:
    """His pattern as of `today`. `promises`: (the day he said it, the day he
    promised to pay by)."""
    days = sorted({d for d in paid_on if d <= today})
    r = rhythm(days, today)
    gaps = sorted((b - a).days for a, b in pairwise(days))
    within = gaps[max(ceil(USUALLY * len(gaps)) - 1, 0)] if gaps else None

    expect_from = expect_by = None
    now: Now = "unknown"
    if r.enough and r.last_paid and r.median_gap is not None and within is not None:
        expect_from = r.last_paid + timedelta(days=r.median_gap)
        expect_by = r.last_paid + timedelta(days=within)
        now = "early" if today < expect_from else "due" if today <= expect_by else "late"

    said = list(promises)
    due = [(on, by) for on, by in said if by < today]
    kept = sum(1 for on, by in due if any(on <= d <= by for d in days))
    ahead = [by for _, by in said if by >= today]

    latest = [(b - a).days for a, b in pairwise(days)][-RECENT:]
    return Pattern(
        rhythm=r,
        usually_within=within,
        recent_gaps=tuple(latest),
        expect_from=expect_from,
        expect_by=expect_by,
        now=now,
        usual_time=usual_time(paid_at),
        promised=min(ahead) if ahead else None,
        promises_due=len(due),
        promises_kept=kept,
        entries=entries,
        disputed=disputed,
    )
