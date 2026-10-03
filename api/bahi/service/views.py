"""Domain and store objects turned into wire models. Formatting only, no rules."""

from __future__ import annotations

from bahi.domain.book import Book, Line
from bahi.domain.check import Check, Checked
from bahi.domain.money import rupees
from bahi.domain.speak import say
from bahi.domain.who import Ask, Person, Picked
from bahi.domain.wording import button
from bahi.service.ledger import Answer, Hearing
from bahi.service.models import (
    AnswerOut,
    AskOut,
    BookOut,
    CheckOut,
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
        waiting_paise=ln.waiting_paise,
        disputed_paise=ln.disputed_paise,
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
            waiting_paise=b.waiting_paise,
            disputed_paise=b.disputed_paise,
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


def _says(c: Check, checked: Checked) -> str:
    words, name = checked.amount_words, checked.person_words
    who = checked.who
    if c.kind == "amount_said":
        return f"“{words}” was said" if c.ok else f"“{words}” is not in what was said"
    if c.kind == "amount_read":
        if c.ok and checked.amount_paise is not None:
            return f"our parser reads “{words}” as {rupees(checked.amount_paise)} too"
        if checked.reader == "rules":
            return f"“{words}” is not one clear amount"
        return f"our parser reads “{words}” as a different amount"
    if c.kind == "person_said":
        return f"“{name}” was said" if c.ok else f"“{name}” is not in what was said"
    if isinstance(who, Picked):
        return f"“{name}” fits one customer: {who.person.name}"
    assert isinstance(who, Ask)
    if who.why == "several":
        return f"“{name}” fits {len(who.among)} customers"
    if who.why == "maybe":
        return f"“{name}” only sounds a little like " + ", ".join(
            p.name for p in who.among
        )
    return f"“{name}” fits nobody in your book"


def _person(p: Person, scans: dict[str, str]) -> PersonOut:
    return PersonOut(
        customer_id=p.ref, display_name=p.name, tag=p.tag, scan_id=scans.get(p.ref)
    )


def _who(who: Picked | Ask, scans: dict[str, str]) -> PickedOut | AskOut:
    if isinstance(who, Picked):
        return PickedOut(how=who.how, person=_person(who.person, scans))
    return AskOut(why=who.why, among=[_person(p, scans) for p in who.among])


def answer_out(a: Answer, transcript: str, source: HeardSource) -> AnswerOut:
    return AnswerOut(transcript=transcript, source=source, who=_who(a.who, a.scans))


def heard_out(hearing: Hearing, transcript: str, source: HeardSource) -> HeardOut:
    c = hearing.checked
    readback = None
    if c.amount_paise is not None:
        try:
            said = say(c.amount_paise)
            readback = ReadbackOut(roman=said.roman, devanagari=said.devanagari)
        except ValueError:
            readback = None  # beyond what is said aloud; the figure still shows
    return HeardOut(
        transcript=transcript,
        source=source,
        reader=c.reader,
        fallback=hearing.fallback,
        intent=c.intent,
        name=c.person_words,
        amount_paise=c.amount_paise,
        amount_words=c.amount_words,
        problem=c.problem,
        checks=[CheckOut(kind=k.kind, ok=k.ok, says=_says(k, c)) for k in c.checks],
        readback=readback,
        who=_who(c.who, hearing.scans),
    )
