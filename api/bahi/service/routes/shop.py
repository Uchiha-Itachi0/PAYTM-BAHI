"""The shopkeeper's side: Paytm for Business."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Request, Response

from bahi import clock, paytm, voice
from bahi.domain.book import book
from bahi.service import chat, ledger, memory, views
from bahi.service.deps import Con, etagged
from bahi.service.errors import Conflict, NotFound
from bahi.service.models import (
    AccountOut,
    CounterOut,
    CustomerDetailOut,
    CustomerOut,
    EntryOut,
    InviteIn,
    LinkIn,
    MemoryIn,
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
    owed = {
        ln.customer_id: ln.balance_paise
        for ln in book(book_store.load(con, shop_id), clock.today()).lines
    }
    return [_customer_out(c, owed.get(c.id, 0)) for c in customers.of_shop(con, shop_id)]


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


def _customer_out(c: CustomerRef, balance_paise: int = 0) -> CustomerOut:
    return CustomerOut(
        id=c.id,
        display_name=c.display_name,
        tag=c.tag,
        joined=c.joined,
        invite_pending=c.invite_person_id is not None,
        balance_paise=balance_paise,
    )


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
        person_id=a.person_id,
        name=a.name,
        named=paytm.named(a),
        here=here.joined if here else None,
    )


@router.post("/shops/{shop_id}/customers/invite", status_code=201)
def invite(shop_id: str, body: InviteIn, con: Con) -> CustomerOut:
    """A4. Send invite: he accepts on his own phone, and nothing is recorded
    against him until he does."""
    a = paytm.lookup(body.query)
    if a is None:
        raise NotFound("No Paytm account with that number or UPI ID")
    name = a.name if paytm.named(a) else (body.display_name or "").strip()
    if not name:
        raise Conflict("Paytm doesn't give this account's name: say what to call them")
    c = ledger.invite(con, shop_id, a.person_id, name, body.tag, clock.now(), voice.hindi)
    return _customer_out(c)


@router.post("/shops/{shop_id}/customers", status_code=201)
def add_by_name(shop_id: str, body: NameOnlyIn, con: Con) -> CustomerOut:
    """A4. No phone: kept by name only, like the notebook."""
    c = ledger.add_by_name(
        con, shop_id, body.display_name, body.tag, clock.now(), voice.hindi
    )
    return _customer_out(c)


# ── one customer ─────────────────────────────────────────────────────────────


def _detail(con: Con, shop_id: str, customer_id: str) -> CustomerDetailOut:
    c = ledger.customer_here(con, shop_id, customer_id)
    return chat.customer_detail(con, c, clock.today())


@router.get("/shops/{shop_id}/customers/{customer_id}", response_model=CustomerDetailOut)
def get_customer(shop_id: str, customer_id: str, request: Request, con: Con) -> Response:
    """One customer: whether he is on BAHI, what he owes, and his entries."""
    return etagged(request, _detail(con, shop_id, customer_id))


@router.post("/shops/{shop_id}/customers/{customer_id}")
def edit_customer(
    shop_id: str, customer_id: str, body: NameOnlyIn, con: Con
) -> CustomerDetailOut:
    """What the shop calls him, and where he lives or works."""
    ledger.rename(con, shop_id, customer_id, body.display_name, body.tag, voice.hindi)
    return _detail(con, shop_id, customer_id)


@router.post("/shops/{shop_id}/customers/{customer_id}/memories", status_code=201)
def remember_note(
    shop_id: str, customer_id: str, body: MemoryIn, con: Con
) -> CustomerDetailOut:
    """M3. A note the shopkeeper types about him ("pays through his son"), and a
    day to stay quiet until, if it asks to wait."""
    c = ledger.customer_here(con, shop_id, customer_id)
    memory.keep(
        con, shop_id, c.id, "note", body.body, "shop", clock.now(), until=body.until
    )
    return _detail(con, shop_id, customer_id)


@router.delete("/shops/{shop_id}/memories/{memory_id}", status_code=204)
def forget(shop_id: str, memory_id: UUID, con: Con) -> None:
    """M3. Forget it: gone from his page and from Tonight at once, and from
    Cognee's search right after."""
    memory.forget(con, shop_id, str(memory_id), clock.now())


@router.post("/shops/{shop_id}/customers/{customer_id}/invite")
def invite_by_name(
    shop_id: str, customer_id: str, body: LinkIn, con: Con
) -> CustomerDetailOut:
    """Someone kept by name: his number or UPI ID, and an invite to his phone. His
    book keeps working by name until he says yes; then his history is his."""
    a = paytm.lookup(body.query)
    if a is None:
        raise NotFound("No Paytm account with that number or UPI ID")
    ledger.invite_by_name(con, shop_id, customer_id, a.person_id, clock.now())
    return _detail(con, shop_id, customer_id)


@router.post("/shops/{shop_id}/customers/{customer_id}/invite/cancel")
def cancel_invite(shop_id: str, customer_id: str, con: Con) -> CustomerDetailOut:
    ledger.cancel_invite(con, shop_id, customer_id)
    return _detail(con, shop_id, customer_id)
