"""The munshi's search: who in the book could the shopkeeper mean.

The munshi (the model) turns his words into a search: a name as heard, and a
description in the book's own words ("B wing", "Room 19", "Milk van"). This
finds the customers who fit, in plain code over the real book, and says how
well each one fits. It never picks: the munshi picks, or asks.

- A name is compared by sound (`sound.key`), in roman and in Devanagari, the same
  way `who` does. 85 or more is the same name; 70 to 84 only sounds a little like
  it, and the munshi must say the name back.
- A description is compared word by word with his tag, in both scripts: a word
  fits if it is the same word, or (four letters or more) sounds the same. "B
  wing" fits every B wing customer fully and every A wing one only half, so only
  the B wing ones come back.
- Name and description together: evidence adds up. A full description beats a
  faint name, so "दूध वाले भैया" said as a name with "Milk van" finds Yadav, not
  whoever "भैया" happens to sound like.

Only the best-fitting group comes back, with a note when one half found nobody.
"""

from __future__ import annotations

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


def _fits(description: str, p: Person) -> float:
    said = _words(description)
    if not said:
        return 0.0
    tag = set(_words(p.tag)) | set(_words(p.tag_hi))
    tag_keys = {key(t) for t in tag if len(key(t)) >= SOUNDS_FROM}

    def fits(w: str) -> bool:
        if w in tag:
            return True
        k = key(w)
        return len(k) >= SOUNDS_FROM and any(ratio(k, t) >= STRONG for t in tag_keys)

    return sum(1 for w in said if fits(w)) / len(said)


def _named(name: str, p: Person) -> float:
    spans = _spoken(name) | {key(name)}
    forms = _forms(p.name, p.name_hi)[1] | _forms(p.name, p.name_hi)[0]
    return max((ratio(s, f) for s in spans for f in forms if s and f), default=0.0)


def find(book: Sequence[Person], name: str | None, description: str | None) -> Search:
    name = (name or "").strip() or None
    description = (description or "").strip() or None
    if not name and not description:
        return Search((), "give a name or a description")

    named = {p.ref: s for p in book if name and (s := _named(name, p)) >= FAINT}
    fitting = {
        p.ref: f for p in book if description and (f := _fits(description, p)) >= HALF
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
