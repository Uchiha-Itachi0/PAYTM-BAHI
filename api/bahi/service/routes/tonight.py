"""V4 · Tonight: who gets a reminder tomorrow, who is left alone, and why.

The decision is code (domain/tonight.py), worked out from the book on every
call. The munshi writes the words of each reminder; the shopkeeper can stop any
of them. n8n will run this at 11 pm and send each reminder at its hour (V8a);
until then Send now posts them at once, for the demo.
"""

from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter

from bahi import clock
from bahi.service import tonight
from bahi.service.deps import Con
from bahi.service.models import (
    PlanOut,
    ReminderOut,
    RhythmOut,
    SentOut,
    TonightOut,
)
from bahi.store import customers
from bahi.store.db import Conn
from bahi.store.reminders import Reminder

router = APIRouter(tags=["tonight"])


def _reminder(r: Reminder | None) -> ReminderOut | None:
    if r is None:
        return None
    return ReminderOut(
        id=r.id,
        send_at=r.send_at,
        body=r.body,
        written=r.written,  # type: ignore[arg-type]
        status=r.status,  # type: ignore[arg-type]
    )


def _out(con: Conn, shop_id: str, e: tonight.Evening) -> TonightOut:
    t = e.tonight
    joined = {c.id: c.joined for c in customers.of_shop(con, shop_id)}
    plans = [
        PlanOut(
            customer_id=p.customer_id,
            display_name=p.display_name,
            tag=p.tag,
            joined=joined[p.customer_id],
            balance_paise=p.balance_paise,
            day=p.day,
            rhythm=RhythmOut(
                n=p.rhythm.n,
                median_gap=p.rhythm.median_gap,
                max_gap=p.rhythm.max_gap,
                last_paid=p.rhythm.last_paid,
            ),
            send=p.send,
            why=p.why,
            reminded_on=p.reminded_on,
            # A reminder already sent for tomorrow stays on the list as sent.
            reminder=_reminder(e.reminders.get(p.customer_id)),
        )
        for p in t.plans
    ]
    return TonightOut(
        today=t.for_day - timedelta(days=1),
        for_day=t.for_day,
        worked_out_at=clock.now(),
        owing_count=t.owing_count,
        sending_count=sum(
            1 for p in plans if p.send or (p.reminder and p.reminder.status == "sent")
        ),
        plans=plans,
    )


@router.get("/shops/{shop_id}/tonight")
def get_tonight(shop_id: str, con: Con) -> TonightOut:
    """A3. Tomorrow's list, as the book stands now. Writes nothing."""
    return _out(con, shop_id, tonight.work_out(con, shop_id, clock.now()))


@router.post("/shops/{shop_id}/tonight")
def run_tonight(shop_id: str, con: Con) -> TonightOut:
    """The 11 pm run: works out the list and has the munshi write each reminder
    not yet written. Running it again changes nothing already written."""
    return _out(con, shop_id, tonight.draft(con, shop_id, clock.now()))


@router.post("/shops/{shop_id}/tonight/send")
def send_due(shop_id: str, con: Con) -> SentOut:
    """Sends the reminders whose hour has come. n8n calls this (V8a)."""
    return SentOut(sent=len(tonight.send(con, shop_id, clock.now())))


@router.post("/shops/{shop_id}/tonight/send-now")
def send_now(shop_id: str, con: Con) -> SentOut:
    """The demo's fast-forward: every planned reminder goes now."""
    return SentOut(sent=len(tonight.send(con, shop_id, clock.now(), all_now=True)))


@router.post("/shops/{shop_id}/reminders/{reminder_id}/stop")
def stop(shop_id: str, reminder_id: str, con: Con) -> ReminderOut:
    """The shopkeeper said no to this one."""
    out = _reminder(tonight.stop(con, shop_id, reminder_id, stopped=True))
    assert out is not None
    return out


@router.post("/shops/{shop_id}/reminders/{reminder_id}/resume")
def resume(shop_id: str, reminder_id: str, con: Con) -> ReminderOut:
    """He changed his mind: it goes after all."""
    out = _reminder(tonight.stop(con, shop_id, reminder_id, stopped=False))
    assert out is not None
    return out
