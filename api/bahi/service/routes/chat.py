"""V5 · Chat: one thread per shop and customer, seen from either side.

People type. BAHI posts the entry cards and the reminders. A disputed entry is
answered with a correction, which is a new entry the customer confirms on his
own. The munshi can suggest replies; nothing is sent until the shopkeeper taps.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Request, Response

from bahi import clock
from bahi.munshi import writer
from bahi.service import chat, ledger, views
from bahi.service.deps import Con, etagged
from bahi.service.models import (
    CorrectIn,
    CustomerSayIn,
    EntryOut,
    EventOut,
    EventsOut,
    InboxOut,
    RepliesOut,
    SayIn,
    ThreadOut,
)
from bahi.store import events, threads

router = APIRouter(tags=["chat"])


# ── the shopkeeper ───────────────────────────────────────────────────────────


@router.get("/shops/{shop_id}/inbox", response_model=InboxOut)
def get_inbox(shop_id: str, request: Request, con: Con) -> Response:
    """C1. Every thread, the latest first, with what is unread."""
    return etagged(request, chat.inbox(con, shop_id, clock.today()))


@router.post("/shops/{shop_id}/inbox/read", status_code=204)
def read_all(shop_id: str, con: Con) -> None:
    """Mark all read."""
    ledger.shop(con, shop_id)
    threads.read_all(con, shop_id, clock.now())


@router.get("/shops/{shop_id}/customers/{customer_id}/thread", response_model=ThreadOut)
def get_shop_thread(
    shop_id: str, customer_id: str, request: Request, con: Con
) -> Response:
    """C3. His thread, as the shop sees it."""
    c = chat.customer_at(con, shop_id, customer_id)
    return etagged(request, chat.thread(con, c, clock.today(), for_shop=True))


@router.post("/shops/{shop_id}/customers/{customer_id}/thread/read", status_code=204)
def read_shop_thread(shop_id: str, customer_id: str, con: Con) -> None:
    c = chat.customer_at(con, shop_id, customer_id)
    t = threads.of_customer(con, c.id)
    if t is not None:
        threads.read(con, t.id, "shop", clock.now())


@router.post("/shops/{shop_id}/customers/{customer_id}/thread", status_code=201)
def shop_says(shop_id: str, customer_id: str, body: SayIn, con: Con) -> ThreadOut:
    """The shopkeeper writes to him. Words only: a message carries no amount."""
    chat.shop_says(con, shop_id, customer_id, body.text, clock.now())
    c = chat.customer_at(con, shop_id, customer_id)
    return chat.thread(con, c, clock.today(), for_shop=True)


@router.post("/shops/{shop_id}/customers/{customer_id}/thread/suggest")
def suggest(shop_id: str, customer_id: str, con: Con) -> RepliesOut:
    """Replies the munshi would send, in his language. Only suggestions: the
    shopkeeper taps one to send it. None when voice is off."""
    c = chat.customer_at(con, shop_id, customer_id)
    s = ledger.shop(con, shop_id)
    t = threads.of_customer(con, c.id)
    said = [
        writer.Said(m.author, m.body)  # type: ignore[arg-type]
        for m in (threads.messages(con, t.id) if t else [])
    ]
    if not said or said[-1].who != "customer":
        return RepliesOut(replies=[])
    return RepliesOut(replies=writer.replies(c.display_name, s.name, said))


@router.post("/shops/{shop_id}/entries/{entry_id}/correct", status_code=201)
def correct(shop_id: str, entry_id: str, body: CorrectIn, con: Con) -> EntryOut:
    """C2. The right amount for an entry he says is wrong: a new entry, which he
    confirms on his own phone. The disputed one is kept, and counts for nothing."""
    e = ledger.correct(con, shop_id, entry_id, body.amount_paise, clock.now())
    return views.entry_out(e)


@router.get("/shops/{shop_id}/events")
def get_events(shop_id: str, con: Con, after: datetime | None = None) -> EventsOut:
    """V7. What happened since `after`: for the Soundbox's tones and the screen's
    news. The first call (no `after`) only says what time it is."""
    ledger.shop(con, shop_id)
    now = clock.now()
    found = events.since(con, shop_id, after, now) if after else []
    return EventsOut(
        now=now,
        events=[
            EventOut(
                kind=e.kind,  # type: ignore[arg-type]
                at=e.at,
                customer_id=e.customer_id,
                display_name=e.display_name,
                amount_paise=e.amount_paise,
                left_paise=ledger.balance(con, shop_id, e.customer_id, now.date())
                if e.kind == "paid"
                else None,
            )
            for e in found
        ],
    )


# ── the customer ─────────────────────────────────────────────────────────────


@router.get("/people/{person_id}/shops/{shop_id}/thread", response_model=ThreadOut)
def get_my_thread(person_id: str, shop_id: str, request: Request, con: Con) -> Response:
    """C2. His thread with one shop."""
    c = chat.person_at(con, person_id, shop_id)
    return etagged(request, chat.thread(con, c, clock.today(), for_shop=False))


@router.post("/people/{person_id}/shops/{shop_id}/thread/read", status_code=204)
def read_my_thread(person_id: str, shop_id: str, con: Con) -> None:
    c = chat.person_at(con, person_id, shop_id)
    t = threads.of_customer(con, c.id)
    if t is not None:
        threads.read(con, t.id, "customer", clock.now())


@router.post("/shops/{shop_id}/thread", status_code=201)
def customer_says(shop_id: str, body: CustomerSayIn, con: Con) -> ThreadOut:
    """He writes to the shop."""
    c = chat.person_at(con, str(body.person_id), shop_id)
    threads.post(con, c.id, "customer", "text", body.text.strip(), clock.now())
    return chat.thread(con, c, clock.today(), for_shop=False)
