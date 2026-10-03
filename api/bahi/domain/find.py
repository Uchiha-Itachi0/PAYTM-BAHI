"""The munshi's search: who in the book could the shopkeeper mean.

The munshi (the model) turns his words into a search: a name as heard, and a
description in the book's own words ("B wing", "Room 19", "Milk van"). This
finds the customers who fit, in plain code over the real book, and says how
well each one fits. It never picks: the munshi picks, or asks.

- A name is compared by sound (`sound.key`), in roman and in Devanagari, the same
  way `who` does. 85 or more is the same name; 70 to 84 only sounds a little like
  it, and the munshi must say the name back.
- A description is compared word by word with his tag, in both scripts: a word
  fits if it is the same word, or (four letters or more) sounds the same. Each
  word counts for what it tells apart in this book: "wing", on everyone with a
  wing, counts for little; "B" or "19" for a lot. So "B wing" fits the B wing
  customers fully, and "V wing" (a misheard B) fits nobody, not every wing.
- A whole name beats a part of one: "अनुभव शुक्ला" finds Anubhav Shukla, not
  every Anubhav, when the book has someone with that whole name.
- Name and description together: evidence adds up. A full description beats a
  faint name, so "दूध वाले भैया" said as a name with "Milk van" finds Yadav, not
  whoever "भैया" happens to sound like.

Only the best-fitting group comes back, with a note when one half found nobody.
"""

from __future__ import annotations

import math
import re
from collections.abc import Sequence
from dataclasses import dataclass

from bahi.domain.sound import key, ratio
from bahi.domain.who import STRONG, Person, _forms, _spoken

#: Below this a name does not come back at all. "Patar" (80) comes back for
#: Pawar, as a weak match.
FAINT = 70
#: A description word this long, as a key, may match by sound.
SOUNDS_FROM = 4
#: At least half the description has to fit.
HALF = 0.5
#: A strong name counts this much, a weak one this much; a description counts
#: the share of its words that fit.
STRONG_NAME, WEAK_NAME = 1.0, 0.4


@dataclass(frozen=True, slots=True)
class Found:
    person: Person
    #: 0 to 100, or 0 if no name was given or it did not come close.
    name_score: float
    #: Share of the description's words his tag has, 0 to 1.
    fits: float

    @property
    def name_strong(self) -> bool:
        return self.name_score >= STRONG

    @property
    def strong(self) -> bool:
        """Good enough to put on a card without asking who: the name is his, or
        the whole description is his tag."""
        return self.name_strong or self.fits >= 1.0


@dataclass(frozen=True, slots=True)
class Search:
    found: tuple[Found, ...]
    note: str | None


def _words(text: str | None) -> list[str]:
    return [w for w in re.split(r"[\s,.;:()/]+", (text or "").lower()) if w]


def _has(w: str, p: Person) -> bool:
    """His tag has the word: the same word, or one that sounds the same."""
    tag = set(_words(p.tag)) | set(_words(p.tag_hi))
    if w in tag:
        return True
    k = key(w)
    return len(k) >= SOUNDS_FROM and any(
        ratio(k, key(t)) >= STRONG for t in tag if len(key(t)) >= SOUNDS_FROM
    )


def _weights(said: list[str], book: Sequence[Person]) -> dict[str, float]:
    """How much each word tells people apart in this book (inverse document
    frequency): a word on nobody's tag counts most, one on everyone's almost
    nothing."""
    n = len(book)
    return {
        w: math.log((n + 1) / (sum(1 for p in book if _has(w, p)) + 0.5)) for w in said
    }


def _fits(said: list[str], weights: dict[str, float], p: Person) -> float:
    if not said:
        return 0.0
    total = sum(weights[w] for w in said)
    if total <= 0:  # only words everyone has: each counts the same
        return sum(1 for w in said if _has(w, p)) / len(said)
    return sum(weights[w] for w in said if _has(w, p)) / total


def _named(name: str, p: Person) -> float:
    spans = _spoken(name) | {key(name)}
    forms = _forms(p.name, p.name_hi)[1] | _forms(p.name, p.name_hi)[0]
    return max((ratio(s, f) for s in spans for f in forms if s and f), default=0.0)


def _whole(name: str, p: Person) -> float:
    """How like his whole name, said as a whole, this is."""
    said = key(" ".join(w for w in name.split() if not w[0].isdigit()))
    return max((ratio(said, f) for f in _forms(p.name, p.name_hi)[0] if f), default=0.0)


def find(book: Sequence[Person], name: str | None, description: str | None) -> Search:
    name = (name or "").strip() or None
    description = (description or "").strip() or None
    if not name and not description:
        return Search((), "give a name or a description")

    named = {p.ref: s for p in book if name and (s := _named(name, p)) >= FAINT}
    if name and len(name.split()) >= 2:
        # He said a whole name and someone has it: those who share only part of
        # it (the first name) are not who he means.
        whole = {p.ref for p in book if p.ref in named and _whole(name, p) >= STRONG}
        if whole:
            named = {r: s for r, s in named.items() if r in whole}
    words = _words(description)
    weights = _weights(words, book)
    fitting = {
        p.ref: f for p in book if words and (f := _fits(words, weights, p)) >= HALF
    }
    if fitting:
        best = max(fitting.values())
        fitting = {r: f for r, f in fitting.items() if f == best}

    def score(ref: str) -> float:
        s = named.get(ref, 0.0)
        return (STRONG_NAME if s >= STRONG else WEAK_NAME if s else 0.0) + fitting.get(
            ref, 0.0
        )

    refs = set(named) | set(fitting)
    top = max((score(r) for r in refs), default=0.0)
    chosen = [p for p in book if p.ref in refs and score(p.ref) == top]
    chosen.sort(key=lambda p: -named.get(p.ref, 0.0))
    found = tuple(
        Found(p, named.get(p.ref, 0.0), fitting.get(p.ref, 0.0)) for p in chosen
    )

    if not found and name and not description:
        # A place can land in the name ("सी विंग", "Room 4"): speech runs the
        # words together, and a model files them where it likes. Read as where
        # they live, the same words may fit.
        as_place = find(book, None, name)
        if as_place.found:
            return as_place

    said = " ".join(x for x in (name, description) if x)
    if not found:
        note = f"nobody in the book fits '{said}'. Say so and ask who he means."
    elif name and description and not any(f.name_score for f in found):
        note = f"nobody is named like '{name}'; these fit '{description}'"
    elif name and description and not any(f.fits for f in found):
        note = f"nobody fits '{description}'; these fit the name '{name}' only"
    else:
        note = None
    return Search(found, note)
