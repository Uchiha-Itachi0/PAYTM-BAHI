"""Hindi, Hinglish and English number words: a table, not a model.

Hindi has a separate word for every number from 1 to 99 (pachchees is 25, not
"twenty-five"), so each one is listed, in roman and in Devanagari, with the
spellings a transcript is likely to use. The first spelling of each is the one
`speak` says back.

Every spelling is reduced to a key (`script.fold` for roman, `_deva_key` for
Devanagari) and the table refuses to build if two numbers would share a key. A test
also checks that everyday words ("chai", "no", "hai") are not numbers.

Known collisions with ordinary words, left in on purpose: "saath" is both 60 and
"with", "tera" both 13 and "your", "das" both 10 and a surname. The parser treats a
sentence with two amounts in it as unclear rather than picking one, so these
produce a question, never a wrong number.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from fractions import Fraction
from functools import lru_cache
from typing import Literal

from bahi.domain.script import fold, is_devanagari

# fmt: off
ROMAN: dict[int, tuple[str, ...]] = {
    1: ("ek",), 2: ("do",), 3: ("teen", "tin"), 4: ("chaar", "char"),
    5: ("paanch", "panch"), 6: ("chhah", "chhe", "chha", "chah"), 7: ("saat",),
    8: ("aath", "ath"), 9: ("nau",), 10: ("das", "dus"),
    11: ("gyaarah", "gyarah", "gyara", "giyarah"), 12: ("baarah", "barah", "bara"),
    13: ("terah", "tera"), 14: ("chaudah", "chauda", "chaudha", "chodah", "choda"),
    15: ("pandrah", "pandra", "pandhra", "pandarah"), 16: ("solah", "sola"),
    17: ("satrah", "satra", "satarah"), 18: ("athaarah", "atharah", "athara"),
    19: ("unnees", "unnis", "unees", "unis"), 20: ("bees", "bis"),
    21: ("ikkees", "ikkis", "ekkis", "ikees"), 22: ("baaees", "bais", "baais", "baayees"),
    23: ("teyees", "teis", "teees"), 24: ("chaubees", "chaubis", "chobis", "chobees"),
    25: ("pachchees", "pachees", "pachis", "pachchis"),
    26: ("chhabbees", "chhabbis", "chabbis", "chabbees"),
    27: ("sattaees", "sattais", "sattaais"),
    28: ("atthaees", "atthais", "athais", "athaais", "athaees"),
    29: ("untees", "untis", "unatis"), 30: ("tees", "tis"),
    31: ("ikattees", "ikattis", "iktees", "iktis"), 32: ("battees", "battis", "batis"),
    33: ("taintees", "taintis", "tentis", "tetis"),
    34: ("chauntees", "chauntis", "chautis", "chontis", "chotis"),
    35: ("paintees", "paintis", "pentis", "paitis"),
    36: ("chhattees", "chhattis", "chattis"), 37: ("saintees", "saintis", "sentis"),
    38: ("adtees", "adtis", "artees", "artis"),
    39: ("untaalees", "untalis", "untalees", "unchalis"),
    40: ("chaalees", "chalis", "chaalis", "chalees"),
    41: ("iktaalees", "iktalis", "ektalis"),
    42: ("bayaalees", "bayalis", "byalis", "biyalis"),
    43: ("taintaalees", "taintalis", "tentalis"),
    44: ("chavaalees", "chavalis", "chauvalis", "chaualis"),
    45: ("paintaalees", "paintalis", "pentalis"),
    46: ("chhiyaalees", "chhiyalis", "chiyalis"),
    47: ("saintaalees", "saintalis", "sentalis"),
    48: ("adtaalees", "adtalis", "artalis", "artalees"),
    49: ("unchaas", "unchas", "unachas"), 50: ("pachaas", "pachas"),
    51: ("ikyaavan", "ikyavan", "ekyavan", "ikkyavan"), 52: ("baavan", "bavan"),
    53: ("tirpan", "tirepan", "trepan"), 54: ("chauvan", "chovan", "chauban"),
    55: ("pachpan", "pachapan"), 56: ("chhappan", "chappan"),
    57: ("sattaavan", "sattavan"), 58: ("atthaavan", "atthavan", "athavan"),
    59: ("unsath", "unsaath", "unasath"), 60: ("saath", "sath"),
    61: ("iksath", "iksaath", "eksath"), 62: ("baasath", "basath"),
    63: ("tirsath", "tiresath"), 64: ("chaunsath", "chausath", "chonsath"),
    65: ("painsath", "paisath", "pensath"),
    66: ("chhiyaasath", "chhiyasath", "chiyasath"),
    67: ("sadsath", "sarsath"), 68: ("adsath", "arsath"),
    69: ("unhattar", "unahattar"), 70: ("sattar",),
    71: ("ikhattar", "ikahattar"), 72: ("bahattar", "behattar"),
    73: ("tihattar", "tehattar"), 74: ("chauhattar", "chohattar"),
    75: ("pachhattar", "pachattar", "pachahattar"),
    76: ("chhihattar", "chhiyattar", "chihattar"),
    77: ("sathattar", "satattar", "satahattar"),
    78: ("athhattar", "athattar", "athahattar"),
    79: ("unaasi", "unasi", "unyaasi", "unyasi"), 80: ("assi", "asi"),
    81: ("ikyaasi", "ikyasi", "ekyasi"), 82: ("bayaasi", "bayasi", "biyasi"),
    83: ("tiraasi", "tirasi"), 84: ("chauraasi", "chaurasi", "chorasi"),
    85: ("pachaasi", "pachasi"), 86: ("chhiyaasi", "chhiyasi", "chiyasi"),
    87: ("sattaasi", "sattasi"), 88: ("atthaasi", "atthasi", "athasi"),
    89: ("navaasi", "navasi"), 90: ("nabbe", "nabe", "navve"),
    91: ("ikyaanave", "ikyanve", "ikyanbe", "ekyanve"),
    92: ("baanave", "banve", "baanbe", "banbe"),
    93: ("tiraanave", "tiranve", "tiranbe"),
    94: ("chauraanave", "chauranve", "chauranbe"),
    95: ("pachaanave", "pachanve", "pachanbe"),
    96: ("chhiyaanave", "chhiyanve", "chiyanve"),
    97: ("sattaanave", "sattanve", "sattanbe"),
    98: ("atthaanave", "atthanve", "athanve"),
    99: ("ninyaanave", "ninyanve", "ninyanbe"),
}

DEVANAGARI: dict[int, tuple[str, ...]] = {
    1: ("एक",), 2: ("दो",), 3: ("तीन",), 4: ("चार",), 5: ("पाँच", "पांच"),
    6: ("छह", "छः", "छै", "छे"), 7: ("सात",), 8: ("आठ",), 9: ("नौ",), 10: ("दस",),
    11: ("ग्यारह",), 12: ("बारह",), 13: ("तेरह",), 14: ("चौदह",),
    15: ("पंद्रह", "पन्द्रह"), 16: ("सोलह",), 17: ("सत्रह",), 18: ("अठारह",),
    19: ("उन्नीस",), 20: ("बीस",), 21: ("इक्कीस",), 22: ("बाईस",), 23: ("तेईस",),
    24: ("चौबीस",), 25: ("पच्चीस",), 26: ("छब्बीस",), 27: ("सत्ताईस",),
    28: ("अट्ठाईस", "अठ्ठाईस", "अठाईस"), 29: ("उनतीस", "उन्तीस"), 30: ("तीस",),
    31: ("इकतीस", "इकत्तीस"), 32: ("बत्तीस",), 33: ("तैंतीस", "तेंतीस"),
    34: ("चौंतीस",), 35: ("पैंतीस", "पेंतीस"), 36: ("छत्तीस",), 37: ("सैंतीस",),
    38: ("अड़तीस",), 39: ("उनतालीस", "उन्तालीस", "उनचालीस"), 40: ("चालीस",),
    41: ("इकतालीस",), 42: ("बयालीस", "ब्यालीस"), 43: ("तैंतालीस", "तेंतालीस"),
    44: ("चवालीस", "चौवालीस"), 45: ("पैंतालीस",), 46: ("छियालीस",),
    47: ("सैंतालीस",), 48: ("अड़तालीस",), 49: ("उनचास", "उनन्चास"), 50: ("पचास",),
    51: ("इक्यावन",), 52: ("बावन",), 53: ("तिरपन", "तिरेपन"), 54: ("चौवन", "चव्वन"),
    55: ("पचपन",), 56: ("छप्पन",), 57: ("सत्तावन",), 58: ("अट्ठावन", "अठ्ठावन"),
    59: ("उनसठ",), 60: ("साठ",), 61: ("इकसठ",), 62: ("बासठ",),
    63: ("तिरसठ", "तिरेसठ"), 64: ("चौंसठ",), 65: ("पैंसठ",), 66: ("छियासठ",),
    67: ("सड़सठ", "सरसठ"), 68: ("अड़सठ",), 69: ("उनहत्तर",), 70: ("सत्तर",),
    71: ("इकहत्तर",), 72: ("बहत्तर",), 73: ("तिहत्तर",), 74: ("चौहत्तर",),
    75: ("पचहत्तर",), 76: ("छिहत्तर",), 77: ("सतहत्तर",), 78: ("अठहत्तर",),
    79: ("उन्यासी", "उनासी", "उनयासी"), 80: ("अस्सी",), 81: ("इक्यासी",),
    82: ("बयासी",), 83: ("तिरासी",), 84: ("चौरासी",), 85: ("पचासी",),
    86: ("छियासी",), 87: ("सत्तासी",), 88: ("अट्ठासी", "अठ्ठासी"), 89: ("नवासी",),
    90: ("नब्बे",), 91: ("इक्यानबे", "इक्यानवे"), 92: ("बानबे", "बानवे"),
    93: ("तिरानबे", "तिरानवे"), 94: ("चौरानबे", "चौरानवे"),
    95: ("पचानबे", "पचानवे"), 96: ("छियानबे", "छियानवे"),
    97: ("सत्तानबे", "सत्तानवे"), 98: ("अट्ठानबे", "अट्ठानवे", "अठ्ठानबे"),
    99: ("निन्यानबे", "निन्यानवे"),
}

# Said in English, as shopkeepers often do: "two hundred fifty".
ENGLISH: dict[int, str] = {
    1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven",
    8: "eight", 9: "nine", 10: "ten", 11: "eleven", 12: "twelve", 13: "thirteen",
    14: "fourteen", 15: "fifteen", 16: "sixteen", 17: "seventeen", 18: "eighteen",
    19: "nineteen", 20: "twenty", 30: "thirty", 40: "forty", 50: "fifty",
    60: "sixty", 70: "seventy", 80: "eighty", 90: "ninety",
}

HUNDRED, THOUSAND, LAKH = 100, 1_000, 100_000
MULTIPLIERS: dict[int, tuple[str, ...]] = {
    HUNDRED: ("sau", "hundred", "सौ"),
    THOUSAND: ("hazaar", "hazar", "hajar", "thousand", "हज़ार", "हजार"),
    LAKH: ("lakh", "lac", "lakhs", "lacs", "लाख"),
}

# dedh sau is 150 and dhai sau 250: a whole number on its own. saade, sava and
# paune change the number after them: saade teen sau is 350, sava do sau 225.
WHOLE_FRACTIONS: dict[Fraction, tuple[str, ...]] = {
    Fraction(3, 2): ("dedh", "derh", "डेढ़", "डेढ"),
    Fraction(5, 2): ("dhaai", "dhai", "dhaee", "ढाई"),
}
PREFIXES: dict[Fraction, tuple[str, ...]] = {
    Fraction(1, 2): ("saade", "sade", "saadhe", "sadhe", "साढ़े", "साढे"),
    Fraction(1, 4): ("sava", "savaa", "sawa", "सवा"),
    Fraction(-1, 4): ("paune", "pone", "पौने"),
}

# The words `speak` uses for a fraction, first spelling of each.
SAY_DEDH, SAY_DHAI, SAY_SAADE = "dedh", "dhaai", "saade"
DEVA_DEDH, DEVA_DHAI, DEVA_SAADE = "डेढ़", "ढाई", "साढ़े"
# fmt: on

Kind = Literal["unit", "multiplier", "prefix"]


@dataclass(frozen=True, slots=True)
class Numeral:
    kind: Kind
    value: Fraction
    #: English tens take a unit after them ("twenty five"); Hindi words never do.
    tens: bool = False


def _deva_key(word: str) -> str:
    """Devanagari spellings that differ only in nasal marks or nukta meet here.

    पाँच/पांच, पंद्रह/पन्द्रह, चौंतीस/चौतीस, हज़ार/हजार.
    """
    w = unicodedata.normalize("NFC", word).replace("़", "")
    w = re.sub(r"[ङञणनम]्(?=[क-ह])", "", w)  # a nasal half-letter before a consonant
    return w.replace("ँ", "").replace("ं", "")


@lru_cache(maxsize=4096)
def key(word: str) -> str:
    """The table's key for a word, in either script."""
    return _deva_key(word) if is_devanagari(word) else fold(word)


def _build() -> dict[str, Numeral]:
    table: dict[str, Numeral] = {}

    def add(spelling: str, numeral: Numeral) -> None:
        k = key(spelling)
        seen = table.get(k)
        if seen is not None and seen != numeral:
            raise ValueError(f"{spelling!r} reads as both {seen} and {numeral}")
        table[k] = numeral

    for n, spellings in (*ROMAN.items(), *DEVANAGARI.items()):
        for s in spellings:
            add(s, Numeral("unit", Fraction(n)))
    for n, word in ENGLISH.items():
        add(word, Numeral("unit", Fraction(n), tens=n >= 20))
    for m, words in MULTIPLIERS.items():
        for w in words:
            add(w, Numeral("multiplier", Fraction(m)))
    for f, words in WHOLE_FRACTIONS.items():
        for w in words:
            add(w, Numeral("unit", f))
    for f, words in PREFIXES.items():
        for w in words:
            add(w, Numeral("prefix", f))
    return table


_TABLE = _build()
_DIGITS = re.compile(r"^\d+(?:,\d+)*(?:\.\d+)?$")


def numeral(token: str) -> Numeral | None:
    """What this word is as a number, if it is one. Digits are a unit of any size."""
    if _DIGITS.match(token):
        return Numeral("unit", Fraction(token.replace(",", "")))
    return _TABLE.get(key(token))


def value(run: list[Numeral]) -> Fraction | None:
    """The amount in rupees, or None if the words are not a well-formed number.

    Indian order, largest first: [coefficient] lakh [coefficient] hazaar
    [coefficient] sau [units]. A bare multiplier means one of it ("sau" is 100).
    Two Hindi numbers side by side ("tera do") are not a number: Hindi has one word
    for each of 1 to 99, so that is two things said, and the answer is None.
    """
    total = Fraction(0)
    coef: Fraction | None = None
    coef_tens = False  # the coefficient so far is an English tens word
    shift: Fraction | None = None  # a saade/sava/paune waiting for its number
    last_multiplier: int | None = None

    for n in run:
        if n.kind == "prefix":
            if shift is not None or coef is not None:
                return None
            shift = n.value
        elif n.kind == "unit":
            if coef is not None:
                # "twenty five": an English tens word takes a single unit after it.
                if not (coef_tens and n.value < 10 and shift is None):
                    return None
                coef += n.value
                coef_tens = False
                continue
            coef = n.value + (shift or 0)
            coef_tens = n.tens
            shift = None
        else:  # multiplier
            m = int(n.value)
            if last_multiplier is not None and m >= last_multiplier:
                return None
            c = coef if coef is not None else 1 + (shift or 0)
            if c <= 0 or c >= 100:
                return None
            total += c * m
            coef, coef_tens, shift, last_multiplier = None, False, None, m

    if shift is not None:
        return None
    if coef is not None:
        if last_multiplier is not None and coef >= last_multiplier:
            return None
        total += coef
    return total
