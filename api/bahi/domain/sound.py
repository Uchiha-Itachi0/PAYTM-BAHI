"""Names compared by how they sound, the way a shopkeeper hears them.

Speech recognition spells a name however it likes: अनुभव, "Anubhav", "Anubhaw",
"Anubav". `key` reduces each spelling to the sound a listener would hear, and
`ratio` scores how alike two keys are, from 0 to 100.

This is looser than `script.fold` on purpose. `fold` keeps aspiration because the
parser must never read "sath" (60) as "saat" (7); a name is different, and
"Anubhav" said quickly is "Anubav". Keys are compared with other keys only, never
shown.

`ratio` is the Indel similarity, 200 x LCS / (len a + len b): the score
rapidfuzz calls `fuzz.ratio`, which the 1,338-recording test used. It is written
here in plain Python, with the bit-parallel LCS, so that the domain stays free of
libraries and the scores stay the ones we measured.
"""

from __future__ import annotations

import re
from functools import lru_cache

from bahi.domain.script import is_devanagari, to_roman

_SOUNDS = (
    ("chh", "c"),
    ("ch", "c"),
    ("sh", "s"),
    ("ph", "f"),
    ("q", "k"),
    ("z", "j"),
    ("w", "v"),
    ("ee", "i"),
    ("oo", "u"),
    ("aa", "a"),
    ("ai", "e"),
    ("au", "o"),
)
_ASPIRATED = re.compile(r"([bcdgjkpt])h")
_DOUBLED = re.compile(r"(.)\1+")
_NOT_A_LETTER = re.compile(r"[^a-z]")


@lru_cache(maxsize=8192)
def key(text: str) -> str:
    """Anubhav, अनुभव and anubaw -> "anubab"; Gaikwad and गायकवाड़ come close."""
    s = "".join(to_roman(w) if is_devanagari(w) else w.lower() for w in text.split())
    s = _NOT_A_LETTER.sub("", s)
    for a, b in _SOUNDS:
        s = s.replace(a, b)
    s = _ASPIRATED.sub(r"\1", s)
    s = s.replace("v", "b")
    return _DOUBLED.sub(r"\1", s)


def _lcs(a: str, b: str) -> int:
    """Length of the longest common subsequence (Hyyrö's bit-vector method)."""
    if len(a) < len(b):
        a, b = b, a
    if not b:
        return 0
    masks: dict[str, int] = {}
    for i, ch in enumerate(b):
        masks[ch] = masks.get(ch, 0) | (1 << i)
    ones = (1 << len(b)) - 1
    v = ones
    for ch in a:
        u = v & masks.get(ch, 0)
        v = (v + u) | (v - u)
    return len(b) - (v & ones).bit_count()


@lru_cache(maxsize=65536)
def ratio(a: str, b: str) -> float:
    """How alike two keys are, 0 to 100. Two empty keys are the same."""
    if not a and not b:
        return 100.0
    # rapidfuzz's order of operations, so a score of exactly 85 stays exactly 85
    total = len(a) + len(b)
    return 100 * (1.0 - (total - 2 * _lcs(a, b)) / total)
