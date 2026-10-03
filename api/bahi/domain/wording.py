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
