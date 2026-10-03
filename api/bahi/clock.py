"""What time it is, for the product.

The seeded world is pinned to 3 October 2026, the day of the hackathon. Anything
written live has to land in that same world, or a confirmation made during a
rehearsal would sit a week *before* the seed's own entries and every "day N"
would be wrong.

So by default the clock keeps the real time of day and pins the date to
BAHI_TODAY. On 3 October the two agree anyway. Set BAHI_TODAY=real for a clock
with no pinning at all.
"""

from __future__ import annotations

import os
from datetime import date, datetime
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")

#: The seed's "today". data/world.py reads it from here, so there is one copy.
DEMO_TODAY = date(2026, 10, 3)


def now() -> datetime:
    real = datetime.now(IST)
    pinned = os.environ.get("BAHI_TODAY", DEMO_TODAY.isoformat())
    if pinned == "real":
        return real
    day = date.fromisoformat(pinned)
    return real.replace(year=day.year, month=day.month, day=day.day)


def today() -> date:
    return now().date()
