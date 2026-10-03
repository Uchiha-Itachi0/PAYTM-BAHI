"""V3 · The customer's own book, in the Paytm app: every shop, pay, and invites.

A person's view never includes anyone else: every call names the person, and
only rows recorded against that person come back.
"""

from __future__ import annotations

from fastapi import APIRouter, Request, Response

from bahi import clock
from bahi.service import chat, ledger, views
from bahi.service.deps import Con, etagged
from bahi.service.models import DemoPhoneOut, MyUdhaarOut, PaidOut, PersonIn
from bahi.store import customers
from data import directory

router = APIRouter(tags=["customer"])


@router.get("/people/{person_id}/udhaar", response_model=MyUdhaarOut)
def my_udhaar(person_id: str, request: Request, con: Con) -> Response:
    """B2. What he owes across every shop, each entry, and invitations waiting."""
    return etagged(request, chat.my_udhaar(con, person_id, clock.today()))


@router.post("/shops/{shop_id}/pay")
def pay(shop_id: str, body: PersonIn, con: Con) -> PaidOut:
    """B3. He paid this shop everything he owes it, by UPI. Paytm moves the
    money; the book records which entries it paid, and the shop is told."""
    now = clock.now()
    p = ledger.pay_upi(con, body.person_id, shop_id, now)
    mine = chat.my_udhaar(con, str(body.person_id), now.date())
    return PaidOut(
        shop=views.shop_out(p.shop),
        amount_paise=p.amount_paise,
        paid_at=now,
        method="upi",
        settled_in=p.settled_in,
        entry_ids=p.entry_ids,
        elsewhere=[m for m in mine.shops if m.shop.id != shop_id and m.balance_paise > 0],
    )


@router.post("/shops/{shop_id}/invite/accept", status_code=204)
def accept(shop_id: str, body: PersonIn, con: Con) -> None:
    """He said yes to the shop's invite, on his own phone."""
    ledger.accept(con, shop_id, body.person_id, clock.now())


@router.post("/shops/{shop_id}/invite/decline", status_code=204)
def decline(shop_id: str, body: PersonIn, con: Con) -> None:
    ledger.decline(con, shop_id, body.person_id)


@router.get("/demo/phones")
def demo_phones(con: Con) -> list[DemoPhoneOut]:
    """Whose phone the customer side can be, for the demo: every customer with a
    Paytm account in any shop's book, once each, and the synthetic accounts in
    nobody's book yet. Someone kept by name only has no phone, so is not here."""
    out = [
        DemoPhoneOut(
            person_id=p.person_id,
            name=p.display_name,
            tag=p.tag,
            state="linked" if p.linked else "invited",
            shops=p.shops,
        )
        for p in customers.phones(con)
    ]
    known = {p.person_id for p in out}
    out += [
        DemoPhoneOut(person_id=a.person_id, name=a.name, tag=None, state="paytm", shops=0)
        for a in directory.ACCOUNTS
        if a.person_id not in known
    ]
    return sorted(out, key=lambda p: p.name.casefold())
