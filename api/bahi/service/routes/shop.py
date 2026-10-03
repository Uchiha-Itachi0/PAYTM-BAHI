"""The shopkeeper's side: Paytm for Business."""

from __future__ import annotations

from fastapi import APIRouter, Request, Response

from bahi import clock, paytm, voice
from bahi.domain.book import book
from bahi.service import ledger, views
from bahi.service.deps import Con, etagged
from bahi.service.errors import NotFound
from bahi.service.models import (
    AccountOut,
    CounterOut,
    CustomerOut,
    EntryOut,
    InviteIn,
    NameOnlyIn,
    RecordIn,
    ShopBookOut,
    ShopOut,
    WaitingOut,
)
from bahi.store import book as book_store
from bahi.store import customers, scans, shops
from bahi.store.customers import CustomerRef

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
    return [_customer_out(c) for c in customers.of_shop(con, shop_id)]


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


# ── V6: adding someone who can't scan ────────────────────────────────────────


def _customer_out(c: CustomerRef) -> CustomerOut:
    return CustomerOut(id=c.id, display_name=c.display_name, tag=c.tag, joined=c.joined)


@router.get("/shops/{shop_id}/accounts")
def find_account(shop_id: str, q: str, con: Con) -> AccountOut:
    """A4. The Paytm account behind a mobile number or UPI ID, and whether he is
    already in this book. The number is only used to look, never kept."""
    ledger.shop(con, shop_id)
    a = paytm.lookup(q)
    if a is None:
        raise NotFound("No Paytm account with that number or UPI ID")
    here = customers.at_shop(con, shop_id, a.person_id)
    return AccountOut(
        person_id=a.person_id, name=a.name, here=here.joined if here else None
    )


@router.post("/shops/{shop_id}/customers/invite", status_code=201)
def invite(shop_id: str, body: InviteIn, con: Con) -> CustomerOut:
    """A4. Send invite: he accepts on his own phone, and nothing is recorded
    against him until he does."""
    a = paytm.lookup(body.query)
    if a is None:
        raise NotFound("No Paytm account with that number or UPI ID")
    c = ledger.invite(
        con, shop_id, a.person_id, a.name, body.tag, clock.now(), voice.hindi
    )
    return _customer_out(c)


@router.post("/shops/{shop_id}/customers", status_code=201)
def add_by_name(shop_id: str, body: NameOnlyIn, con: Con) -> CustomerOut:
    """A4. No phone: kept by name only, like the notebook."""
    c = ledger.add_by_name(
        con, shop_id, body.display_name, body.tag, clock.now(), voice.hindi
    )
    return _customer_out(c)
