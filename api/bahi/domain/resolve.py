"""Who the entry is for: someone picked for a stated reason, or a question.

The system never decides the person. It may only:

- take the one person at the counter, when exactly one is waiting and no name was
  said;
- take the one person whose name was said, looking first at the people waiting
  and only then at the book.

Everything else is a question for the shopkeeper, never a pick by queue order:
several people waiting and no name ("Kiske liye?"), a name that fits two people,
a name that fits nobody.

Names are compared by key (`script.fold`), with the words that are respect rather
than name ("bhai", "ji", "Tai") set aside, so "Iqbal bhai", "iqbal" and इक़बाल meet.
A near miss (one letter off, "Sharmaa" for "Sharma") counts only among the few
people at the counter, never across the whole book.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Literal

from bahi.domain.script import fold, tokens

How = Literal["only_one", "at_counter", "in_book"]
Why = Literal["who", "nobody", "not_found", "several"]

#: The most people waiting for which a near miss still counts.
NEAR_MISS_LIMIT = 5

# Words of respect, not of name: "Iqbal bhai" is Iqbal.
_RESPECT_WORDS = """
ji jee bhai bhaiya bhaiyya bhau saab sahab saheb sahib didi tai mausi masi aunty
uncle chacha kaka kaku bhabhi behen behan bahen bahan madam mr mrs miss seth
"""
_RESPECT = frozenset(fold(w) for w in _RESPECT_WORDS.split())


@dataclass(frozen=True, slots=True)
class Person:
    #: The scan id for someone at the counter, the customer id for the book.
    ref: str
    name: str


@dataclass(frozen=True, slots=True)
class Picked:
    person: Person
    how: How


@dataclass(frozen=True, slots=True)
class Ask:
    why: Why
    #: Who the question is about: everyone waiting, or everyone the name fits.
    among: tuple[Person, ...]


def name_keys(name: str) -> frozenset[str]:
    """{"ikbal"} for "Iqbal bhai". A name that is only a word of respect keeps it."""
    keys = [fold(w) for w in tokens(name)]
    keys = [k for k in keys if k]
    named = [k for k in keys if k not in _RESPECT]
    return frozenset(named or keys)


def _distance_at_most_one(a: str, b: str) -> bool:
    if a == b:
        return True
    if abs(len(a) - len(b)) > 1:
        return False
    if len(a) > len(b):
        a, b = b, a
    i = 0
    while i < len(a) and a[i] == b[i]:
        i += 1
    # Substitution skips one letter of each; insertion skips one of the longer.
    return a[i + 1 :] == b[i + 1 :] if len(a) == len(b) else a[i:] == b[i + 1 :]


def _near(said: frozenset[str], name: frozenset[str]) -> bool:
    return all(
        any(len(s) >= 4 and _distance_at_most_one(s, n) for n in name) for s in said
    )


Rule = Callable[[frozenset[str], frozenset[str]], bool]


def _same(said: frozenset[str], name: frozenset[str]) -> bool:
    return said == name


def _part(said: frozenset[str], name: frozenset[str]) -> bool:
    """ "Sharma" for "Ashok Sharma"."""
    return said < name


def _more(said: frozenset[str], name: frozenset[str]) -> bool:
    """ "Chhotu chai" for "Chhotu": the name, and a word that wasn't one."""
    return name < said


def _first_fit(
    said: frozenset[str], people: Sequence[Person], rules: Sequence[Rule]
) -> list[Person]:
    """Everyone who fits the strictest rule anyone fits."""
    for rule in rules:
        fits = [p for p in people if rule(said, name_keys(p.name))]
        if fits:
            return fits
    return []


def resolve(
    waiting: Sequence[Person], book: Sequence[Person], said_name: str | None
) -> Picked | Ask:
    if said_name is None or not name_keys(said_name):
        if len(waiting) == 1:
            return Picked(waiting[0], "only_one")
        return Ask("who" if waiting else "nobody", tuple(waiting))

    said = name_keys(said_name)
    exact: list[Rule] = [_same, _part, _more]
    near: list[Rule] = [_near] if len(waiting) <= NEAR_MISS_LIMIT else []
    places: tuple[tuple[Sequence[Person], How, list[Rule]], ...] = (
        (waiting, "at_counter", exact + near),
        (book, "in_book", exact),
    )
    for people, how, rules in places:
        fits = _first_fit(said, people, rules)
        if len(fits) == 1:
            return Picked(fits[0], how)
        if fits:
            return Ask("several", tuple(fits))
    return Ask("not_found", tuple(waiting))
