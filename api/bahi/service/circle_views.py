"""Circles as a member's phone shows them. Formatting and gathering only."""

from __future__ import annotations

from datetime import date

from bahi.domain.circle import DEFAULT_ON_UDHAAR, setting
from bahi.service import circle, views
from bahi.service.circle_models import (
    CircleEntryOut,
    CircleOut,
    CirclePaymentOut,
    CircleSummaryOut,
    ListedOut,
    MemberOut,
    MyCirclesOut,
    NoticeOut,
)
from bahi.store import circles, entries, shops
from bahi.store.circles import Circle, Share
from bahi.store.db import Conn
from bahi.store.entries import EntryRef


def _state(e: EntryRef, today: date) -> str:
    if e.status == "settled":
        return "paid"
    return "open" if circle.is_open(e, today) else "closed"


def _entries(
    con: Conn, listed: list[Share], viewer: str, today: date
) -> list[CircleEntryOut]:
    found = entries.by_ids(con, [s.entry_id for s in listed])
    paid = circles.payments(con, list(found))
    debtors = [e.person_id for e in found.values() if e.person_id]
    who = circle.names(con, debtors + [p.paid_by for p in paid if p.paid_by])
    out = []
    for s in listed:
        e = found[s.entry_id]
        debtor = e.person_id or ""
        state = _state(e, today)
        shop = shops.get(con, e.shop_id)
        assert shop is not None
        out.append(
            CircleEntryOut(
                entry_id=e.id,
                debtor_name=who.get(debtor, circle.SOMEONE),
                debtor_person_id=debtor,
                mine=debtor == viewer,
                shop=views.shop_out(shop),
                amount_paise=e.amount_paise,
                paid_paise=e.paid_paise,
                left_paise=e.amount_paise - e.paid_paise if state == "open" else 0,
                recorded_at=e.recorded_at,
                shared_at=s.shared_at,
                state=state,  # type: ignore[arg-type]
                payments=[
                    CirclePaymentOut(
                        payer_name=who[p.paid_by] if p.paid_by else who.get(debtor, ""),
                        by_debtor=p.paid_by is None,
                        amount_paise=p.amount_paise,
                        paid_at=p.paid_at,
                    )
                    for p in paid
                    if p.entry_id == e.id
                ],
            )
        )
    return out


def circle_out(con: Conn, c: Circle, viewer: str, today: date) -> CircleOut:
    members = circles.members(con, c.id)
    who = circle.names(con, [m.person_id for m in members])
    listed = _entries(con, circles.listed(con, c.id), viewer, today)
    return CircleOut(
        id=c.id,
        name=c.name,
        created_at=c.created_at,
        members=[
            MemberOut(
                person_id=m.person_id,
                name=who[m.person_id],
                me=m.person_id == viewer,
                made_it=m.person_id == c.created_by,
            )
            for m in members
        ],
        entries=listed,
        open_paise=sum(e.left_paise for e in listed),
    )


def _summary(con: Conn, c: Circle, today: date) -> CircleSummaryOut:
    members = circles.members(con, c.id)
    who = circle.names(con, [m.person_id for m in members])
    found = entries.by_ids(con, [s.entry_id for s in circles.listed(con, c.id)])
    still = [e for e in found.values() if circle.is_open(e, today)]
    return CircleSummaryOut(
        id=c.id,
        name=c.name,
        members=[who[m.person_id] for m in members],
        open_paise=sum(e.amount_paise - e.paid_paise for e in still),
        open_count=len(still),
    )


def mine(con: Conn, person_id: str, today: date) -> MyCirclesOut:
    """Their circles, their setting, their notes, and which of their entries are on
    a list."""
    chosen = circles.chosen(con, person_id)
    mine_ = circles.of_person(con, person_id)
    notes = circles.notices(con, person_id)
    about = entries.by_ids(con, [n.entry_id for n in notes if n.entry_id])
    by_id = {c.id: c for c in mine_}
    listed = circles.listed_for(con, person_id)
    named = {s.circle_id: circles.get(con, s.circle_id) for s in listed}
    return MyCirclesOut(
        person_id=person_id,
        on_udhaar=setting(chosen),
        chosen=chosen is not None,
        default_on_udhaar=DEFAULT_ON_UDHAAR,
        circles=[_summary(con, c, today) for c in mine_],
        notices=[
            NoticeOut(
                id=n.id,
                kind=n.kind,  # type: ignore[arg-type]
                body=n.body,
                circle_id=n.circle_id if n.circle_id in by_id else None,
                entry_id=n.entry_id,
                shop_id=about[n.entry_id].shop_id if n.entry_id in about else None,
                created_at=n.created_at,
            )
            for n in notes
        ],
        listed=[
            ListedOut(
                entry_id=s.entry_id,
                circle_id=s.circle_id,
                circle_name=c.name,
            )
            for s in listed
            if (c := named[s.circle_id]) is not None
        ],
    )
