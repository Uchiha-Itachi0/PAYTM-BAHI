"""The family circle, in the Paytm app.

Every call names the person acting, and a circle is seen only by its members.
No route here is ever called by the shop's screens: the shop does not see the
circle.
"""

from __future__ import annotations

from fastapi import APIRouter, Request, Response

from bahi import clock
from bahi.service import circle, circle_views, views
from bahi.service.circle_models import (
    CircleIn,
    CircleOut,
    CirclePaidOut,
    CirclePayIn,
    MyCirclesOut,
    OnUdhaarIn,
    ShareIn,
)
from bahi.service.deps import Con, etagged
from bahi.service.errors import NotFound
from bahi.service.models import PersonIn
from bahi.store import circles, shops

router = APIRouter(tags=["circle"])


@router.get("/people/{person_id}/circles", response_model=MyCirclesOut)
def my_circles(person_id: str, request: Request, con: Con) -> Response:
    """C1. Their circles, what happens to their next udhaar, and their notes."""
    return etagged(request, circle_views.mine(con, person_id, clock.today()))


@router.post("/people/{person_id}/circle-setting")
def set_on_udhaar(person_id: str, body: OnUdhaarIn, con: Con) -> MyCirclesOut:
    """C1. When I take udhaar: send it to my circle, or keep it to myself."""
    now = clock.now()
    circle.set_on_udhaar(con, person_id, body.on_udhaar, now)
    return circle_views.mine(con, person_id, now.date())


@router.post("/circles", status_code=201)
def create(body: CircleIn, con: Con) -> CircleOut:
    """C2. A new circle, with the people behind these mobile numbers."""
    now = clock.now()
    pid = str(body.person_id)
    c = circle.create(con, pid, body.name, body.phones, now)
    return circle_views.circle_out(con, c, pid, now.date())


@router.get("/circles/{circle_id}", response_model=CircleOut)
def get_circle(circle_id: str, person_id: str, request: Request, con: Con) -> Response:
    """C3. The circle: who is in it, and its list. Only for a member."""
    c = circle.member_of(con, circle_id, person_id)
    return etagged(request, circle_views.circle_out(con, c, person_id, clock.today()))


@router.post("/circles/{circle_id}/leave", status_code=204)
def leave(circle_id: str, body: PersonIn, con: Con) -> None:
    """C3. They leave: their entries come off the list and stay theirs to pay."""
    circle.leave(con, circle_id, str(body.person_id), clock.now())


@router.post("/circles/{circle_id}/share")
def share(circle_id: str, body: ShareIn, con: Con) -> CircleOut:
    """C4. "Add to circle": one of their own open entries, onto this list."""
    now = clock.now()
    pid = str(body.person_id)
    circle.share(con, circle_id, str(body.entry_id), pid, now)
    c = circle.member_of(con, circle_id, pid)
    return circle_views.circle_out(con, c, pid, now.date())


@router.post("/circles/{circle_id}/entries/{entry_id}/take-back", status_code=204)
def take_back(circle_id: str, entry_id: str, body: PersonIn, con: Con) -> None:
    """C4. The debtor takes their entry off the list."""
    circle.take_back(con, circle_id, entry_id, str(body.person_id), clock.now())


@router.post("/circles/{circle_id}/entries/{entry_id}/pay")
def pay(circle_id: str, entry_id: str, body: CirclePayIn, con: Con) -> CirclePaidOut:
    """C5. A member pays an entry on the list by UPI, all or part. The money goes
    to the shop, against the debtor's entry; nobody owes the payer anything."""
    now = clock.now()
    p = circle.pay(con, circle_id, entry_id, str(body.person_id), now, body.amount_paise)
    s = shops.get(con, p.entry.shop_id)
    if s is None:
        raise NotFound(f"no shop {p.entry.shop_id}")
    return CirclePaidOut(
        circle_id=p.circle.id,
        entry_id=p.entry.id,
        shop=views.shop_out(s),
        debtor_name=circle.names(con, [p.entry.person_id or ""])[p.entry.person_id or ""],
        amount_paise=p.amount_paise,
        left_paise=p.entry.amount_paise - p.entry.paid_paise,
        paid_at=now,
    )


@router.post("/circle-notices/{notice_id}/done", status_code=204)
def notice_done(notice_id: str, body: PersonIn, con: Con) -> None:
    """A note read and put aside."""
    if not circles.done(con, notice_id, str(body.person_id), clock.now()):
        raise NotFound("no such note waiting")
