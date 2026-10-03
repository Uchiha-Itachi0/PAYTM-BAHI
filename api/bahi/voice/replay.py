"""`make voice-eval`: the voice test behind slide 4, replayed through this code.

On 24 Sep 2026 we spoke 42 shopkeeper lines in 12 voices, quiet, over street noise
and with a second customer talking: 1,338 recordings. Sarvam heard each one
(saaras:v4) and Sarvam-105B read it. What Sarvam returned is kept in
`bahi/audio/test-1338.json.gz`, with a 68-customer test book that has 20
customers named Anubhav.

This replays those transcripts and replies through the checker the app runs
(`domain.check`), with no network calls, and grades every outcome:

    voice       the right person and amount, from the words alone
    one tap     asked "Kaunse …?" with the right person offered
    say again   refused, or asked without the right person offered
    wrong       a wrong person, amount or intent would have gone to a phone

It also runs our parser as the reader (what the app does offline) on the same
transcripts, and shows the grades V2's rules got on the day. If a change to the
checker moves a number on the slide, this is where it shows.
"""

from __future__ import annotations

import gzip
import json
import sys
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from bahi.domain.check import Checked, Draft, check_draft, check_rules
from bahi.domain.who import Person, Picked, shortlist

DATA = Path(__file__).resolve().parent.parent / "audio" / "test-1338.json.gz"

#: How each grade counts on the slide.
BUCKET = {
    "right": "voice",
    "asked, right group": "tap",
    "asked, right one offered": "tap",
    "asked (new)": "tap",
    "refused": "again",
    "missed": "again",
    "asked, wrong group": "again",
    "WRONG person": "wrong",
    "WRONG amount/intent": "wrong",
}
BUCKETS = ("voice", "tap", "again", "wrong")
#: "Anubhav ko 220" should ask among (nearly) all of them.
GROUP_ENOUGH = 15


@dataclass(frozen=True, slots=True)
class Line:
    said: str
    intent: str
    rupees: int
    #: A customer id, "ANU" (ask among the Anubhavs), or None (not in the book).
    who: str | None
    waiting: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Test:
    book: list[Person]
    lines: list[Line]
    recordings: list[dict[str, Any]]

    @property
    def group(self) -> set[str]:
        return {p.ref for p in self.book if p.name.startswith("Anubhav")}

    @property
    def near_group(self) -> set[str]:
        """The group, and Anubha: one letter from Anubhav, fair to offer."""
        return self.group | {p.ref for p in self.book if p.name == "Anubha"}


def load(path: Path = DATA) -> Test:
    with gzip.open(path, "rt", encoding="utf-8") as f:
        raw = json.load(f)
    book = [
        Person(c["id"], c["name"], c["tag"], c["name_hi"], c.get("tag_hi"))
        for c in raw["book"]
    ]
    lines = [
        Line(x["said"], x["intent"], x["rupees"], x["who"], tuple(x["waiting"]))
        for x in raw["lines"]
    ]
    return Test(book, lines, raw["recordings"])


def draft_of(reply: dict[str, Any]) -> Draft:
    return Draft(
        intent=reply["intent"],
        amount_words=reply["amount_words"],
        amount_rupees=reply["amount_rupees"],
        person_words=reply.get("person_words"),
        customer_id=reply["customer_id"],
        candidates=tuple(reply["candidates"]),
        reason=reply["reason"],
    )


def grade(test: Test, line: Line, c: Checked) -> str:
    """The test's grading, rule for rule."""
    if c.problem is not None:
        return "refused"
    amount_ok = c.amount_paise == line.rupees * 100 and c.intent == line.intent
    if not amount_ok:
        return "WRONG amount/intent"
    if isinstance(c.who, Picked):
        right = line.who not in (None, "ANU") and c.who.person.ref == line.who
        return "right" if right else "WRONG person"
    if c.who.why == "not_found":
        return "right" if line.who is None else "missed"
    offered = {p.ref for p in c.who.among}
    if line.who == "ANU":
        whole = offered <= test.near_group and len(offered & test.group) >= GROUP_ENOUGH
        return "asked, right group" if offered and whole else "asked, wrong group"
    if line.who is None:
        return "asked (new)"
    return "asked, right one offered" if line.who in offered else "missed"


Reader = Callable[[Test, dict[str, Any]], str]


def by_sarvam(test: Test, rec: dict[str, Any]) -> str:
    """Sarvam-105B's saved reply, checked by the app's checker."""
    reply = rec["sarvam_105b"]
    if reply is None:  # its reply was not JSON, twice: nothing was sent
        return "refused"
    line = test.lines[rec["line"]]
    by_ref = {p.ref: p for p in test.book}
    waiting = [by_ref[r] for r in line.waiting]
    shown = shortlist(rec["heard"], waiting, test.book)
    return grade(
        test, line, check_draft(rec["heard"], draft_of(reply), shown, waiting, test.book)
    )


def by_rules(test: Test, rec: dict[str, Any]) -> str:
    """Our parser as the reader, as the app runs offline."""
    line = test.lines[rec["line"]]
    by_ref = {p.ref: p for p in test.book}
    waiting = [by_ref[r] for r in line.waiting]
    return grade(test, line, check_rules(rec["heard"], waiting, test.book))


def as_saved(key: str) -> Reader:
    return lambda _test, rec: str(rec[key])


def table(grades: Sequence[str]) -> str:
    c = Counter(BUCKET[g] for g in grades)
    n = len(grades)
    cells = [f"{100 * c[b] / n:5.1f}%" for b in BUCKETS]
    return f"{n:5d}  " + "  ".join(cells) + f"   ({c['wrong']} wrong)"


def run(test: Test) -> dict[str, list[str]]:
    readers: dict[str, Reader] = {
        "sarvam-105b + checks": by_sarvam,
        "our parser + checks (offline)": by_rules,
        "V2 rules, as graded on the day": as_saved("v2_rules"),
    }
    return {
        name: [r(test, rec) for rec in test.recordings] for name, r in readers.items()
    }


def main() -> int:
    test = load()
    graded = run(test)
    head = "recordings   voice  one tap  say again  wrong"
    for noise in ("clean", "street", "babble", None):
        idx = [
            i
            for i, rec in enumerate(test.recordings)
            if noise is None or rec["noise"] == noise
        ]
        print(f"\n{noise or 'all'}".upper())
        print(f"  {'':32} {head}")
        for name, grades in graded.items():
            print(f"  {name:32} {table([grades[i] for i in idx])}")

    ours = graded["sarvam-105b + checks"]
    moved = [i for i, rec in enumerate(test.recordings) if ours[i] != rec["graded"]]
    rank = {b: i for i, b in enumerate(BUCKETS)}
    worse = [
        i
        for i in moved
        if rank[BUCKET[ours[i]]] > rank[BUCKET[test.recordings[i]["graded"]]]
    ]
    print(
        f"\n{len(moved)} of {len(ours)} recordings graded differently from the day, "
        f"{len(worse)} of them worse."
    )
    for i in moved[:10]:
        rec = test.recordings[i]
        where = f"[{rec['line']}] {rec['voice']} {rec['noise']}"
        print(f"  {where}: {rec['graded']} -> {ours[i]}")

    print("\nwrong, with Sarvam-105B:")
    for i, g in enumerate(ours):
        if BUCKET[g] == "wrong":
            rec = test.recordings[i]
            reply = rec["sarvam_105b"]
            print(
                f"  [{rec['line']:2d}] {g:20} heard {rec['heard']!r} -> "
                f"{reply['intent']} ₹{reply['amount_rupees']}"
            )
    return 1 if worse else 0


if __name__ == "__main__":
    sys.exit(main())
