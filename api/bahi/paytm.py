"""Paytm's side of a person, simulated: finding an account from a number, and
the account itself.

In Paytm the person is signed in, and the name on the account, its UPI ID and
its mobile number come from there; nobody types them into BAHI and nobody can
change them in it. For the demo:

- lookup() reads a synthetic directory (data/directory.py), and any other valid
  mobile number stands for an account of its own, so the invite flow can be tried
  with any number. The number goes in, the account comes out, and BAHI's book
  keeps only the account.
- The accounts themselves live in the `paytm` schema, beside the book and not in
  it: BAHI's tables hold no phone number. A phone that scans for the first time
  signs up with the name it gives; its number and UPI ID are made up from its id,
  once, and never change. The shop sees the name and the UPI ID, never the number.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime

from psycopg.rows import class_row

from bahi.store.db import Conn
from data.directory import ACCOUNTS, Account
from data.world import uid

_NOT_DIGITS = re.compile(r"\D")
_NOT_HANDLE = re.compile(r"[^a-z]")
BANKS = ("ptsbi", "pthdfc", "ptaxis", "ptyes")
#: The languages Sarvam hears and speaks.
LANGUAGES = (
    "hi-IN",
    "en-IN",
    "mr-IN",
    "gu-IN",
    "bn-IN",
    "ta-IN",
    "te-IN",
    "kn-IN",
    "ml-IN",
    "pa-IN",
    "od-IN",
)


def mobile(text: str) -> str | None:
    """ "+91 98765 43210" -> "9876543210". None unless it is an Indian mobile."""
    digits = _NOT_DIGITS.sub("", text)
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    elif len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]
    return digits if len(digits) == 10 and digits[0] in "6789" else None


def lookup(query: str) -> Account | None:
    """The account behind a mobile number or UPI ID, or None.

    A number not in the directory stands for a demo account of its own: named
    only by its last digits, because Paytm would tell us the name and we can't.
    """
    q = query.strip().lower()
    if "@" in q:
        return next((a for a in ACCOUNTS if a.upi == q), None)
    number = mobile(q)
    if number is None:
        return None
    known = next((a for a in ACCOUNTS if a.phone == number), None)
    if known is not None:
        return known
    return Account(
        person_id=str(uid("paytm", number)),
        name=f"Paytm account ••{number[-4:]}",
        phone=number,
        upi="",
    )


def named(account: Account) -> bool:
    """Paytm told us whose account it is (a directory account)."""
    return bool(account.upi)


# ── the account ──────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class PaytmAccount:
    person_id: str
    name: str
    phone: str
    upi: str


def made_up(person_id: str, name: str, attempt: int = 0) -> tuple[str, str]:
    """A demo account's mobile number and UPI ID, from its id: the same every
    time, so the seed and a live sign-up agree. `attempt` > 0 only after a clash."""
    h = int(hashlib.sha256(f"{person_id}:{attempt}".encode()).hexdigest(), 16)
    phone = f"{9 - h % 3}{(h // 3) % 10**9:09d}"
    handle = _NOT_HANDLE.sub("", (name.split() or ["paytm"])[0].lower()) or "paytm"
    upi = f"{handle}{(h // 7) % 100:02d}@{BANKS[(h // 11) % len(BANKS)]}"
    return phone, upi


SELECT = "SELECT person_id::text AS person_id, name, phone, upi FROM paytm.accounts"


def account(con: Conn, person_id: str) -> PaytmAccount | None:
    with con.cursor(row_factory=class_row(PaytmAccount)) as cur:
        return cur.execute(SELECT + " WHERE person_id = %s", (person_id,)).fetchone()


def accounts(con: Conn, person_ids: list[str]) -> dict[str, PaytmAccount]:
    if not person_ids:
        return {}
    with con.cursor(row_factory=class_row(PaytmAccount)) as cur:
        rows = cur.execute(
            SELECT + " WHERE person_id = ANY(%s::uuid[])", (person_ids,)
        ).fetchall()
    return {a.person_id: a for a in rows}


def sign_up(con: Conn, person_id: str, name: str, now: datetime) -> PaytmAccount:
    """The account for this phone, made on its first scan with the name it
    gave. Already there: unchanged, whatever name is given now."""
    found = account(con, person_id)
    if found is not None:
        return found
    name = " ".join(name.split())[:60] or "Paytm user"
    for attempt in range(8):
        phone, upi = made_up(person_id, name, attempt)
        row = con.execute(
            "INSERT INTO paytm.accounts (person_id, name, phone, upi, created_at) "
            "VALUES (%s, %s, %s, %s, %s) ON CONFLICT DO NOTHING RETURNING person_id",
            (person_id, name, phone, upi, now),
        ).fetchone()
        if row is not None:
            break
    made = account(con, person_id)
    assert made is not None, "eight clashes in a row"
    return made
