"""Words, in either script, reduced to something two spellings can agree on.

A transcript can come back in Devanagari ("शर्मा को दो सौ"), in roman Hinglish
("sharma ko do sau"), or mixed, with digits anywhere. The book has names in roman.
Three small tools let the parser and the name matcher work across all of that:

- `tokens` splits a transcript into words and digit groups. Python's `\\w` breaks
  Devanagari at every vowel sign, so the script ranges are spelled out.
- `to_roman` reads a Devanagari word out in roman, dropping the silent "a" the way
  Hindi speakers do (कमला is "kamla", not "kamala").
- `fold` removes the spelling choices romanised Hindi leaves open (aa or a, ee or
  i, w or v, sh or s, a doubled letter), so "Shaikh", "shekh" and शेख meet.

`fold` keeps aspiration: "sath" (60) and "saat" (7) must never meet.
"""

from __future__ import annotations

import re
import unicodedata

# A Devanagari run (letters, vowel signs, digits; not the danda), a roman word
# (with an apostrophe for D'Souza), or a digit group with Indian commas.
_TOKEN = re.compile(
    r"[\u0900-\u0963\u0966-\u097f]+|[a-z][a-z']*|\d+(?:,\d+)*(?:\.\d+)?", re.I
)

_DEVANAGARI_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")


def tokens(text: str) -> list[str]:
    """Words and numbers, in order, as written. Punctuation and ₹ are dropped."""
    text = unicodedata.normalize("NFC", text).translate(_DEVANAGARI_DIGITS)
    return _TOKEN.findall(text)


def is_devanagari(word: str) -> bool:
    return any("\u0900" <= ch <= "\u097f" for ch in word)


# ── Devanagari to roman ──────────────────────────────────────────────────────

_CONSONANTS = {
    "क": "k", "ख": "kh", "ग": "g", "घ": "gh", "ङ": "n",
    "च": "ch", "छ": "chh", "ज": "j", "झ": "jh", "ञ": "n",
    "ट": "t", "ठ": "th", "ड": "d", "ढ": "dh", "ण": "n",
    "त": "t", "थ": "th", "द": "d", "ध": "dh", "न": "n",
    "प": "p", "फ": "ph", "ब": "b", "भ": "bh", "म": "m",
    "य": "y", "र": "r", "ल": "l", "ळ": "l", "व": "v",
    "श": "sh", "ष": "sh", "स": "s", "ह": "h",
}  # fmt: skip
# With a nukta (NFC keeps it as a separate mark): क़ q, ज़ z, फ़ f, ड़ r ...
_NUKTA_FORMS = {"क": "q", "ख": "kh", "ग": "g", "ज": "z", "ड": "r", "ढ": "rh", "फ": "f"}
_VOWELS = {
    "अ": "a", "आ": "aa", "इ": "i", "ई": "ee", "उ": "u", "ऊ": "oo", "ऋ": "ri",
    "ए": "e", "ऐ": "ai", "ओ": "o", "औ": "au", "ऑ": "o", "ऍ": "e",
}  # fmt: skip
_SIGNS = {
    "ा": "aa", "ि": "i", "ी": "ee", "ु": "u", "ू": "oo", "ृ": "ri",
    "े": "e", "ै": "ai", "ो": "o", "ौ": "au", "ॉ": "o", "ॅ": "e",
}  # fmt: skip
_VIRAMA, _NUKTA, _ANUSVARA, _CANDRABINDU, _VISARGA = "्", "़", "ं", "ँ", "ः"
_INHERENT = "a"


class _Unit:
    """One consonant (or none) with its vowel: inherent "a", a sign, or none."""

    __slots__ = ("cons", "vowel", "nasal", "visarga")

    def __init__(self, cons: str, vowel: str | None) -> None:
        self.cons = cons
        self.vowel = vowel  # None after a virama
        self.nasal = False
        self.visarga = False


def to_roman(word: str) -> str:
    """शर्मा -> sharmaa, कमला -> kamlaa, इक़बाल -> iqbaal. Other text passes through."""
    units: list[_Unit] = []
    for ch in unicodedata.normalize("NFC", word):
        last = units[-1] if units else None
        if ch in _CONSONANTS:
            units.append(_Unit(_CONSONANTS[ch], _INHERENT))
        elif ch in _VOWELS:
            units.append(_Unit("", _VOWELS[ch]))
        elif last is None:
            continue
        elif ch in _SIGNS and last.cons:
            last.vowel = _SIGNS[ch]
        elif ch == _VIRAMA:
            last.vowel = None
        elif ch == _NUKTA:
            base = next((k for k, v in _CONSONANTS.items() if v == last.cons), "")
            last.cons = _NUKTA_FORMS.get(base, last.cons)
        elif ch in (_ANUSVARA, _CANDRABINDU):
            last.nasal = True
        elif ch == _VISARGA:
            last.visarga = True

    # The silent "a", right to left: dropped at the end of the word, and between
    # a vowel and a consonant that carries its own vowel (VC_CV -> VCCV).
    silent = [False] * len(units)
    for i in range(len(units) - 1, 0, -1):
        u = units[i]
        if u.vowel != _INHERENT or not u.cons or u.nasal:
            continue
        if i == len(units) - 1:
            silent[i] = True
            continue
        before, after = units[i - 1], units[i + 1]
        if before.vowel is not None and after.cons and after.vowel and not silent[i + 1]:
            silent[i] = True

    out = []
    for u, drop in zip(units, silent, strict=True):
        out.append(u.cons)
        if u.vowel and not drop:
            out.append(u.vowel)
        if u.nasal:
            out.append("n")
        if u.visarga:
            out.append("h")
    return "".join(out)


# ── Folding roman spellings together ─────────────────────────────────────────

_FOLDS = (
    ("chch", "ch"),
    ("ph", "f"),
    ("sh", "s"),
    ("w", "v"),
    ("z", "j"),
    ("q", "k"),
    ("ck", "k"),
    ("ee", "i"),
    ("ii", "i"),
    ("oo", "u"),
    ("uu", "u"),
    ("aa", "a"),
    ("ai", "e"),
)
_DOUBLED = re.compile(r"(.)\1+")
_TRAILING_H = re.compile(r"(?<=[aeiou])h$")


def fold(word: str) -> str:
    """One key for the spellings of one sound: Sharma/sharmaa/शर्मा -> "sarma".

    Aspiration survives ("sath" is not "sat"), and so does chh ("chhe" is not
    "chai"): in numbers those are different words. Keys are compared only with
    other keys, never shown.
    """
    w = to_roman(word) if is_devanagari(word) else word.lower()
    w = re.sub(r"[^a-z]", "", w)
    # छ is one sound: kept apart from च, and out of reach of the doubled-letter rule
    # below, which would otherwise read "chh" as "ch" + a doubled "h".
    w = w.replace("chh", "C")
    for a, b in _FOLDS:
        w = w.replace(a, b)
    w = _DOUBLED.sub(r"\1", w)
    return _TRAILING_H.sub("", w)
