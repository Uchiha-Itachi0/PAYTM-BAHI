"""
Seeds Postgres: one kirana with 60 udhaar customers and six months of history,
plus two small shops that exist only so one customer's cross-shop total is real.

Deterministic. SEED, TODAY and uuid5 ids (data/world.py) mean every run builds the
same rows, and `plan()` can be called twice in a test and compared.

The cast in data/personas.py drives the demo. Everyone else is generated around
them from ordinary habits, and generated to be *inside* their own rhythm, so the
only people the book shows as "changed" are the four written in on purpose.

How one customer's history is built:
  1. His payment days come from his gaps, counted back from TODAY - day.
  2. Between two payment days he buys a few times; the next payment clears all
     of it. One repayment row per entry, all at the same moment, because a
     payment names the entries it pays.
  3. What he bought since his last payment is still open today.
  4. A linked customer confirms each entry seconds after it is recorded, at the
     counter. A customer kept by name only never can.

Money is integer paise throughout. Nothing here is a float that reaches Postgres.

    uv run python -m data.generate
"""

from __future__ import annotations

import random
import time
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any

from bahi.domain.money import rupees
from data import db
from data.personas import CAST, CROWD, Open, Persona
from data.world import HOME, SEED, SHOPS, START, TODAY, at, uid

#: The usual gap for a generated customer is drawn from this, in days. Weighted
#: toward weekly and fortnightly, with a few who settle once a month.
HABITS = (3, 4, 5, 6, 7, 7, 7, 8, 9, 10, 10, 12, 14, 14, 15, 15, 20, 21, 30)

#: Of the generated customers, how many owe something today. With the eleven
#: owing members of the cast that makes 38 of 60.
CROWD_SIZE = 47
CROWD_OWING = 27

NOTES = (None,) * 7 + ("Atta", "Doodh", "Chawal", "Dal", "Tel", "Sabun", "Chai patti")

Row = tuple[Any, ...]


@dataclass
class Plan:
    shops: list[Row] = field(default_factory=list)
    customers: list[Row] = field(default_factory=list)
    entries: list[Row] = field(default_factory=list)
    acknowledgments: list[Row] = field(default_factory=list)
    repayments: list[Row] = field(default_factory=list)
    threads: list[Row] = field(default_factory=list)
    messages: list[Row] = field(default_factory=list)


class Builder:
    """Appends rows to a Plan and hands out stable ids."""

    def __init__(self, rng: random.Random) -> None:
        self.rng = rng
        self.plan = Plan()
        self._n: dict[str, int] = {}

    def _next(self, key: str) -> int:
        self._n[key] = self._n.get(key, 0) + 1
        return self._n[key]

    def shop(self, key: str) -> uuid.UUID:
        sid = uid("shop", key)
        name, locality = SHOPS[key]
        self.plan.shops.append((sid, name, locality, at(START, 8)))
        return sid

    def customer(
        self,
        shop: str,
        key: str,
        name: str,
        tag: str | None,
        *,
        person: str | None,
        added_at: datetime,
        linked_at: datetime | None,
    ) -> uuid.UUID:
        cid = uid("customer", shop, key)
        pid = uid("person", person) if person else None
        self.plan.customers.append(
            (cid, uid("shop", shop), pid, name, tag, added_at, linked_at)
        )
        return cid

    def entry(
        self,
        shop: str,
        who: str,
        cid: uuid.UUID,
        paise: int,
        status: str,
        recorded_at: datetime,
        *,
        note: str | None = None,
        spoken: str | None = None,
        corrects: uuid.UUID | None = None,
    ) -> uuid.UUID:
        eid = uid("entry", shop, who, str(self._next(f"entry:{shop}:{who}")))
        self.plan.entries.append(
            (eid, cid, paise, note, spoken, status, corrects, recorded_at)
        )
        return eid

    def ack(self, shop: str, eid: uuid.UUID, paise: int, when: datetime) -> None:
        wording = f"Yes, I owe {rupees(paise)} to {SHOPS[shop][0]}"
        self.plan.acknowledgments.append((uid("ack", str(eid)), eid, wording, when))

    def pay(self, eid: uuid.UUID, paise: int, method: str, when: datetime) -> None:
        self.plan.repayments.append((uid("pay", str(eid)), eid, paise, method, when))


# ── one customer's history ───────────────────────────────────────────────────


def amount(rng: random.Random, ticket: int) -> int:
    """A purchase near his usual ticket, in whole tens of rupees, as paise."""
    rs = max(20, round(ticket * rng.uniform(0.4, 2.0) / 10) * 10)
    return rs * 100


def payment_days(p: Persona) -> list[date]:
    last = TODAY - timedelta(days=p.day)
    days = [last]
    for gap in reversed(p.gaps):
        days.insert(0, days[0] - timedelta(days=gap))
    return days


def history(b: Builder, shop: str, p: Persona, cid: uuid.UUID, linked: bool) -> None:
    rng = b.rng
    pays = payment_days(p)
    spacing = rng.choice((2, 3, 4, 5))
    before = pays[0] - timedelta(days=p.gaps[0] if p.gaps else 7)
    prev = p.since or before
    disputed = False

    for pay_day in pays:
        span = (pay_day - prev).days
        k = max(1, min(4, round(span / spacing), span))
        offsets = sorted(rng.sample(range(1, span + 1), k))
        method = "upi" if rng.random() < p.upi else "cash"
        paid_at = at(pay_day, 20, rng.randrange(0, 60, 5))

        for off in offsets:
            day = prev + timedelta(days=off)
            when = at(day, rng.randint(8, 19), rng.randrange(0, 60))
            paise = amount(rng, p.ticket)
            note = rng.choice(NOTES)

            if p.dispute and not disputed and day.month == 8:
                disputed = True
                eid = dispute(b, shop, p, cid, when)
                b.pay(eid, 15000, method, paid_at)
                continue

            eid = b.entry(shop, p.key, cid, paise, "settled", when, note=note)
            if linked:
                b.ack(shop, eid, paise, when + timedelta(seconds=rng.randint(20, 90)))
            b.pay(eid, paise, method, paid_at)
        prev = pay_day

    for o in p.opens:
        opened(b, shop, p.key, cid, o, linked)


def opened(
    b: Builder, shop: str, who: str, cid: uuid.UUID, o: Open, linked: bool
) -> None:
    rng = b.rng
    when = at(o.on, rng.randint(8, 19), rng.randrange(0, 60))
    acked = linked and o.confirmed
    eid = b.entry(
        shop,
        who,
        cid,
        o.paise,
        "confirmed" if acked else "recorded",
        when,
        spoken=o.spoken,
    )
    if acked:
        b.ack(shop, eid, o.paise, when + timedelta(seconds=rng.randint(20, 90)))


def dispute(
    b: Builder, shop: str, p: Persona, cid: uuid.UUID, when: datetime
) -> uuid.UUID:
    """₹200 recorded, disputed, corrected to ₹150 and confirmed. Returns the
    correction, which is the entry that gets paid."""
    wrong = b.entry(shop, p.key, cid, 20000, "corrected", when, note="Atta, tel")
    right = b.entry(
        shop,
        p.key,
        cid,
        15000,
        "settled",
        when + timedelta(minutes=6),
        note="Atta",
        corrects=wrong,
    )
    b.ack(shop, right, 15000, when + timedelta(minutes=7))

    tid = uid("thread", shop, p.key)
    b.plan.threads.append(
        (tid, cid, when + timedelta(minutes=10), when + timedelta(minutes=10), when)
    )
    lines = (
        ("bahi", "entry", "Ramesh recorded ₹200 udhaar.", wrong, 0),
        ("customer", "text", "Tel nahi liya tha maine. Sirf atta.", None, 2),
        ("shop", "text", "Achha haan, galti ho gayi. 150 kar deta hoon.", None, 4),
        ("bahi", "entry", "Corrected by Ramesh to ₹150.", right, 6),
    )
    for n, (author, kind, body, eid, minutes) in enumerate(lines):
        b.plan.messages.append(
            (
                uid("message", str(tid), str(n)),
                tid,
                author,
                kind,
                body,
                eid,
                when + timedelta(minutes=minutes, seconds=5),
            )
        )
    return right


def join(b: Builder, shop: str, p: Persona) -> uuid.UUID:
    """His customer row. Linked customers joined by scanning, the day before their
    history starts; the name-only ones were simply written into the book."""
    pays = payment_days(p)
    start = p.since or pays[0] - timedelta(days=p.gaps[0] if p.gaps else 7)
    added = at(start, 9)
    if p.joined == "invited":
        added = at(TODAY - timedelta(days=1), 19, 10)
    return b.customer(
        shop,
        p.key,
        p.name,
        p.tag,
        person=None if p.joined == "name_only" else p.key,
        added_at=added,
        linked_at=added if p.joined == "linked" else None,
    )


# ── the crowd ────────────────────────────────────────────────────────────────


def crowd(rng: random.Random) -> list[Persona]:
    """47 ordinary customers, each placed inside his own rhythm today."""
    people = rng.sample(CROWD, CROWD_SIZE)
    owing = set(rng.sample(range(CROWD_SIZE), CROWD_OWING))
    out: list[Persona] = []

    for i, (name, tag) in enumerate(people):
        usual = rng.choice(HABITS)
        late = usual < 20 and rng.random() < 0.3
        since = START + timedelta(days=rng.randint(10, 70)) if late else START
        # Owing customers sit well inside their usual gap; the rest paid recently.
        day = (
            rng.randint(2, max(2, int(usual * 0.7)))
            if i in owing
            else rng.randint(1, max(1, usual))
        )

        gaps: list[int] = []
        cursor = TODAY - timedelta(days=day)
        while True:
            gap = max(1, round(usual * rng.uniform(0.75, 1.3)))
            if cursor - timedelta(days=gap + usual) < since:
                break
            gaps.insert(0, gap)
            cursor -= timedelta(days=gap)

        ticket = rng.choice((60, 90, 120, 150, 200, 250))
        opens: tuple[Open, ...] = ()
        if i in owing:
            after = sorted(rng.sample(range(1, day), min(day - 1, rng.randint(1, 3))))
            last = TODAY - timedelta(days=day)
            opens = tuple(
                Open(last + timedelta(days=d), amount(rng, ticket)) for d in after
            )

        out.append(
            Persona(
                key=f"crowd-{i:02d}",
                name=name,
                tag=tag,
                joined="linked",
                gaps=tuple(gaps),
                day=day,
                opens=opens,
                ticket=ticket,
                upi=rng.choice((0.5, 0.7, 0.8, 0.9, 0.95)),
                since=since if since > START else None,
            )
        )
    return out


# ── Sharma, beyond the one shop ──────────────────────────────────────────────


def sharma_elsewhere(b: Builder, sharma: uuid.UUID) -> None:
    """His paper-book entry from 2023, and the two other shops he owes.

    The 2023 entry was carried over from Ramesh's notebook and never confirmed,
    so its three years ran from the sale and ended in July 2026. It stays in the
    book, struck through, and counts for nothing.
    """
    b.entry(
        HOME,
        "sharma",
        sharma,
        18000,
        "recorded",
        at(date(2023, 7, 14), 10, 30),
        note="From the paper book",
    )

    for shop, name, tag, joined_on, settled, paid_on, still in (
        (
            "salim",
            "Sharma ji",
            None,
            date(2026, 8, 1),
            (date(2026, 8, 20), 42000),
            date(2026, 8, 25),
            (date(2026, 9, 27), 69000),
        ),
        (
            "gupta",
            "Room 19",
            "B wing",
            date(2026, 8, 20),
            (date(2026, 9, 10), 28000),
            date(2026, 9, 16),
            (date(2026, 9, 30), 35000),
        ),
    ):
        cid = b.customer(
            shop,
            "sharma",
            name,
            tag,
            person="sharma",
            added_at=at(joined_on, 11),
            linked_at=at(joined_on, 11),
        )
        old = b.entry(shop, "sharma", cid, settled[1], "settled", at(settled[0], 18))
        b.ack(shop, old, settled[1], at(settled[0], 18, 1))
        b.pay(old, settled[1], "upi", at(paid_on, 19, 30))
        new = b.entry(shop, "sharma", cid, still[1], "confirmed", at(still[0], 17, 45))
        b.ack(shop, new, still[1], at(still[0], 17, 46))


# ── the whole world ──────────────────────────────────────────────────────────


def plan() -> Plan:
    rng = random.Random(SEED)
    b = Builder(rng)
    for key in SHOPS:
        b.shop(key)

    ids: dict[str, uuid.UUID] = {}
    people = [*CAST, *crowd(rng)]
    for p in people:
        ids[p.key] = join(b, HOME, p)

    # Sharma was in the paper book long before he ever scanned.
    sharma = next(i for i, row in enumerate(b.plan.customers) if row[0] == ids["sharma"])
    row = b.plan.customers[sharma]
    b.plan.customers[sharma] = (*row[:5], at(date(2023, 7, 14), 10), row[6])

    for p in people:
        if p.joined != "invited":
            history(b, HOME, p, ids[p.key], linked=p.joined == "linked")
    sharma_elsewhere(b, ids["sharma"])
    return b.plan


INSERTS = {
    "shops": "INSERT INTO shops (id, name, locality, created_at) VALUES (%s,%s,%s,%s)",
    "customers": "INSERT INTO customers (id, shop_id, person_id, display_name, tag, "
    "added_at, linked_at) VALUES (%s,%s,%s,%s,%s,%s,%s)",
    "entries": "INSERT INTO entries (id, customer_id, amount_paise, note, spoken_text, "
    "status, corrects_entry_id, recorded_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
    "acknowledgments": "INSERT INTO acknowledgments (id, entry_id, wording, "
    "acknowledged_at) VALUES (%s,%s,%s,%s)",
    "repayments": "INSERT INTO repayments (id, entry_id, amount_paise, method, paid_at) "
    "VALUES (%s,%s,%s,%s,%s)",
    "threads": "INSERT INTO threads (id, customer_id, shop_read_at, customer_read_at, "
    "created_at) VALUES (%s,%s,%s,%s,%s)",
    "messages": "INSERT INTO messages (id, thread_id, author, kind, body, entry_id, "
    "sent_at) VALUES (%s,%s,%s,%s,%s,%s,%s)",
}


def load(con: db.Conn, p: Plan) -> dict[str, int]:
    counts: dict[str, int] = {}
    with con.cursor() as cur:
        for table, sql in INSERTS.items():
            rows: list[Row] = getattr(p, table)
            cur.executemany(sql, rows)
            counts[table] = len(rows)
    con.commit()
    return counts


def main() -> int:
    from data import contract

    started = time.perf_counter()
    p = plan()
    with db.connect() as con:
        counts = load(con, p)
        path = contract.write(con)
    for table, n in counts.items():
        print(f"  {table:<16} {n:>6,}")
    print(f"  wrote {path.relative_to(path.parents[1])}")
    print(f"  seeded in {time.perf_counter() - started:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
