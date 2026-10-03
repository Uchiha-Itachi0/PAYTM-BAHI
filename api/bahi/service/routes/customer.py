"""The customer's side: the Paytm app."""

from __future__ import annotations

from fastapi import APIRouter, Request, Response

from bahi import clock
from bahi.service import ledger, views
from bahi.service.deps import Con, etagged
from bahi.service.models import (
    DisputeIn,
    EntryOut,
    JoinIn,
    JoinOut,
    PersonIn,
    ScanOut,
)
from bahi.store import entries

router = APIRouter(tags=["customer"])


@router.post("/join/{shop_id}", status_code=201)
def join(shop_id: str, body: JoinIn, con: Con) -> JoinOut:
    """B0. He scanned the shop's udhaar QR: he is at the counter."""
    j = ledger.join(con, shop_id, body.person_id, body.name, clock.now())
    return JoinOut(
        customer_id=j.customer.id,
        scan_id=j.scan_id,
        shop=views.shop_out(ledger.shop(con, shop_id)),
        first_time=j.first_time,
    )


@router.get("/scans/{scan_id}", response_model=ScanOut)
def get_scan(scan_id: str, request: Request, con: Con) -> Response:
    """What happened to his scan. Once the shopkeeper records an amount, the entry
    comes back here and his phone shows the confirmation sheet."""
    s = ledger.scan(con, scan_id)
    e = entries.get(con, s.entry_id) if s.entry_id else None
    body = ScanOut(
        scan_id=s.id,
        state=s.state(clock.now()),
        entry=views.entry_out(e) if e else None,
    )
    return etagged(request, body)


@router.post("/scans/{scan_id}/leave", status_code=204)
def leave(scan_id: str, con: Con) -> None:
    """He tapped Cancel."""
    ledger.leave(con, scan_id, clock.now())


@router.get("/entries/{entry_id}")
def get_entry(entry_id: str, con: Con) -> EntryOut:
    return views.entry_out(ledger.entry(con, entry_id))


@router.post("/entries/{entry_id}/confirm")
def confirm(entry_id: str, body: PersonIn, con: Con) -> EntryOut:
    """B1. "Yes, I owe ₹200"."""
    return views.entry_out(ledger.confirm(con, entry_id, body.person_id, clock.now()))


@router.post("/entries/{entry_id}/dispute")
def dispute(entry_id: str, body: DisputeIn, con: Con) -> EntryOut:
    """B1. "That's not right"."""
    e = ledger.dispute(con, entry_id, body.person_id, body.reason, clock.now())
    return views.entry_out(e)
