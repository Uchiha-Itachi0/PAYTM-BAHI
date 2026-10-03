"""The munshi's words for other people: a reminder, and replies to suggest.

Code has already decided everything that matters: who gets a reminder, for how
much, and at what hour (domain/tonight.py). The model only writes the sentence,
in the customer's own language, and our code holds it to what was decided before
anyone sees it:

- the only figure in a reminder is his balance, exactly, so a reminder can never
  name a different sum, a date or a deadline (Rule 1);
- it is short enough to read at a glance.

If the model is offline, slow or writes something that fails a check, the
reminder is our own sentence (`wording.reminder`) and says so. Suggested replies
are only offered: the shopkeeper taps one to send it, or ignores them.

`promise` reads a customer's chat message for a day he promises to pay by (M3).
The model only reads the day; code keeps his own words, and only a day from
today to three months on.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Literal

from bahi import voice
from bahi.domain import wording
from bahi.domain.money import rupees
from bahi.voice import sarvam

log = logging.getLogger(__name__)

#: A reminder longer than this is not read at a glance.
LONGEST = 240
#: How much of the chat the model is shown.
RECENT = 8

_RUPEES = re.compile(r"(?:₹|\brs\.?|\binr)\s*([\d,]+(?:\.\d+)?)", re.I)
_DIGIT = re.compile(r"\d")


@dataclass(frozen=True, slots=True)
class Said:
    """A line in the thread, as the model is shown it."""

    who: Literal["shop", "customer", "bahi"]
    text: str


@dataclass(frozen=True, slots=True)
class Written:
    body: str
    #: munshi: the model wrote it and it passed. words: our own sentence.
    by: Literal["munshi", "words"]


def _chat(said: Sequence[Said], customer: str) -> str:
    if not said:
        return "(no messages yet)"
    who = {"shop": "Shop", "customer": customer, "bahi": "BAHI"}
    return "\n".join(f"{who[s.who]}: {s.text}" for s in said[-RECENT:])


def fits(text: str, balance_paise: int) -> bool:
    """A reminder names his balance and no other figure: no other sum, no date,
    no count of days. Short, and not empty."""
    text = text.strip()
    if not text or len(text) > LONGEST:
        return False
    for m in _RUPEES.finditer(text):
        if round(float(m.group(1).replace(",", "")) * 100) != balance_paise:
            return False
    return not _DIGIT.search(_RUPEES.sub("", text))


REMINDER = """You write one short chat message from a kirana shop to a customer who has
udhaar (goods on credit) with it. The shop has decided to send it; you only write it.

- Ask, never chase: warm and respectful, like a neighbour. No pressure, no threat,
  no guilt, no "overdue".
- Say the amount exactly as given, once. No other number of any kind: no date, no
  deadline, no count of days, no "by Friday".
- Say it's fine to tell the shop if there is any difficulty.
- One or two sentences, under 200 characters.
- Write in the language and script the customer uses in the chat. If there is no
  chat, write Hinglish in English letters.

Reply as JSON: {"message": "..."}."""

REMINDER_SCHEMA = {
    "type": "object",
    "properties": {"message": {"type": "string"}},
    "required": ["message"],
    "additionalProperties": False,
}


def reminder(
    customer: str, shop: str, balance_paise: int, said: Sequence[Said]
) -> Written:
    """The reminder's words: the munshi's, checked, or our own."""
    ours = Written(wording.reminder(customer, shop, balance_paise), "words")
    key = voice.api_key()
    if voice.offline() or key is None:
        return ours
    user = (
        f"Shop: {shop}\nCustomer: {customer}\nAmount: {rupees(balance_paise)}\n\n"
        f"Their chat so far:\n{_chat(said, customer)}"
    )
    try:
        answer = sarvam.chat_json(
            REMINDER, user, REMINDER_SCHEMA, key=key, name="reminder"
        )
    except sarvam.SarvamError as e:
        log.warning("the munshi wrote no reminder for %s: %s", customer, e)
        return ours
    text = str(answer.get("message") or "").strip()
    if not fits(text, balance_paise):
        log.warning("the munshi's reminder for %s failed our checks: %r", customer, text)
        return ours
    return Written(text, "munshi")


REPLIES = """You help a kirana shopkeeper answer a customer in their chat. Suggest two
short replies the shopkeeper might send next: different from each other, friendly
and respectful, a few words each.

- Reply in the language and script the customer used.
- Never ask for payment by a date, and never name an amount that isn't already in
  the chat.
- If the customer has a problem, be kind about it.

Reply as JSON: {"replies": ["...", "..."]}."""

REPLIES_SCHEMA = {
    "type": "object",
    "properties": {"replies": {"type": "array", "items": {"type": "string"}}},
    "required": ["replies"],
    "additionalProperties": False,
}


def replies(customer: str, shop: str, said: Sequence[Said]) -> list[str]:
    """Up to two replies for the shopkeeper to tap, or none when voice is off."""
    key = voice.api_key()
    if voice.offline() or key is None or not said:
        return []
    user = f"Shop: {shop}\nCustomer: {customer}\n\nThe chat:\n{_chat(said, customer)}"
    try:
        answer = sarvam.chat_json(REPLIES, user, REPLIES_SCHEMA, key=key, name="replies")
    except sarvam.SarvamError as e:
        log.warning("the munshi suggested no replies: %s", e)
        return []
    out = [str(r).strip() for r in answer.get("replies") or [] if str(r).strip()]
    return [r for r in out if len(r) <= LONGEST][:2]


PROMISE = """You read one chat message that a kirana shop's customer sent the shop, where
the customer has udhaar (goods on credit). Decide whether it promises to pay, in
full or in part, by a particular day.

- A day counts in any form: a date (5 तारीख, 10th), a weekday (सोमवार), कल,
  परसों, "next week", "when salary comes on the 1st".
- Only the customer's own promise counts. A question, a complaint, or "I'll pay
  soon" with no day is not a promise.
- Today is {today}. Give pay_by as the calendar date the day means (YYYY-MM-DD),
  the first such date on or after today.

Reply as JSON: {{"promise": true or false, "pay_by": "YYYY-MM-DD" or ""}}."""

PROMISE_SCHEMA = {
    "type": "object",
    "properties": {"promise": {"type": "boolean"}, "pay_by": {"type": "string"}},
    "required": ["promise", "pay_by"],
    "additionalProperties": False,
}

#: A promise further off than this is not taken as one to wait for.
FARTHEST_PROMISE_DAYS = 90


def promise(message: str, today: date) -> date | None:
    """The day his message promises to pay by, or None: none promised, the
    model is off, or the day it named can't be right (past, or months away)."""
    key = voice.api_key()
    if voice.offline() or key is None or not message.strip():
        return None
    try:
        answer = sarvam.chat_json(
            PROMISE.format(today=today.strftime("%A %d %B %Y")),
            message.strip(),
            PROMISE_SCHEMA,
            key=key,
            name="promise",
        )
    except sarvam.SarvamError as e:
        log.warning("the munshi couldn't read a promise: %s", e)
        return None
    if answer.get("promise") is not True:
        return None
    try:
        day = date.fromisoformat(str(answer.get("pay_by") or "").strip())
    except ValueError:
        return None
    if not today <= day <= today + timedelta(days=FARTHEST_PROMISE_DAYS):
        log.warning("a promise for %s isn't one to wait for", day)
        return None
    return day
