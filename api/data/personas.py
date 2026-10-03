"""The people the demo is about, written by hand.

Each one exists to make a single point on stage. Their payment gaps are listed
explicitly, oldest first, so the figures the screens show can be checked by hand
against this file: Sharma's usual gap is the median of his list, and so on.

The other customers in the shop are generated around them (see generate.py), so
the book does not look staged.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Literal

Joined = Literal["linked", "invited", "name_only"]


@dataclass(frozen=True, slots=True)
class Open:
    """An entry he still owes today."""

    on: date
    paise: int
    confirmed: bool = True
    spoken: str | None = None


@dataclass(frozen=True, slots=True)
class Persona:
    key: str
    name: str
    tag: str | None
    joined: Joined
    #: Days between his payment days, oldest first.
    gaps: tuple[int, ...]
    #: Days since he last paid, as of TODAY.
    day: int
    opens: tuple[Open, ...]
    #: His usual purchase, in rupees. History amounts are drawn around it.
    ticket: int
    #: Share of his payments made by UPI rather than cash.
    upi: float = 0.8
    #: When his history begins, if later than the six-month window.
    since: date | None = None
    #: Carries the dispute story: one August entry was wrong and was corrected.
    dispute: bool = False
    #: The hour he usually pays, in Kurla. Tonight sends a reminder at that hour.
    pays_at: int = 20
    why: str = field(default="", compare=False)


D = date

CAST: tuple[Persona, ...] = (
    Persona(
        key="sharma",
        name="Sharma",
        tag="Room 19, B wing",
        joined="linked",
        gaps=(9, 8, 10, 9, 11, 9, 7, 9, 10, 8, 9, 9, 12, 9, 8, 10, 9, 9, 8),
        day=4,
        opens=(Open(D(2026, 10, 1), 20000, spoken="do sau"),),
        ticket=160,
        why="Pays every 9 days. Today is day 4, so nothing goes to him.",
    ),
    Persona(
        key="patil",
        name="Patil",
        tag="Auto stand",
        joined="linked",
        gaps=(21, 18, 25, 30, 22, 19),
        day=40,
        opens=(
            Open(D(2026, 8, 27), 40000),
            Open(D(2026, 9, 3), 32000),
            Open(D(2026, 9, 10), 24000),
        ),
        ticket=260,
        upi=0.5,
        pays_at=10,
        why="Never went past 30 days. Today is day 40: something changed. Pays in "
        "the morning, before his first ride.",
    ),
    Persona(
        key="meena",
        name="Meena Tai",
        tag="Opposite lane",
        joined="linked",
        gaps=(18, 17, 19, 18, 20, 16, 18, 19),
        day=11,
        opens=(Open(D(2026, 9, 28), 34000),),
        ticket=220,
        why="Her gap is 18 days, not 7. Day 11 is normal for her.",
    ),
    Persona(
        key="iqbal",
        name="Iqbal bhai",
        tag="Garage, lane 2",
        joined="linked",
        gaps=(6, 5, 7, 6, 6, 8, 5, 6, 7, 6, 6, 5, 7, 6, 6, 8, 6, 7, 5, 6, 6, 7, 6),
        day=12,
        opens=(
            Open(D(2026, 9, 24), 12000),
            Open(D(2026, 9, 27), 9000),
            Open(D(2026, 9, 30), 11000),
        ),
        ticket=90,
        upi=0.6,
        pays_at=18,
        why="Usually 6 days, never more than 8. Day 12. Pays when the garage shuts.",
    ),
    Persona(
        key="anil",
        name="Anil",
        tag="Tailor shop",
        joined="linked",
        gaps=(8, 7, 9, 8, 10, 8, 7, 9, 8, 8, 9, 7, 8, 10, 8, 9, 8, 7, 9, 8),
        day=2,
        opens=(Open(D(2026, 10, 2), 15000, confirmed=False),),
        ticket=120,
        why="Has an entry he has not said yes to. It still counts in the book.",
    ),
    Persona(
        key="raju",
        name="Raju",
        tag="Dhobi ghat",
        joined="linked",
        gaps=(10, 12, 9, 11, 13, 10, 9, 11, 10, 12, 8, 10),
        day=26,
        opens=(Open(D(2026, 9, 12), 22000), Open(D(2026, 9, 20), 18000)),
        ticket=180,
        why="Usually 10 days. Day 26.",
    ),
    Persona(
        key="salma",
        name="Salma",
        tag="Building 7",
        joined="linked",
        gaps=(7, 6, 8, 7, 9, 7, 6, 7, 8, 7, 5, 7, 8, 7, 6, 7, 8, 9),
        day=19,
        opens=(Open(D(2026, 9, 18), 26000), Open(D(2026, 9, 25), 14000)),
        ticket=200,
        why="Usually a week. Day 19.",
    ),
    Persona(
        key="nikhil",
        name="Nikhil",
        tag="PG, 3rd floor",
        joined="linked",
        gaps=(),
        day=13,
        opens=(Open(D(2026, 9, 25), 30000),),
        ticket=250,
        since=D(2026, 9, 12),
        why="Joined in September. One payment is not a rhythm.",
    ),
    Persona(
        key="farah",
        name="Farah",
        tag="Room 8, A wing",
        joined="linked",
        gaps=(13,),
        day=14,
        opens=(Open(D(2026, 9, 24), 21000), Open(D(2026, 10, 1), 16000)),
        ticket=190,
        since=D(2026, 8, 28),
        why="Two payments. Still not enough to read.",
    ),
    Persona(
        key="bablu",
        name="Bablu",
        tag="Chai tapri",
        joined="name_only",
        gaps=(5, 4, 6, 5, 5, 6, 4, 5, 5, 6, 5, 4, 6, 5, 5, 6, 5, 4, 5, 6, 5, 5, 6, 5, 4),
        day=3,
        opens=(Open(D(2026, 10, 1), 6000),),
        ticket=50,
        upi=0.0,
        why="No phone. Kept by name, like the notebook. Pays cash.",
    ),
    Persona(
        key="mausi",
        name="Mausi",
        tag="Building 4",
        joined="name_only",
        gaps=(15, 14, 16, 15, 17, 13, 15, 16, 14, 15),
        day=8,
        opens=(Open(D(2026, 9, 29), 45000),),
        ticket=300,
        upi=0.0,
        why="No phone either. Her book works; nobody can remind her.",
    ),
    Persona(
        key="chhotu",
        name="Chhotu",
        tag="Delivery boy",
        joined="name_only",
        gaps=(7, 6, 8, 7, 7, 6, 8, 7, 7, 6, 7, 8, 7, 6, 7, 7, 8, 6, 7, 7, 6, 8, 7),
        day=2,
        opens=(),
        ticket=70,
        upi=0.0,
        why="Name only, and square with the shop today.",
    ),
    Persona(
        key="kamla",
        name="Kamla behen",
        tag="Room 3, C wing",
        joined="linked",
        gaps=(6, 7, 6, 5, 6, 7, 6, 6, 5, 7, 6, 6, 7) * 2,
        day=1,
        opens=(),
        ticket=140,
        dispute=True,
        why="Disputed ₹200 in August; it was corrected to ₹150 and paid.",
    ),
    Persona(
        key="rukhsana",
        name="Rukhsana Shaikh",
        tag=None,
        joined="invited",
        gaps=(),
        day=0,
        opens=(),
        ticket=0,
        why="Invited by number yesterday. Nothing can be recorded until she accepts.",
    ),
)

#: Background customers: (name, tag). Generated around the cast. Four are named
#: Anubhav, as a real book has namesakes: "Anubhav ko do sau" must ask which one.
CROWD: tuple[tuple[str, str], ...] = (
    ("Deshmukh", "Building 2"),
    ("Farida", "Room 14, A wing"),
    ("Pinto aunty", "Chapel lane"),
    ("Rahul", "Room 6, B wing"),
    ("Salunkhe", "Chawl 3"),
    ("Joshi kaka", "Near temple"),
    ("Nazia", "Building 5"),
    ("Kadam", "Room 21, C wing"),
    ("Babu", "Pan stall"),
    ("Shinde", "Chawl 1"),
    ("Lobo", "Chapel lane"),
    ("Rane", "Building 9"),
    ("Ansari", "Room 2, A wing"),
    ("Gaikwad", "Chawl 5"),
    ("Pooja", "Room 11, B wing"),
    ("Shaikh bhai", "Scrap shop"),
    ("Mhatre", "Building 1"),
    ("Suresh", "Watchman, bldg 6"),
    ("Yadav", "Milk van"),
    ("Pawar", "Room 17, C wing"),
    ("Fernandes", "Building 8"),
    ("Qureshi", "Butcher lane"),
    ("Sawant", "Chawl 2"),
    ("Rekha", "Room 4, A wing"),
    ("Anubhav", "Room 311, B wing"),
    ("Mishra ji", "Room 9, B wing"),
    ("Jadhav", "Chawl 4"),
    ("Sunita", "Room 15, C wing"),
    ("D'Souza", "Chapel lane"),
    ("Khan", "Room 20, A wing"),
    ("More", "Building 10"),
    ("Ganesh", "Vegetable cart"),
    ("Bhosale", "Chawl 6"),
    ("Asha", "Room 7, B wing"),
    ("Chavan", "Building 11"),
    ("Imran", "Mobile repair"),
    ("Kulkarni", "Room 12, C wing"),
    ("Lata", "Building 2"),
    ("Naik", "Chawl 3"),
    ("Pandey", "Room 5, A wing"),
    ("Rizwan", "Room 18, B wing"),
    ("Shetty", "Hotel, corner"),
    ("Anubhav Shukla", "Room 1006, B wing"),
    ("Usha", "Room 10, C wing"),
    ("Vora", "Building 6"),
    ("Wagh", "Chawl 1"),
    ("Zainab", "Room 16, A wing"),
    ("Anubhav", "Room 204, A wing"),
    ("Kamat", "Room 13, B wing"),
    ("Anubhav Jain", "Medical shop"),
)
