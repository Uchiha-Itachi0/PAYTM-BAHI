"""How each customer pays (domain/pattern.py), from the book, his payment times,
and the promises memory kept. For the munshi's card, the customer's page, and the
sentence Cognee keeps about him.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date

from bahi import clock
from bahi.domain.pattern import Pattern, pattern
from bahi.service.models import PatternOut
from bahi.store import book as book_store
from bahi.store import memories
from bahi.store.db import Conn


def of_shop(con: Conn, shop_id: str, today: date) -> dict[str, Pattern]:
    return _patterns(con, shop_id, None, today)


def of_customer(con: Conn, shop_id: str, customer_id: str, today: date) -> Pattern:
    found = _patterns(con, shop_id, customer_id, today)
    return found.get(customer_id) or pattern((), (), today)


def _patterns(
    con: Conn, shop_id: str, customer_id: str | None, today: date
) -> dict[str, Pattern]:
    times = book_store.paid_times(con, shop_id)
    counts = book_store.disputes(con, shop_id, customer_id)
    promised: dict[str, list[tuple[date, date]]] = defaultdict(list)
    for m in memories.of_shop(con, shop_id, "promise"):
        if m.until is not None:
            said_on = m.remembered_at.astimezone(clock.IST).date()
            promised[m.customer_id].append((said_on, m.until))
    return {
        c.id: pattern(
            c.paid_on,
            times.get(c.id, []),
            today,
            promises=promised.get(c.id, []),
            entries=counts.get(c.id, (0, 0))[0],
            disputed=counts.get(c.id, (0, 0))[1],
        )
        for c in book_store.load(con, shop_id, customer_id)
    }


def out(p: Pattern) -> PatternOut:
    r = p.rhythm
    return PatternOut(
        payments=r.n + 1 if r.last_paid else 0,
        usual_gap=r.median_gap,
        usually_within=p.usually_within,
        longest_gap=r.max_gap,
        recent_gaps=list(p.recent_gaps),
        last_paid=r.last_paid,
        expect_from=p.expect_from,
        expect_by=p.expect_by,
        now=p.now,
        usual_time=p.usual_time.strftime("%H:%M") if p.usual_time else None,
        promised=p.promised,
        promises_due=p.promises_due,
        promises_kept=p.promises_kept,
        entries=p.entries,
        disputed=p.disputed,
    )


def _day(d: date) -> str:
    return f"{d.day} {d:%b}"


def facts(p: Pattern, said: int) -> dict[str, object]:
    """His pattern as the munshi is shown it: the book's figures, in words it can
    say. `said`: what memory kept from his chat (complaints, requests…)."""
    r = p.rhythm
    out: dict[str, object] = {"payments_so_far": r.n + 1 if r.last_paid else 0}
    if r.last_paid:
        out["last_paid"] = _day(r.last_paid)
    if r.median_gap is not None:
        out["usually_pays_every_days"] = r.median_gap
        out["8_in_10_times_within_days"] = p.usually_within
        out["longest_gap_days"] = r.max_gap
        out["latest_gaps_days"] = list(p.recent_gaps)
    if p.expect_from and p.expect_by:
        window = f"{_day(p.expect_from)} to {_day(p.expect_by)}"
        if p.now == "early":
            out["likely_next"] = window
            out["right_now"] = "not due yet by his own rhythm"
        elif p.now == "due":
            out["likely_next"] = f"any day now, by {_day(p.expect_by)} by his rhythm"
            out["right_now"] = "due about now, by his own rhythm"
        else:  # a window that has passed is not a guess for the future
            out["likely_next"] = "no date from his rhythm: he is past it"
            out["right_now"] = (
                f"late by his own rhythm: {r.day} days since he paid; his usual "
                f"window ({window}) has passed"
            )
    else:
        out["likely_next"] = "too little history to tell"
    if p.usual_time:
        out["usually_pays_around"] = p.usual_time.strftime("%I:%M %p").lstrip("0")
    if p.promised:
        out["promised_to_pay_by"] = _day(p.promised)
    if p.promises_due:
        out["promises_kept"] = f"{p.promises_kept} of {p.promises_due}"
    if p.entries:
        out["entries_he_said_were_wrong"] = f"{p.disputed} of {p.entries}"
    if said:
        out["things_he_said_remembered"] = said
    return out


def sentence(p: Pattern, who: str) -> str:
    """His pattern as one sentence for Cognee: what doesn't go stale. Dates he
    paid, never "days ago", and no window for his next payment (a guess about
    the future is worked out when it is asked for: facts, expected)."""
    r = p.rhythm
    if not r.last_paid:
        parts = [f"Payment pattern of {who}: has not paid anything yet."]
    else:
        parts = [f"Payment pattern of {who}:"]
        parts.append(
            f"paid on {r.n + 1} days, last on {_day(r.last_paid)} {r.last_paid.year}."
        )
        if r.median_gap is not None:
            parts.append(
                f"Usually pays every {r.median_gap} days; 8 in 10 times within "
                f"{p.usually_within} days; longest gap {r.max_gap} days; latest gaps "
                + ", ".join(str(g) for g in p.recent_gaps)
                + " days."
            )
        if p.usual_time:
            parts.append(f"Usually pays around {p.usual_time:%H:%M}.")
    if p.promises_due:
        parts.append(
            f"Kept {p.promises_kept} of {p.promises_due} promises to pay by a day."
        )
    if p.entries:
        parts.append(f"Said {p.disputed} of {p.entries} entries were wrong.")
    return " ".join(parts)
