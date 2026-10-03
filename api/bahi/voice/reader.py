"""Sarvam-105B reads what the shopkeeper said, and drafts the entry.

The prompt and the JSON schema are the ones the 1,338-recording test measured,
word for word; change them and `make voice-eval` no longer speaks for them. The
model sees the transcript, who is at the counter, and a shortlist of customers
whose names sound like words said (`domain.who.shortlist`). It returns a draft;
`domain.check` decides what, if anything, the screen may do with it.

Customers are shown to the model as c00, c01, … as in the test, not by their
UUIDs, which a model can miscopy. An id it returns that we never showed stays as
it was, and the checker refuses the draft.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

from bahi.domain.check import Draft
from bahi.domain.who import Person
from bahi.voice import sarvam

SYSTEM = """You read what a kirana shopkeeper said on the "Add udhaar" screen and draft one entry for his udhaar (credit) book.
You get: the transcript (speech recognition: names may be misspelled, in Devanagari or roman), who is at the counter (people who scanned the shop's QR just now), and a SHORTLIST of customers from the shop's book whose names sound like words in the transcript or whose tag matches a number said. Each has an id, a name and a tag (room, wing, work).
Return JSON only.
- intent: "udhaar" by default: any amount written against a customer. "payment" only when the customer gave money back ("X ne 200 diye", "X se 200 aaye", "jama", "wapas"). "unclear" if no amount was said.
- amount_words: the exact words of the transcript that state the final amount, copied character for character. If he corrected himself, the corrected amount. amount_rupees: that amount as a number. Numbers that describe the person (room 1006, "das sau chhe wale") are NOT the amount.
- customer_id: choose ONLY an id from the shortlist or the counter. Judge names by how they sound: speech recognition misspells them. Use surnames, nicknames and tag details (room, wing, work) that were said. If the person said is at the counter, that is them. Pick a customer only when exactly one fits what was said. If several fit equally (for example the same name and no detail said), return null and put every id that fits in candidates. If no shortlisted customer fits the name said, return null with empty candidates (a new customer).
- person_words: the exact words of the transcript that name or describe the customer (name, surname, nickname, room, wing), copied character for character. null if no customer was named.
- reason: one short sentence.
Never invent an id or an amount that is not in the input."""  # noqa: E501

_NULLABLE_STRING = {"type": ["string", "null"]}
SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "intent",
        "customer_id",
        "candidates",
        "amount_words",
        "amount_rupees",
        "reason",
        "person_words",
    ],
    "properties": {
        "intent": {"type": "string", "enum": ["udhaar", "payment", "unclear"]},
        "customer_id": _NULLABLE_STRING,
        "candidates": {"type": "array", "items": {"type": "string"}},
        "amount_words": _NULLABLE_STRING,
        "amount_rupees": {"type": ["number", "null"]},
        "reason": {"type": "string"},
        "person_words": _NULLABLE_STRING,
    },
}

_INTENTS = ("udhaar", "payment", "unclear")


def message(
    transcript: str, waiting: Sequence[Person], shown: Sequence[Person]
) -> tuple[str, dict[str, str]]:
    """The user message, and short id -> customer id."""
    short: dict[str, str] = {}  # customer id -> short id
    for p in (*shown, *waiting):
        short.setdefault(p.ref, f"c{len(short):02d}")

    def card(p: Person) -> dict[str, str | None]:
        return {"id": short[p.ref], "name": p.name, "tag": p.tag}

    body = {
        "transcript": transcript,
        "at_the_counter": [card(p) for p in waiting],
        "shortlist": [card(p) for p in shown],
    }
    return json.dumps(body, ensure_ascii=False), {s: ref for ref, s in short.items()}


def _text(v: Any) -> str | None:
    return v if isinstance(v, str) and v else None


def draft(answer: dict[str, Any], refs: dict[str, str]) -> Draft:
    """The model's answer as a Draft. Raises SarvamError if it is not the shape
    the schema promised."""
    intent = answer.get("intent")
    rupees = answer.get("amount_rupees")
    candidates = answer.get("candidates")
    if (
        intent not in _INTENTS
        or not (rupees is None or isinstance(rupees, int | float))
        or not isinstance(candidates, list)
    ):
        raise sarvam.SarvamError("Sarvam-105B's reply did not follow the schema")
    cid = _text(answer.get("customer_id"))
    return Draft(
        intent=intent,
        amount_words=_text(answer.get("amount_words")),
        amount_rupees=float(rupees) if rupees is not None else None,
        person_words=_text(answer.get("person_words")),
        customer_id=refs.get(cid, cid) if cid else None,
        candidates=tuple(refs.get(c, c) for c in candidates if isinstance(c, str)),
        reason=str(answer.get("reason") or ""),
    )


def read(
    transcript: str,
    waiting: Sequence[Person],
    shown: Sequence[Person],
    *,
    key: str,
) -> Draft:
    """One reading. A reply that is not the JSON asked for is asked for once more,
    as in the test; after that, SarvamError, and our parser reads instead."""
    user, refs = message(transcript, waiting, shown)
    for attempt in (1, 2):
        try:
            answer = sarvam.chat_json(SYSTEM, user, SCHEMA, key=key, name="draft")
            return draft(answer, refs)
        except sarvam.SarvamError as e:
            if attempt == 2 or "not the JSON" not in str(e):
                raise
    raise AssertionError("unreachable")
