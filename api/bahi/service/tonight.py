"""Tonight: the decision (code), the words (the munshi), and sending them.

`work_out` asks domain/tonight.py who gets a reminder tomorrow, from the book as
it stands. `draft` has the munshi write the words for each one not yet written,
and keeps them. `send` posts the ones whose hour has come into the customer's
thread; n8n will call it (V8a), and the screen's Send now does it at once for
the demo. Nothing reaches a customer the shopkeeper stopped.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import date, datetime

from bahi import clock
from bahi.domain.tonight import Plan, Tonight, tonight
from bahi.munshi import writer
from bahi.service import ledger
from bahi.service.errors import Conflict, NotFound
from bahi.store import book as book_store
from bahi.store import reminders, threads
from bahi.store.db import Conn
from bahi.store.reminders import Reminder

#: Reminders are written this many at a time.
WRITERS = 4


@dataclass(frozen=True, slots=True)
class Evening:
    tonight: Tonight
    #: Reminders already drafted for tomorrow, by customer.
    reminders: dict[str, Reminder]


def work_out(con: Conn, shop_id: str, now: datetime) -> Evening:
    """Who gets a reminder tomorrow, and the words kept for each so far."""
    ledger.shop(con, shop_id)
    t = tonight(
        book_store.load(con, shop_id),
        now.date(),
        book_store.paid_times(con, shop_id),
        reminders.last_sent(con, shop_id),
    )
    return Evening(t, reminders.for_day(con, shop_id, t.for_day))


def _said(con: Conn, customer_id: str) -> list[writer.Said]:
    t = threads.of_customer(con, customer_id)
    if t is None:
        return []
    return [
        writer.Said(m.author, m.body)  # type: ignore[arg-type]
        for m in threads.messages(con, t.id)
    ]


def send_at(day: date, plan: Plan) -> datetime:
    assert plan.send_at is not None
    return datetime.combine(day, plan.send_at, tzinfo=clock.IST)


def draft(con: Conn, shop_id: str, now: datetime) -> Evening:
    """The munshi writes each reminder that has no words yet. Idempotent: a
    reminder already written keeps its words, and a Stop stays a Stop."""
    e = work_out(con, shop_id, now)
    shop = ledger.shop(con, shop_id)
    todo = [p for p in e.tonight.sending if p.customer_id not in e.reminders]
    if not todo:
        return e
    chats = {p.customer_id: _said(con, p.customer_id) for p in todo}
    with ThreadPoolExecutor(max_workers=WRITERS) as pool:
        written = list(
            pool.map(
                lambda p: writer.reminder(
                    p.display_name, shop.name, p.balance_paise, chats[p.customer_id]
                ),
                todo,
            )
        )
    for p, w in zip(todo, written, strict=True):
        reminders.add(
            con,
            p.customer_id,
            e.tonight.for_day,
            send_at(e.tonight.for_day, p),
            w.body,
            w.by,
            now,
        )
    return work_out(con, shop_id, now)


def stop(con: Conn, shop_id: str, reminder_id: str, *, stopped: bool) -> Reminder:
    """The shopkeeper's Stop, or his change of mind."""
    r = reminders.get(con, reminder_id, shop_id)
    if r is None:
        raise NotFound(f"no reminder {reminder_id} at this shop")
    if not reminders.set_status(con, r.id, "stopped" if stopped else "planned"):
        raise Conflict("that reminder has already gone")
    out = reminders.get(con, r.id, shop_id)
    assert out is not None
    return out


def send(con: Conn, shop_id: str, now: datetime, *, all_now: bool = False) -> list[str]:
    """Posts tomorrow's planned reminders whose hour has come (all of them with
    `all_now`, the demo's fast-forward) into each customer's thread. Only to
    someone the decision still sends to: a customer who paid since it was
    drafted is not reminded. Returns the customers reminded."""
    e = work_out(con, shop_id, now)
    still = {p.customer_id for p in e.tonight.sending}
    sent: list[str] = []
    for cid, r in e.reminders.items():
        if r.status != "planned" or cid not in still:
            continue
        if not all_now and r.send_at > now:
            continue
        claimed = reminders.claim(con, r.id)
        if claimed is None:
            continue
        m = threads.post(con, cid, "bahi", "reminder", claimed.body, now)
        reminders.mark_sent(con, claimed.id, m.id)
        sent.append(cid)
    return sent
