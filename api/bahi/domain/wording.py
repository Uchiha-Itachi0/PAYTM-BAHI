"""The exact words the customer is shown, generated in one place.

The acknowledgment's wording is stored with it as evidence of what he agreed to,
so the words on the button and the words in the database must be the same string.
The API sends the button text to the screen; the screen never writes its own.

Rule 1: an acknowledgment of a sum, never a promise to pay by a date.
"""

from __future__ import annotations

from bahi.domain.money import rupees


def button(amount_paise: int) -> str:
    """What the confirm button says."""
    return f"Yes, I owe {rupees(amount_paise)}"


def acknowledgment(amount_paise: int, shop_name: str) -> str:
    """What is stored when he taps it."""
    return f"{button(amount_paise)} to {shop_name}"


def asked(amount_paise: int, shop_name: str) -> str:
    """What her ask is stored as, when the shopkeeper writes exactly that: her own
    words of acknowledgment. Never her note: that is what it was for, and a note
    could carry a date ("pay by Friday"), which an acknowledgment must not."""
    return f"I'm taking {rupees(amount_paise)} udhaar from {shop_name}"


# ── what BAHI writes in a thread ─────────────────────────────────────────────
#
# BAHI's own lines: the entry card's caption, and a short line when something
# happens to an entry. Generated here so the seed and the live product say the
# same thing, and so a line never carries a figure the ledger does not hold.


def recorded(shop_name: str, amount_paise: int) -> str:
    return f"{shop_name} recorded {rupees(amount_paise)} udhaar."


def corrected(shop_name: str, amount_paise: int) -> str:
    return f"Corrected by {shop_name} to {rupees(amount_paise)}."


def disputed(customer_name: str, amount_paise: int, disputed_as: str) -> str:
    if disputed_as == "not_mine":
        return f"{customer_name} says {rupees(amount_paise)} is not theirs."
    return f"{customer_name} says {rupees(amount_paise)} is not the right amount."


def removed(shop_name: str, amount_paise: int) -> str:
    return f"{shop_name} took back {rupees(amount_paise)}. Nothing to pay for it."


def paid(amount_paise: int, method: str, left_paise: int | None = None) -> str:
    """ "Paid ₹100 by UPI. ₹100 still open." What is left is at this shop, after it."""
    how = "by UPI" if method == "upi" else "in cash"
    said = f"Paid {rupees(amount_paise)} {how}."
    if left_paise is None:
        return said
    if left_paise == 0:
        return f"{said} Nothing left to pay."
    return f"{said} {rupees(left_paise)} still open."


def reminder(customer_name: str, shop_name: str, balance_paise: int) -> str:
    """The reminder in our own words, when the munshi can't write it: it asks,
    names the sum, and promises nothing and sets no date. Rule 1."""
    return (
        f"{customer_name}, {shop_name} par {rupees(balance_paise)} ka udhaar hai. "
        "Koi dikkat ho to bata dena, jaldi nahi hai."
    )
