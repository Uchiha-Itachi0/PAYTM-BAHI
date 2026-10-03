"""Domain and store objects turned into wire models. Formatting only, no rules."""

from __future__ import annotations

from bahi.domain.book import Book, Line
from bahi.domain.resolve import Person, Picked
from bahi.domain.speak import say
from bahi.domain.wording import button
from bahi.service.ledger import Hearing
from bahi.service.models import (
    AskOut,
    BookOut,
    EntryOut,
    HeardOut,
    HeardSource,
    LineOut,
    PersonOut,
    PickedOut,
    ReadbackOut,
    RhythmOut,
    ShopBookOut,
    ShopOut,
)
from bahi.store.entries import EntryRef
from bahi.store.shops import Shop


def shop_out(s: Shop) -> ShopOut:
    return ShopOut(id=s.id, name=s.name, locality=s.locality)


def line_out(ln: Line) -> LineOut:
    r = ln.rhythm
    return LineOut(
        customer_id=ln.customer_id,
        display_name=ln.display_name,
        tag=ln.tag,
        joined=ln.joined,
        balance_paise=ln.balance_paise,
        day=ln.day,
        chip=ln.chip,
        rhythm=RhythmOut(
            n=r.n, median_gap=r.median_gap, max_gap=r.max_gap, last_paid=r.last_paid
        ),
    )


def book_out(shop: Shop, b: Book) -> ShopBookOut:
    return ShopBookOut(
        today=b.today,
        shop=shop_out(shop),
        book=BookOut(
            customer_count=b.customer_count,
            invited_count=b.invited_count,
            owing_count=b.owing_count,
            outstanding_paise=b.outstanding_paise,
            lines=[line_out(ln) for ln in b.lines],
        ),
    )


def entry_out(e: EntryRef) -> EntryOut:
    return EntryOut(
        id=e.id,
        customer_id=e.customer_id,
        display_name=e.display_name,
        shop_id=e.shop_id,
        shop_name=e.shop_name,
        amount_paise=e.amount_paise,
        paid_paise=e.paid_paise,
        status=e.status,  # type: ignore[arg-type]
        recorded_at=e.recorded_at,
        note=e.note,
        spoken_text=e.spoken_text,
        corrects_entry_id=e.corrects_entry_id,
        acknowledged_at=e.acknowledged_at,
        button=button(e.amount_paise),
    )


def heard_out(hearing: Hearing, transcript: str, source: HeardSource) -> HeardOut:
    h = hearing.heard

    def person(p: Person) -> PersonOut:
        return PersonOut(
            customer_id=p.ref, display_name=p.name, scan_id=hearing.scans.get(p.ref)
        )

    who = hearing.who
    readback = None
    if h.amount_paise is not None:
        try:
            said = say(h.amount_paise)
            readback = ReadbackOut(roman=said.roman, devanagari=said.devanagari)
        except ValueError:
            readback = None  # beyond what is said aloud; the figure still shows
    return HeardOut(
        transcript=transcript,
        source=source,
        name=h.name,
        amount_paise=h.amount_paise,
        amount_words=h.amount_words,
        problem=h.problem,
        readback=readback,
        who=(
            PickedOut(how=who.how, person=person(who.person))
            if isinstance(who, Picked)
            else AskOut(why=who.why, among=[person(p) for p in who.among])
        ),
    )
