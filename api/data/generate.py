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
from dataclasses import dataclass, field, replace
from datetime import date, datetime, timedelta

from bahi.domain import wording
from bahi.domain.wording import acknowledgment
from data import db, names_hi
from data.personas import CAST, CROWD, Open, Persona
from data.rows import (
    AcknowledgmentRow,
    CustomerRow,
    EntryRow,
    MessageRow,
    RepaymentRow,
    ShopRow,
    ThreadRow,
    insert,
)
from data.world import HOME, SEED, SHOPS, START, TODAY, at, uid

#: The usual gap for a generated customer is drawn from this, in days. Weighted
#: toward weekly and fortnightly, with a few who settle once a month.
HABITS = (3, 4, 5, 6, 7, 7, 7, 8, 9, 10, 10, 12, 14, 14, 15, 15, 20, 21, 30)

#: Every seeded name and tag in Devanagari, as Sarvam writes it. Committed, so the seed
#: still rebuilds identically with the wifi off.
HINDI = names_hi.load()

#: Of the generated customers, how many owe something today. With the eleven
#: owing members of the cast that makes 38 of 60.
CROWD_SIZE = 47
CROWD_OWING = 27

NOTES = (None,) * 7 + ("Atta", "Doodh", "Chawal", "Dal", "Tel", "Sabun", "Chai patti")


@dataclass
class Plan:
    """Every row the seed will write, table by table, in insert order."""

    shops: list[ShopRow] = field(default_factory=list)
    customers: list[CustomerRow] = field(default_factory=list)
    entries: list[EntryRow] = field(default_factory=list)
    acknowledgments: list[AcknowledgmentRow] = field(default_factory=list)
    repayments: list[RepaymentRow] = field(default_factory=list)
    threads: list[ThreadRow] = field(default_factory=list)
    messages: list[MessageRow] = field(default_factory=list)


class Builder:
    """Appends rows to a Plan and hands out stable ids."""

    def __init__(self, rng: random.Random) -> None:
        self.rng = rng
        self.plan = Plan()
        self._n: dict[str, int] = {}
        self._threads: dict[uuid.UUID, int] = {}

    def _next(self, key: str) -> int:
        self._n[key] = self._n.get(key, 0) + 1
        return self._n[key]

    def shop(self, key: str) -> uuid.UUID:
        sid = uid("shop", key)
        name, locality = SHOPS[key]
        self.plan.shops.append(ShopRow(sid, name, locality, created_at=at(START, 8)))
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
            CustomerRow(
                id=cid,
                shop_id=uid("shop", shop),
                person_id=pid,
                display_name=name,
                tag=tag,
                added_at=added_at,
                linked_at=linked_at,
                name_hi=HINDI.get(name),
                tag_hi=HINDI.get(tag) if tag else None,
            )
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
            EntryRow(
                id=eid,
                customer_id=cid,
                amount_paise=paise,
                status=status,
                recorded_at=recorded_at,
                note=note,
                spoken_text=spoken,
                corrects_entry_id=corrects,
            )
        )
        return eid

    def ack(self, shop: str, eid: uuid.UUID, paise: int, when: datetime) -> None:
        wording = acknowledgment(paise, SHOPS[shop][0])
        self.plan.acknowledgments.append(
            AcknowledgmentRow(uid("ack", str(eid)), eid, wording, acknowledged_at=when)
        )

    def pay(self, eid: uuid.UUID, paise: int, method: str, when: datetime) -> None:
        self.plan.repayments.append(
            RepaymentRow(uid("pay", str(eid)), eid, paise, method, paid_at=when)
        )

    def say(
        self,
        shop: str,
        who: str,
        cid: uuid.UUID,
        author: str,
        kind: str,
        body: str,
        when: datetime,
        entry: uuid.UUID | None = None,
    ) -> None:
        """One message in his thread with the shop; the thread is made on the first."""
        tid = uid("thread", shop, who)
        if tid not in self._threads:
            self._threads[tid] = len(self.plan.threads)
            self.plan.threads.append(ThreadRow(tid, cid, created_at=when))
        n = self._next(f"message:{tid}") - 1
        self.plan.messages.append(
            MessageRow(
                id=uid("message", str(tid), str(n)),
                thread_id=tid,
                author=author,
                kind=kind,
                body=body,
                sent_at=when,
                entry_id=entry,
            )
        )

    def all_read(self) -> None:
        """Both sides have read every seeded thread: the demo starts with an
        empty inbox badge, and what arrives live is what shows as new."""
        last: dict[uuid.UUID, datetime] = {}
        for m in self.plan.messages:
            last[m.thread_id] = max(m.sent_at, last.get(m.thread_id, m.sent_at))
        self.plan.threads = [
            replace(t, shop_read_at=last[t.id], customer_read_at=last[t.id])
            for t in self.plan.threads
        ]


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
        paid_at = at(pay_day, p.pays_at, rng.randrange(0, 60, 5))

        for off in offsets:
            day = prev + timedelta(days=off)
            when = at(day, rng.randint(8, 19), rng.randrange(0, 60))
            paise = amount(rng, p.ticket)
            note = rng.choice(NOTES)

            if p.dispute and not disputed and day.month == 8:
                disputed = True
                eid = dispute(b, shop, p, cid, when)
                b.pay(eid, 15000, method, paid_at)
                b.say(
                    shop,
                    p.key,
                    cid,
                    "bahi",
                    "entry",
                    wording.paid(15000, method),
                    paid_at,
                    eid,
                )
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
    if linked:
        # Its card in his thread, posted as it was recorded.
        body = wording.recorded(SHOPS[shop][0], o.paise)
        b.say(shop, who, cid, "bahi", "entry", body, when + timedelta(seconds=5), eid)


def dispute(
    b: Builder, shop: str, p: Persona, cid: uuid.UUID, when: datetime
) -> uuid.UUID:
    """₹200 recorded, disputed, corrected to ₹150 and confirmed. Returns the
    correction, which is the entry that gets paid."""
    name = SHOPS[shop][0]
    said_wrong = when + timedelta(minutes=2)
    wrong = b.entry(
        shop,
        p.key,
        cid,
        20000,
        "corrected",
        when,
        note="Atta, tel",
    )
    b.plan.entries[-1] = replace(b.plan.entries[-1], disputed_at=said_wrong)
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

    lines = (
        ("bahi", "entry", wording.recorded(name, 20000), wrong, timedelta(seconds=5)),
        ("bahi", "entry", wording.disputed(p.name, 20000), wrong, timedelta(minutes=2)),
        (
            "customer",
            "text",
            "Tel nahi liya tha maine. Sirf atta.",
            None,
            timedelta(minutes=2, seconds=1),
        ),
        (
            "shop",
            "text",
            "Achha haan, galti ho gayi. 150 kar deta hoon.",
            None,
            timedelta(minutes=4),
        ),
        (
            "bahi",
            "entry",
            wording.corrected(name, 15000),
            right,
            timedelta(minutes=6, seconds=5),
        ),
    )
    for author, kind, body, eid, after in lines:
        b.say(shop, p.key, cid, author, kind, body, when + after, eid)
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
        b.say(
            shop,
            "sharma",
            cid,
            "bahi",
            "entry",
            wording.recorded(SHOPS[shop][0], still[1]),
            at(still[0], 17, 45, 5),
            new,
        )


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
    i = next(n for n, c in enumerate(b.plan.customers) if c.id == ids["sharma"])
    b.plan.customers[i] = replace(b.plan.customers[i], added_at=at(date(2023, 7, 14), 10))

    for p in people:
        if p.joined != "invited":
            history(b, HOME, p, ids[p.key], linked=p.joined == "linked")
    sharma_elsewhere(b, ids["sharma"])
    b.all_read()
    return b.plan


#: Parents before children, so every foreign key already exists when it is used.
TABLES = (
    "shops",
    "customers",
    "entries",
    "acknowledgments",
    "repayments",
    "threads",
    "messages",
)


def load(con: db.Conn, p: Plan) -> dict[str, int]:
    with con.cursor() as cur:
        counts = {table: insert(cur, table, getattr(p, table)) for table in TABLES}
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
