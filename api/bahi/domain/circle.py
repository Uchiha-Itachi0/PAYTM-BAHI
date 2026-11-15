"""The family circle's rules, as plain functions.

A circle is people who can pay each other's udhaar. Three rules decide the rest:

1. The person who said "Yes, I owe" stays the debtor. A member can pay an entry
   on the circle's list; nobody in the circle ever owes it.
2. Where a new udhaar goes is the debtor's own setting. Until they choose, the
   default below decides.
3. A member who leaves takes their entries off the list. From then on the debt is
   theirs to pay, and nobody else can.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

OnUdhaar = Literal["circle", "self"]

#: What happens to a new udhaar for someone who has not chosen: it goes to their
#: circle. The captain's choice for the first version; the research behind the
#: feature argues for "self" (docs/family-circle.md). One line to flip.
DEFAULT_ON_UDHAAR: OnUdhaar = "circle"

#: The most people one circle can hold. Not a product limit (limits are left for
#: later), just a bound on what one request can add.
MOST_MEMBERS = 12


def setting(chosen: str | None) -> OnUdhaar:
    """The person's setting: what they chose, or the default."""
    if chosen == "circle":
        return "circle"
    if chosen == "self":
        return "self"
    return DEFAULT_ON_UDHAAR


@dataclass(frozen=True, slots=True)
class Route:
    """Where a newly agreed udhaar goes.

    share   straight onto this circle's list (they are in exactly one)
    choose  they pick one of their circles ("Add to circle" opens a picker)
    keep    it stays with them (their setting); they can still add it
    none    they are in no circle
    """

    kind: Literal["share", "choose", "keep", "none"]
    circle_id: str | None = None


def route(chosen: str | None, circle_ids: Sequence[str]) -> Route:
    """Where a new udhaar goes, from the debtor's setting and their circles."""
    if not circle_ids:
        return Route("none")
    if setting(chosen) == "self":
        return Route("keep")
    if len(circle_ids) == 1:
        return Route("share", circle_ids[0])
    return Route("choose")


#: Notes that ask for something to be done about an open udhaar. They hold only
#: while it is open; the others ("added", "paid") record what happened.
ABOUT_AN_OPEN_ENTRY = frozenset({"shared", "choose", "kept", "help"})


def notice_stands(
    kind: str, *, entry_open: bool, listed_in: str | None, circle_id: str | None
) -> bool:
    """Whether a waiting note still means anything, from the entry as it is now.

    A note asking to pay, place, or take back an udhaar is over once that udhaar
    is paid, closed, or no longer where the note says: whoever paid it, and by
    whatever route (a member, the debtor at the shop, cash in the book).
    """
    if kind not in ABOUT_AN_OPEN_ENTRY:
        return True
    if not entry_open:
        return False
    if kind in ("shared", "help"):
        return listed_in is not None and listed_in == circle_id
    return listed_in is None


def why_not_pay(
    *,
    payer_is_member: bool,
    on_the_list: bool,
    agreed: bool,
    left_paise: int,
    amount_paise: int,
) -> str | None:
    """Why this payment from a member cannot go through, or None if it can.

    `on_the_list` is the entry's share in this circle, still standing: an entry
    whose debtor left the circle is off the list, so only the debtor can pay it.
    """
    if not payer_is_member:
        return "you are not in this circle"
    if not on_the_list:
        return "this udhaar is not on the circle's list any more"
    if not agreed or left_paise <= 0:
        return "there is nothing left to pay on this udhaar"
    if amount_paise <= 0:
        return "pay at least something"
    if amount_paise > left_paise:
        return "that is more than is left on this udhaar"
    return None


def paid_by(payer: str, debtor: str) -> str | None:
    """Who the payment records as the payer: nobody extra when the debtor pays
    their own entry, the member otherwise. Never a debt between the two."""
    return None if payer == debtor else payer
