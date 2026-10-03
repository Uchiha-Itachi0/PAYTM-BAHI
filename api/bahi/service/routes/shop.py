"""The shopkeeper's side: Paytm for Business."""

from __future__ import annotations

from fastapi import APIRouter, Request, Response

from bahi import clock
from bahi.domain.book import book
from bahi.service import ledger, views
from bahi.service.deps import Con, etagged
from bahi.service.models import (
    CounterOut,
    CustomerOut,
    EntryOut,
    RecordIn,
    ShopBookOut,
    ShopOut,
    WaitingOut,
)
from bahi.store import book as book_store
from bahi.store import customers, scans, shops

router = APIRouter(tags=["shopkeeper"])


@router.get("/shops")
def list_shops(con: Con) -> list[ShopOut]:
    return [views.shop_out(s) for s in shops.all_shops(con)]


@router.get("/shops/{shop_id}/book", response_model=ShopBookOut)
def get_book(shop_id: str, request: Request, con: Con) -> Response:
    """A1. Every figure here is computed by bahi/domain from the ledger."""
    s = ledger.shop(con, shop_id)
    b = book(book_store.load(con, shop_id), clock.today())
    return etagged(request, views.book_out(s, b))


@router.get("/shops/{shop_id}/counter", response_model=CounterOut)
def get_counter(shop_id: str, request: Request, con: Con) -> Response:
    """A2. Everyone who scanned the udhaar QR in the last three minutes."""
    ledger.shop(con, shop_id)
    now = clock.now()
    waiting = scans.waiting(con, shop_id, now)
    body = CounterOut(
        shop_id=shop_id,
        waiting=[
            WaitingOut(
                scan_id=w.scan_id,
                customer_id=w.customer_id,
                display_name=w.display_name,
                tag=w.tag,
                scanned_at=w.scanned_at,
                waited_s=int((now - w.scanned_at).total_seconds()),
                first_time=w.first_time,
            )
            for w in waiting
        ],
    )
    return etagged(request, body)


@router.get("/shops/{shop_id}/customers")
def list_customers(shop_id: str, con: Con) -> list[CustomerOut]:
    """Everyone in the book, for picking someone who is not at the counter."""
    ledger.shop(con, shop_id)
    return [
        CustomerOut(id=c.id, display_name=c.display_name, tag=c.tag, joined=c.joined)
        for c in customers.of_shop(con, shop_id)
    ]


@router.post("/shops/{shop_id}/entries", status_code=201)
def record_entry(shop_id: str, body: RecordIn, con: Con) -> EntryOut:
    """Record udhaar: for a scan at the counter, or a customer from the book."""
    e = ledger.record(
        con,
        shop_id,
        body.amount_paise,
        clock.now(),
        scan_id=body.scan_id,
        customer_id=body.customer_id,
        note=body.note,
        spoken_text=body.spoken_text,
    )
    return views.entry_out(e)
