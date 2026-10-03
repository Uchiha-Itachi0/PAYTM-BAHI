"""The reader's draft, checked by code. Nothing a model says is taken on trust.

Sarvam-105B reads what the shopkeeper said and drafts the entry: udhaar or
payment, the words that state the amount and the amount they state, and the words
that name the person. Before any of it reaches the screen:

- the amount words must be in the transcript, and our parser (`parse.heard`) must
  read them as the amount the draft states, to the rupee;
- a customer the draft names must be one it was shown;
- who the entry is for is decided by `who`, from the quoted words, never by the
  draft's own pick.

When Sarvam-105B cannot be asked (offline, no key, no answer, or an answer that
is not the JSON asked for), our parser is the reader: its amount and the words it
left over go through the same `who`. Either way the shopkeeper hears the amount
back and has three seconds to cancel, and the customer confirms on his own phone.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from bahi.domain.parse import heard
from bahi.domain.who import Ask, Person, Picked, who

Intent = Literal["udhaar", "payment", "unclear"]
Reader = Literal["sarvam", "rules"]
#: no_amount / unclear_amount: the words hold no amount, or not one clear one.
#: amount_not_said: the draft's amount words are not in what was said.
#: amount_mismatch: our parser reads the draft's words as a different amount.
#: invented_customer: the draft named a customer it was never shown.
Problem = Literal[
    "no_amount",
    "unclear_amount",
    "amount_not_said",
    "amount_mismatch",
    "invented_customer",
]
#: amount_said: the amount words are in the transcript.
#: amount_read: our parser reads them as the amount.
#: person_said: the words naming the person were said.
#: person_fits: they fit exactly one customer.
CheckKind = Literal["amount_said", "amount_read", "person_said", "person_fits"]


@dataclass(frozen=True, slots=True)
class Draft:
    """What Sarvam-105B returned, field for field as its JSON schema names them."""

    intent: Intent
    amount_words: str | None
    amount_rupees: float | None
    person_words: str | None
    customer_id: str | None
    candidates: tuple[str, ...]
    reason: str


@dataclass(frozen=True, slots=True)
class Check:
    kind: CheckKind
    ok: bool


@dataclass(frozen=True, slots=True)
class Checked:
    """What the screen may act on. `amount_paise` is None unless every amount check
    passed; then it is our parser's number, not the draft's."""

    reader: Reader
    intent: Intent
    amount_paise: int | None
    amount_words: str | None
    person_words: str | None
    problem: Problem | None
    who: Picked | Ask
    checks: tuple[Check, ...]


def _person(
    words: str | None,
    transcript: str | None,
    waiting: Sequence[Person],
    book: Sequence[Person],
) -> tuple[Picked | Ask, list[Check]]:
    decided = who(words, waiting, book, transcript=transcript)
    checks: list[Check] = []
    if words:
        if transcript is not None:
            checks.append(Check("person_said", decided != Ask("not_said", ())))
        if not (isinstance(decided, Ask) and decided.why == "not_said"):
            checks.append(Check("person_fits", isinstance(decided, Picked)))
    return decided, checks


def check_draft(
    transcript: str,
    draft: Draft,
    shown: Sequence[Person],
    waiting: Sequence[Person],
    book: Sequence[Person],
) -> Checked:
    """Sarvam-105B's draft, held to the words. `shown` is the shortlist it was given."""
    decided, person_checks = _person(draft.person_words, transcript, waiting, book)

    def refused(problem: Problem, checks: Sequence[Check] = ()) -> Checked:
        return Checked(
            "sarvam",
            draft.intent,
            None,
            draft.amount_words,
            draft.person_words,
            problem,
            decided,
            (*checks, *person_checks),
        )

    allowed = {p.ref for p in shown} | {p.ref for p in waiting}
    if draft.customer_id is not None and draft.customer_id not in allowed:
        return refused("invented_customer")
    if draft.amount_words is None or draft.amount_rupees is None:
        return refused("no_amount")
    if draft.amount_words not in transcript:
        return refused("amount_not_said", (Check("amount_said", False),))
    said = Check("amount_said", True)
    paise = heard(draft.amount_words).amount_paise
    if paise is None or paise != round(draft.amount_rupees * 100):
        return refused("amount_mismatch", (said, Check("amount_read", False)))
    return Checked(
        "sarvam",
        draft.intent,
        paise,
        draft.amount_words,
        draft.person_words,
        None,
        decided,
        (said, Check("amount_read", True), *person_checks),
    )


def check_rules(
    transcript: str, waiting: Sequence[Person], book: Sequence[Person]
) -> Checked:
    """Our parser as the reader: udhaar only, the amount by rule, and the words
    left over as the name. The words come from the transcript itself, so there is
    no quote to hold to it."""
    h = heard(transcript)
    decided, person_checks = _person(h.name, None, waiting, book)
    amount = [Check("amount_read", h.problem is None)] if h.amount_words else []
    return Checked(
        "rules",
        "udhaar" if h.amount_paise is not None else "unclear",
        h.amount_paise,
        h.amount_words,
        h.name,
        h.problem,
        decided,
        (*amount, *person_checks),
    )
