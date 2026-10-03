"""How long an entry stays claimable. Limitation Act 1963, s.18.

A debt for goods sold can be claimed for three years from the sale, and a written
acknowledgment before that runs out starts a fresh three years. The Act puts no
cap on how many times that can happen, so an app that kept asking could keep a
₹200 debt alive forever. Ours cannot: the database allows one acknowledgment per
entry, so the clock restarts at most once.

This is the product's reading of the rule, used to stop prompting and to show a
debt as expired. It is not legal advice to anyone about their own debt.
"""

from __future__ import annotations

from datetime import date

YEARS = 3


def claimable_until(recorded_on: date, acknowledged_on: date | None) -> date:
    """The last day the entry can be claimed."""
    start = recorded_on if acknowledged_on is None else max(recorded_on, acknowledged_on)
    return _add_years(start, YEARS)


def expired(recorded_on: date, acknowledged_on: date | None, today: date) -> bool:
    return today > claimable_until(recorded_on, acknowledged_on)


def _add_years(d: date, years: int) -> date:
    """Same day and month, `years` later. 29 February becomes 28 February."""
    try:
        return d.replace(year=d.year + years)
    except ValueError:
        return d.replace(year=d.year + years, day=28)
