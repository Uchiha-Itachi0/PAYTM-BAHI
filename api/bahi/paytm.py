"""Finding a Paytm account from a mobile number or a UPI ID.

In Paytm this is its own account lookup. For the demo it reads a synthetic
directory (data/directory.py). Either way the number goes in, the account comes
out, and the number is never stored: the book keeps only the account.
"""

from __future__ import annotations

import re

from data.directory import ACCOUNTS, Account

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
    """The account behind a mobile number or UPI ID, or None."""
    q = query.strip().lower()
    if "@" in q:
        return next((a for a in ACCOUNTS if a.upi == q), None)
    number = mobile(q)
    return next((a for a in ACCOUNTS if a.phone == number), None) if number else None
