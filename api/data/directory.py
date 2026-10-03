"""Paytm's accounts, as far as the demo needs them. Synthetic.

BAHI never holds a phone number: the shopkeeper types one, Paytm finds the
account, and the number is thrown away. We don't have Paytm's user system, so
this file stands in for its lookup. Every number and UPI ID here is made up.

Rukhsana is the seed's invitation (data/personas.py): she was invited by number
yesterday and hasn't said yes. Kavita and Tushar are on Paytm and in nobody's
book yet, so an invite can be tried live. Sharma is already in the book.
"""

from __future__ import annotations

from dataclasses import dataclass

from data.world import uid


@dataclass(frozen=True, slots=True)
class Account:
    person_id: str
    name: str
    phone: str
    upi: str


ACCOUNTS: tuple[Account, ...] = (
    Account(
        str(uid("person", "rukhsana")), "Rukhsana Shaikh", "9876543210", "rukhsana@ptys"
    ),
    Account(
        str(uid("person", "kavita")), "Kavita Rao", "9820011223", "kavita.rao@ptaxis"
    ),
    Account(str(uid("person", "tushar")), "Tushar Pawar", "9867044556", "tushar@pthdfc"),
    Account(str(uid("person", "sharma")), "Sharma", "9819019019", "sharma19@ptsbi"),
)
