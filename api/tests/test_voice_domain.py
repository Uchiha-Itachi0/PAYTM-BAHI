"""The voice rules: number words, the parse, the readback, and the scripts.

None of this touches speech recognition. The transcript is a string; from there
to an amount is these rules, and these tests pin them. Who it is for is
tests/test_voice_who.py.
"""

from __future__ import annotations

import pytest

from bahi.domain.numerals import numeral
from bahi.domain.parse import heard
from bahi.domain.script import fold, to_roman, tokens
from bahi.domain.speak import say

# ── the parse ────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("text", "name", "paise"),
    [
        ("do sau", None, 20000),
        ("Sharma ko do sau udhaar", "Sharma", 20000),
        ("Kavita, teen sau", "Kavita", 30000),
        ("शर्मा को दो सौ उधार", "शर्मा", 20000),
        ("Iqbal bhai ka dhaai sau likh do", "Iqbal bhai", 25000),
        ("Sharma ko do sau de do", "Sharma", 20000),  # the second "do" is "give"
        ("dedh sau", None, 15000),
        ("saade teen sau", None, 35000),
        ("sava sau", None, 12500),
        ("paune do sau", None, 17500),
        ("barah sau", None, 120000),
        ("dedh hazaar", None, 150000),
        ("do hazaar paanch sau", None, 250000),
        ("do sau aur pachaas", None, 25000),
        ("two hundred fifty", None, 25000),
        ("₹450 Meena Tai", "Meena Tai", 45000),
        ("Patil 1,200 rupaye", "Patil", 120000),
        ("राजू को ₹२००", "राजू", 20000),
        ("साढ़े तीन सौ", None, 35000),
        ("हजार", None, 100000),  # हज़ार without the nukta
        ("do sau, haan do sau", None, 20000),  # said twice, same amount
    ],
)
def test_it_hears_the_amount_and_the_name(
    text: str, name: str | None, paise: int
) -> None:
    h = heard(text)
    assert (h.name, h.amount_paise, h.problem) == (name, paise, None)


@pytest.mark.parametrize(
    "text",
    [
        "Sharma ko do sau aur Patil ko teen sau",  # two amounts
        "Sharma tera do sau",  # "tera" is 13 and "your": not a number, so ask
        "do sau teen sau",
        "sau sau",
        "saade teen",  # ₹3.50, or saade teen sau with the sau swallowed: ask
        "0",
    ],
)
def test_it_asks_rather_than_guess_an_amount(text: str) -> None:
    h = heard(text)
    assert h.amount_paise is None
    assert h.problem == "unclear_amount"


def test_no_number_is_no_amount() -> None:
    h = heard("Patil")
    assert (h.name, h.amount_paise, h.problem) == ("Patil", None, "no_amount")


@pytest.mark.parametrize("word", ["chai", "no", "hai", "to", "so", "sab", "bhai", "ko"])
def test_everyday_words_are_not_numbers(word: str) -> None:
    assert numeral(word) is None


# ── the readback ─────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("rupees", "roman", "devanagari"),
    [
        (100, "sau", "सौ"),
        (150, "dedh sau", "डेढ़ सौ"),
        (200, "do sau", "दो सौ"),
        (250, "dhaai sau", "ढाई सौ"),
        (350, "saade teen sau", "साढ़े तीन सौ"),
        (1200, "baarah sau", "बारह सौ"),
        (1500, "dedh hazaar", "डेढ़ हज़ार"),
        (2500, "dhaai hazaar", "ढाई हज़ार"),
        (100000, "ek lakh", "एक लाख"),
    ],
)
def test_the_amount_is_said_the_way_a_counter_says_it(
    rupees: int, roman: str, devanagari: str
) -> None:
    said = say(rupees * 100)
    assert (said.roman, said.devanagari) == (roman, devanagari)


def test_every_amount_said_back_is_heard_as_the_same_amount() -> None:
    """parse(say(n)) == n, in both scripts, for every whole rupee up to ₹1 lakh."""
    wrong = []
    for rupees in range(1, 100_001):
        said = say(rupees * 100)
        for text in (said.roman, said.devanagari):
            if heard(text).amount_paise != rupees * 100:
                wrong.append((rupees, text))
    assert wrong == []


def test_only_whole_rupees_are_said() -> None:
    with pytest.raises(ValueError, match="whole rupees"):
        say(12550)


# ── the scripts ──────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("devanagari", "roman"),
    [
        ("शर्मा", "sharmaa"),
        ("कमला", "kamlaa"),  # the silent "a" in the middle
        ("इक़बाल", "iqbaal"),  # nukta
        ("रमेश", "ramesh"),  # the silent "a" at the end
        ("कविता", "kavitaa"),  # but never the first
    ],
)
def test_devanagari_reads_out_in_roman(devanagari: str, roman: str) -> None:
    assert to_roman(devanagari) == roman


def test_spellings_of_one_name_meet() -> None:
    assert fold("Sharma") == fold("sharmaa") == fold("शर्मा")
    assert fold("Iqbal") == fold("इक़बाल")
    assert fold("Shaikh") == fold("shekh")


def test_numbers_that_sound_alike_do_not_meet() -> None:
    assert fold("saath") != fold("saat")  # 60 and 7
    assert fold("chhe") != fold("chai")  # 6 and tea


def test_devanagari_words_are_not_split_at_their_vowel_signs() -> None:
    assert tokens("शर्मा को ₹२००, ok") == ["शर्मा", "को", "200", "ok"]


def test_money_arriving_says_what_was_owed_what_came_and_what_is_left() -> None:
    from bahi.voice.said import received

    assert received(10000, 10000) == (
        "दो सौ रुपये का उधार था, उसमें से सौ रुपये मिले, सौ रुपये बाकी।"
    )
    assert received(20000, 0) == "दो सौ रुपये का उधार था, पूरे दो सौ रुपये मिले, हिसाब पूरा।"
