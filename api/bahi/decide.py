"""Tonight's decision for every customer who owes, with the figures behind it.

    make decide                       # the demo shop
    uv run python -m bahi.decide

Reads only. The same code the Tomorrow screen and the 11 pm run use
(domain/tonight.py), printed so every hold and send can be checked by hand.
"""

from __future__ import annotations

from collections import Counter

from bahi import clock
from bahi.domain.money import rupees
from bahi.service import tonight
from bahi.store import db
from data.world import HOME, uid

WHY = {
    "past_longest_gap": "past the longest gap ever",
    "inside_gap": "inside own gap",
    "not_confirmed": "waiting for his yes",
    "disputed": "says an entry is wrong",
    "too_new": "too new to read",
    "no_phone": "kept by name, no phone",
    "reminded": "reminded within a gap",
}


def main() -> None:
    with db.connect() as con:
        e = tonight.work_out(con, str(uid("shop", HOME)), clock.now())
    t = e.tonight
    print(f"Tomorrow, {t.for_day:%d %b}: {len(t.sending)} of {t.owing_count}\n")
    for p in t.plans:
        r = p.rhythm
        what = f"send {p.send_at:%H:%M}" if p.send_at else "hold"
        gaps = (
            f"usual {r.median_gap}d, longest {r.max_gap}d, n={r.n}" if r.n else "no gaps"
        )
        print(
            f"  {what:10} {p.display_name:18} {rupees(p.balance_paise):>7}  "
            f"day {p.day:<3} {gaps:32} {WHY[p.why]}"
        )
    print()
    for why, n in Counter(p.why for p in t.plans).most_common():
        print(f"  {n:3}  {WHY[why]}")


if __name__ == "__main__":
    main()
