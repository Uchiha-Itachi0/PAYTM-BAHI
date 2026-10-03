"""Who the entry is for: someone picked for a stated reason, or a question.

The reader (Sarvam-105B, or our parser when offline) quotes the words that name
the person: "अनुभव शुक्ला", "204 वाले अनुभव", "Iqbal bhai". It never picks him.
This module decides whether those words fit exactly one customer, and asks when
they do not. Every rule below was measured on the 1,338-recording test:

- Names are compared by sound (`sound.key`), in the roman the book was written in
  and in Devanagari (Sarvam's transliteration), because a transcript can come back
  in either.
- The longest stretch of the words that names someone wins: "अनुभव शुक्ला" is
  Anubhav Shukla, not all the Anubhavs.
- A strong match scores 85 or more. Everyone within 10 points of the best is the
  same name to a shopkeeper's ear, so two of them is a question.
- A number said with the name (room 1006, "204 wale") narrows it to the customers
  whose tag has that number. A run of number words is a number, never part of a
  name: "दस सौ छह" is 1006, not Anubhav Das.
- Someone at the counter beats someone in the book with the same name.
- A weak match (65 to 84) is never picked, only offered.

With no words naming anyone, the one person waiting is the one; several waiting is
"Kiske liye?", never the first in line.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from functools import lru_cache
from typing import Literal

from bahi.domain.numerals import numeral
from bahi.domain.parse import heard
from bahi.domain.script import tokens
from bahi.domain.sound import key, ratio

How = Literal["only_one", "at_counter", "in_book"]
#: who: several waiting, no name. nobody: nobody waiting, no name.
#: several: the name fits more than one. maybe: only a weak match, offered.
#: not_found: the name fits nobody. not_said: the quoted words were not said.
Why = Literal["who", "nobody", "several", "maybe", "not_found", "not_said"]
Strength = Literal["strong", "weak", "none"]

#: A pick needs this much. "Patar" is 80 from Pawar, and is not Pawar.
STRONG = 85
#: Below this a name is not offered at all.
WEAK = 65
#: Names this close to the best are the same name to the ear.
TIE = 10
#: A shortlist match, for what the reader is shown.
SHORTLIST = 80
SHORTLIST_MAX = 30
WEAK_OFFERED = 3


@dataclass(frozen=True, slots=True)
class Person:
    #: The customer id.
    ref: str
    name: str
    #: Room, wing, or work: "Room 1006, B wing". How a shopkeeper tells two apart.
    tag: str | None = None
    #: The name in Devanagari, from Sarvam's transliteration. None if we lack it.
    name_hi: str | None = None


@dataclass(frozen=True, slots=True)
class Picked:
    person: Person
    how: How


@dataclass(frozen=True, slots=True)
class Ask:
    why: Why
    #: Who the question is about: everyone waiting, or everyone the words fit.
    among: tuple[Person, ...]


# ── names by sound ───────────────────────────────────────────────────────────


@lru_cache(maxsize=4096)
def _forms(name: str, name_hi: str | None) -> tuple[frozenset[str], frozenset[str]]:
    """(whole names, names and their parts), as keys, in both scripts."""
    written = [name.replace("'", "")]
    if name_hi:
        written.append(name_hi.replace("'", ""))
    whole = frozenset(key(w) for w in written)
    parts = frozenset(
        k for w in written for p in (w, *w.split()) if len(k := key(p)) >= 3
    )
    return whole, parts


def _spans(words: Sequence[str], sizes: Iterable[int]) -> list[str]:
    out = [
        key(" ".join(words[i : i + n])) for n in sizes for i in range(len(words) - n + 1)
    ]
    return [s for s in out if len(s) >= 3]


def _spoken(text: str) -> set[str]:
    """Every 1-3 word stretch of the text, by sound. Digits are not names."""
    return set(_spans([w for w in tokens(text) if not w[0].isdigit()], (1, 2, 3)))


def _best(spans: Iterable[str], forms: Iterable[str]) -> float:
    return max((ratio(s, f) for s in spans for f in forms), default=0)


def _scores(text: str, people: Sequence[Person]) -> dict[str, float]:
    spans = _spoken(text)
    return {p.ref: _best(spans, _forms(p.name, p.name_hi)[1]) for p in people}


def _with_number(numbers: Sequence[str], people: Sequence[Person]) -> list[str]:
    """Everyone whose tag has one of these numbers as a whole: 204 is not 1204."""
    if not numbers:
        return []
    return [
        p.ref for p in people if any(re.search(rf"\b{n}\b", p.tag or "") for n in numbers)
    ]


def _people(waiting: Sequence[Person], book: Sequence[Person]) -> list[Person]:
    """The book, with anyone waiting who is not in it yet, each once."""
    return list({p.ref: p for p in (*book, *waiting)}.values())


# ── what the reader is shown ─────────────────────────────────────────────────


def shortlist(
    transcript: str, waiting: Sequence[Person], book: Sequence[Person]
) -> list[Person]:
    """Customers whose names sound like words said, or whose tag has a number said,
    then everyone waiting. The reader sees these; it may name no one else."""
    people = _people(waiting, book)
    by_ref = {p.ref: p for p in people}
    sc = _scores(transcript, people)
    keep = sorted((r for r, s in sc.items() if s >= SHORTLIST), key=lambda r: -sc[r])
    keep += _with_number(re.findall(r"\d+", transcript), people)
    keep += [p.ref for p in waiting]
    return [by_ref[r] for r in dict.fromkeys(keep)][:SHORTLIST_MAX]


def said_like(words: str, transcript: str) -> bool:
    """The quoted words are in the transcript, or sound like words in it (the
    reader sometimes writes वैभव back as "Vaibhav")."""
    if words in transcript:
        return True
    heard_spans = _spoken(transcript)
    return any(ratio(a, b) >= STRONG for a in _spoken(words) for b in heard_spans)


# ── who the words fit ────────────────────────────────────────────────────────


def fits(
    words: str, waiting: Sequence[Person], book: Sequence[Person]
) -> tuple[Strength, list[Person]]:
    """Everyone the words could mean, and how strongly."""
    people = _people(waiting, book)
    by_ref = {p.ref: p for p in people}
    at_counter = {p.ref for p in waiting}

    toks = tokens(words)
    is_num = [numeral(w) is not None or w[0].isdigit() for w in toks]
    in_number = [
        is_num[i]
        and (
            (i > 0 and is_num[i - 1])
            or (i + 1 < len(toks) and is_num[i + 1])
            or toks[i][0].isdigit()
        )
        for i in range(len(toks))
    ]
    name_words = [w for w, num in zip(toks, in_number, strict=True) if not num]

    numbers = re.findall(r"\d+", words)
    said = heard(words).amount_paise  # number words read by our parser: दस सौ छह
    if said:
        numbers.append(str(said // 100))
    detail = _with_number(numbers, people)

    for n in (4, 3, 2, 1):  # the longest stretch that names someone wins
        spans = _spans(name_words, (n,))
        if not spans:
            continue
        sc: dict[str, float] = {}
        for p in people:
            whole, parts = _forms(p.name, p.name_hi)
            sc[p.ref] = max(_best(spans, whole), _best(spans, parts))
        strong = [r for r, v in sc.items() if v >= STRONG]
        if strong:
            top = max(sc[r] for r in strong)
            fit = [r for r in strong if sc[r] >= top - TIE]
            fit = [r for r in fit if r in detail] or fit
            fit = [r for r in fit if r in at_counter] or fit
            return "strong", [by_ref[r] for r in fit]
    if detail:
        return "strong", [by_ref[r] for r in detail]

    sc = _scores(" ".join(name_words), people)
    weak = sorted((r for r, v in sc.items() if v >= WEAK), key=lambda r: -sc[r])
    if weak:
        return "weak", [by_ref[r] for r in weak[:WEAK_OFFERED]]
    return "none", []


def who(
    words: str | None,
    waiting: Sequence[Person],
    book: Sequence[Person],
    *,
    transcript: str | None = None,
) -> Picked | Ask:
    """The person the words name, or a question.

    `transcript`, when given, is what the words must have been said in: a
    reader's quote that nobody said is not a name.
    """
    if not words or not words.strip():
        if len(waiting) == 1:
            return Picked(waiting[0], "only_one")
        return Ask("who" if waiting else "nobody", tuple(waiting))
    if transcript is not None and not said_like(words, transcript):
        return Ask("not_said", ())
    strength, fit = fits(words, waiting, book)
    if strength == "strong" and len(fit) == 1:
        p = fit[0]
        return Picked(p, "at_counter" if p.ref in {w.ref for w in waiting} else "in_book")
    if strength == "none":
        return Ask("not_found", ())
    return Ask("several" if strength == "strong" else "maybe", tuple(fit))
