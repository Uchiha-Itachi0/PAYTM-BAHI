"""The life of an entry: which moves are allowed from which state.

    recorded ──confirm──▶ confirmed ──settle──▶ settled
        │                                         ▲
        ├──dispute──▶ disputed                    │
        └──────────────settle─────────────────────┘

    recorded, confirmed or disputed ──correct──▶ corrected

A correction is the shopkeeper's: he finds the amount was wrong, whether the
customer said so (disputed), hasn't answered yet (recorded), or already said yes
(confirmed). The entry is kept, marked corrected, and a new entry with the right
amount takes its place, needing the customer's own yes. Nothing that has been
paid against is corrected: the payment names that entry.

A table, not a web of if-statements, so the whole rule fits on one screen and a
test can walk every pair. Anything not in the table raises, and the API turns
that into 409 Conflict: an illegal move is refused, never quietly ignored.

"Expired" is not here on purpose. Nobody moves an entry into it; time does, and
it is computed (see limitation.py).
"""

from __future__ import annotations

from typing import Literal

Status = Literal["recorded", "confirmed", "disputed", "corrected", "settled"]
Action = Literal["confirm", "dispute", "correct", "settle"]

STATUSES: tuple[Status, ...] = (
    "recorded",
    "confirmed",
    "disputed",
    "corrected",
    "settled",
)
ACTIONS: tuple[Action, ...] = ("confirm", "dispute", "correct", "settle")

MOVES: dict[tuple[Status, Action], Status] = {
    ("recorded", "confirm"): "confirmed",
    ("recorded", "dispute"): "disputed",
    ("disputed", "correct"): "corrected",
    # He found the mistake himself, before or after the customer said yes.
    ("recorded", "correct"): "corrected",
    ("confirmed", "correct"): "corrected",
    # Paid before he answered, or kept by name only and paid in cash.
    ("recorded", "settle"): "settled",
    ("confirmed", "settle"): "settled",
}


class IllegalMove(Exception):
    def __init__(self, status: str, action: str) -> None:
        super().__init__(f"an entry that is {status} cannot be asked to {action}")
        self.status = status
        self.action = action


def move(status: str, action: Action) -> Status:
    """The status after `action`, or IllegalMove."""
    for (frm, act), to in MOVES.items():
        if frm == status and act == action:
            return to
    raise IllegalMove(status, action)
