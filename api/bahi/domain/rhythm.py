"""A customer's own payment rhythm, from the days he paid. Arithmetic only.

"Sharma pays every 9 days" is the median of the gaps between the days he paid.
No model and no score: a list of dates goes in, three whole numbers come out, and
each one can be checked by hand against his ledger.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from itertools import pairwise
from statistics import median_low

#: Fewest gaps we will read a rhythm from. Two gaps are an anecdote.
MIN_GAPS = 3


@dataclass(frozen=True, slots=True)
class Rhythm:
    #: How many gaps the figures below were measured over.
    n: int
    #: His usual gap, in days. median_low, so it is always a gap he actually had
    #: (never a half-day), and one festival month cannot drag it the way it would
    #: drag a mean.
    median_gap: int | None
    #: The longest he has ever gone between payments.
    max_gap: int | None
    last_paid: date | None
    #: Days since he last paid. None if he never has.
    day: int | None

    @property
    def enough(self) -> bool:
        return self.n >= MIN_GAPS


def rhythm(paid_on: Iterable[date], today: date) -> Rhythm:
    """His rhythm as of `today`, from every day he paid.

    Gaps are between distinct *days*. One UPI payment that clears three entries is
    three repayment rows with the same time; counting them as three payments would
    put two zero-day gaps into his history and halve his median.
    """
    days = sorted({d for d in paid_on if d <= today})
    if not days:
        return Rhythm(n=0, median_gap=None, max_gap=None, last_paid=None, day=None)

    gaps = [(later - earlier).days for earlier, later in pairwise(days)]
    last = days[-1]
    return Rhythm(
        n=len(gaps),
        median_gap=median_low(gaps) if gaps else None,
        max_gap=max(gaps) if gaps else None,
        last_paid=last,
        day=(today - last).days,
    )
