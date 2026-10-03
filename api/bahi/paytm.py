"""Finding a Paytm account from a mobile number or a UPI ID.

In Paytm this is its own account lookup. For the demo it reads a synthetic
directory (data/directory.py), and any other valid mobile number stands for an
account of its own, so the flow can be tried with any number. Either way the
number goes in, the account comes out, and the number is never stored: the book
keeps only the account.
"""

from __future__ import annotations

import re

from data.directory import ACCOUNTS, Account
from data.world import uid

_NOT_DIGITS = re.compile(r"\D")


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
