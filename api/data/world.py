"""The fixed facts of the synthetic world. Change one and every figure moves.

Everything the seed produces is a function of these constants. A fixed random
seed, a fixed "today" and uuid5 ids mean two runs build the same database byte
for byte, which is the only way a demo can be rehearsed rather than attempted.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from zoneinfo import ZoneInfo

SEED = 20261003

#: The day of the hackathon. Every "day N" on every screen is counted to here.
TODAY = date(2026, 10, 3)

#: Six months of history before it.
START = date(2026, 4, 3)

IST = ZoneInfo("Asia/Kolkata")

#: Fixed namespace, so ids are stable across machines and reruns. Random uuids
#: would make "identical on every rebuild" false on the first rerun.
NS = uuid.UUID("f4b9939b-2f16-43cb-ab93-16b3fc6cae02")

#: key -> (name, locality). The first is the shop the demo runs in; the other two
#: exist only so one customer's "you owe across 3 shops" is real data.
SHOPS = {
    "ramesh": ("Ramesh Kirana Store", "Kurla West"),
    "salim": ("Salim Medical", "Kurla West"),
    "gupta": ("Gupta Dairy", "Kurla West"),
}
HOME = "ramesh"


def uid(*parts: str) -> uuid.UUID:
    return uuid.uuid5(NS, ":".join(parts))


def at(day: date, hour: int, minute: int = 0, second: int = 0) -> datetime:
    """A moment on `day`, in Kurla."""
    return datetime(day.year, day.month, day.day, hour, minute, second, tzinfo=IST)
