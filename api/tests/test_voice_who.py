"""Who it's for, and the checks on what Sarvam-105B read.

The book here has five Anubhavs, as a real book can. The rules are the ones the
1,338-recording test measured; tests/test_voice_replay.py holds them to it.
"""

from __future__ import annotations

import pytest

from bahi.domain.check import Draft, check_draft, check_rules
from bahi.domain.sound import key, ratio
from bahi.domain.who import Ask, Person, Picked, said_like, shortlist, who

SHUKLA = Person("c-shukla", "Anubhav Shukla", "Room 1006, B wing", "अनुभव शुक्ला")
A204 = Person("c-204", "Anubhav", "Room 204, A wing", "अनुभव")
JAIN = Person("c-jain", "Anubhav Jain", "Medical shop", "अनुभव जैन", "मेडिकल शॉप")
A311 = Person("c-311", "Anubhav", "Room 311, B wing", "अनुभव")
DAS = Person("c-das", "Anubhav Das", "Garage", "अनुभव दास")
ANUBHAVS = (SHUKLA, A204, JAIN, A311, DAS)
SHARMA = Person("c-sharma", "Sharma", "Room 19, B wing", "शर्मा")
IQBAL = Person("c-iqbal", "Iqbal bhai", "Garage, lane 2", "इकबाल भाई")
MEENA = Person("c-meena", "Meena Tai", "Opposite lane", "मीना ताई")
GAIKWAD = Person("c-gaikwad", "Gaikwad", "Chawl 5", "गायकवाड़")
PAWAR = Person("c-pawar", "Pawar", "Room 17, C wing", "पवार")
KAVITA = Person("c-kavita", "Kavita")  # joined offline: no Devanagari
BABLU = Person("c-bablu", "Bablu", "Chai tapri", "बबलू", "चाय तापरी")
ANIL = Person("c-anil", "Anil", "Tailor shop", "अनिल", "टेलर शॉप")
SCRAP = Person("c-shaikh", "Shaikh bhai", "Scrap shop", "शेख भाई", "स्क्रैप शॉप")
ROOMS = [Person(f"c-r{i}", f"Resident {i}", f"Room {i}, B wing") for i in range(1, 6)]
MARKET = [
    Person("c-mutton", "Salim", "Mutton market"),
    Person("c-veg", "Lakshmi", "Vegetable market"),
    Person("c-flower", "Gauri", "Flower market"),
]
BOOK = [
    *ANUBHAVS,
    *(SHARMA, IQBAL, MEENA, GAIKWAD, PAWAR, KAVITA, BABLU, ANIL, SCRAP),
    *ROOMS,
    *MARKET,
]


def picked(words: str, waiting: list[Person] | None = None) -> Picked:
    p = who(words, waiting or [], BOOK)
    assert isinstance(p, Picked), p
    return p


# ── by sound ─────────────────────────────────────────────────────────────────


def test_spellings_of_one_name_sound_the_same() -> None:
    assert len({key(s) for s in ("Anubhav", "anubhaw", "अनुभव", "Anubav")}) == 1


def test_the_score_is_the_one_the_test_used() -> None:
    """rapidfuzz's fuzz.ratio: 200 x LCS / total length. Pawar and Patar share
    p-a-a-r, 4 of 5 letters each: 80, below a pick."""
    assert ratio(key("Pawar"), key("Patar")) == 80.0
    assert ratio("", "") == 100.0 and ratio("abc", "") == 0.0


# ── no name ──────────────────────────────────────────────────────────────────


def test_one_person_waiting_and_no_name_is_that_person() -> None:
    assert who(None, [KAVITA], BOOK) == Picked(KAVITA, "only_one")


def test_several_waiting_and_no_name_is_a_question_not_the_first_in_line() -> None:
    assert who(None, [KAVITA, SHARMA], BOOK) == Ask("who", (KAVITA, SHARMA))


def test_nobody_waiting_and_no_name_is_a_question() -> None:
    assert who("", [], BOOK) == Ask("nobody", ())


# ── twenty Anubhavs ──────────────────────────────────────────────────────────


@pytest.mark.parametrize("said", ["अनुभव", "Anubhav", "Anubhaw", "अनुबव"])
def test_a_name_five_people_have_asks_which_one(said: str) -> None:
    assert who(said, [], BOOK) == Ask("several", ANUBHAVS)


@pytest.mark.parametrize(
    ("said", "person"),
    [
        ("अनुभव शुक्ला", SHUKLA),
        ("Anubhav Shukla", SHUKLA),
        ("Shukla ji", SHUKLA),
        ("अनुभव जैन", JAIN),
    ],
)
def test_the_whole_name_picks_one_of_them(said: str, person: Person) -> None:
    assert picked(said) == Picked(person, "in_book")


@pytest.mark.parametrize(
    ("said", "person"),
    [
        ("रूम दो सौ चार वाले अनुभव", A204),
        ("204 wale Anubhav", A204),
        ("Anubhav 1006", SHUKLA),
        ("दस सौ छह वाले अनुभव", SHUKLA),
    ],
)
def test_a_room_number_said_picks_one_of_them(said: str, person: Person) -> None:
    assert picked(said).person == person


def test_number_words_are_a_number_never_a_name() -> None:
    """ "दस सौ छह" is 1006, not "Das": Anubhav Das must not tie with Shukla."""
    assert picked("दस सौ छह वाले अनुभव").person == SHUKLA


def test_the_one_at_the_counter_beats_his_namesakes_in_the_book() -> None:
    assert who("अनुभव", [A311], BOOK) == Picked(A311, "at_counter")


# ── other names ──────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("said", "person"),
    [
        ("गायकवाड़", GAIKWAD),  # matched through his name in Devanagari
        ("Gaikwad", GAIKWAD),
        ("इक़बाल भाई", IQBAL),
        ("Iqbal", IQBAL),
        ("मीना ताई", MEENA),
        ("Meena", MEENA),
        ("कविता", KAVITA),  # no Devanagari on file: the roman still matches
    ],
)
def test_a_name_is_found_in_either_script(said: str, person: Person) -> None:
    assert picked(said).person == person


# ── how the shop describes him ───────────────────────────────────────────────


@pytest.mark.parametrize("said", ["चाय टपरी वाले", "chai tapri wala", "Chai tapri"])
def test_the_shops_description_of_him_picks_him(said: str) -> None:
    assert picked(said) == Picked(BABLU, "in_book")


def test_a_description_narrows_a_shared_name() -> None:
    """ "मेडिकल वाले अनुभव": the Anubhav at the medical shop, not all five."""
    assert picked("मेडिकल वाले अनुभव").person == JAIN
    assert picked("medical wale Anubhav").person == JAIN


def test_a_word_three_customers_share_asks_among_them() -> None:
    assert who("market wale", [], BOOK) == Ask("several", tuple(MARKET))
    assert picked("mutton market wale").person == MARKET[0]


def test_a_word_many_customers_share_tells_nobody_apart() -> None:
    """Five rooms in B wing: "room" and "wing" point to no one, and nothing in the
    code says so; the book does."""
    for said in ("room wale", "B wing wale"):
        result = who(said, [], BOOK)
        assert isinstance(result, Ask)
        assert not set(result.among) & set(ROOMS)
    assert who("B wing wale Anubhav", [], BOOK) == Ask("several", ANUBHAVS)


def test_short_description_words_are_not_enough_alone() -> None:
    """ "shop" is three letters by sound, like "van" or "pan": too easily a word
    said in passing. The whole phrase still counts."""
    assert not isinstance(who("shop wale", [], BOOK), Picked)
    assert picked("tailor shop wale").person == ANIL


def test_what_tells_customers_apart_comes_from_the_whole_book() -> None:
    """Offered two of the five rooms, "room" still tells nobody apart, because the
    book has five; and "fish" still picks among the market three."""
    two_rooms = ROOMS[:2]
    result = who("room wale", [], two_rooms, known=BOOK)
    assert not (isinstance(result, Ask) and result.why == "several")
    assert who("mutton wale", [], MARKET[:2], known=BOOK) == Picked(MARKET[0], "in_book")


def test_a_weak_match_is_offered_never_picked() -> None:
    assert who("Patar", [], BOOK) == Ask("maybe", (PAWAR,))


def test_a_name_that_fits_nobody_is_a_question() -> None:
    assert who("Ramesh", [KAVITA], BOOK) == Ask("not_found", ())


def test_words_the_reader_quoted_but_nobody_said_are_not_a_name() -> None:
    assert who("Vaibhav", [], BOOK, transcript="Sharma ko do sau") == Ask("not_said", ())


def test_a_quote_written_in_the_other_script_still_counts_as_said() -> None:
    assert said_like("Sharma", "शर्मा को दो सौ")


def test_the_shortlist_is_names_that_sound_alike_numbers_and_the_counter() -> None:
    shown = shortlist("अनुभव 204 को सौ", [KAVITA], BOOK)
    assert set(ANUBHAVS) <= set(shown) and KAVITA in shown
    assert SHARMA not in shown


# ── Sarvam-105B's draft, checked ─────────────────────────────────────────────

SAID = "अनुभव शुक्ला को दो सौ बीस रुपये दे दो"


def draft(**kw: object) -> Draft:
    base: dict[str, object] = {
        "intent": "udhaar",
        "amount_words": "दो सौ बीस",
        "amount_rupees": 220,
        "person_words": "अनुभव शुक्ला",
        "customer_id": None,
        "candidates": (),
        "reason": "",
    }
    return Draft(**(base | kw))  # type: ignore[arg-type]


def test_a_draft_that_holds_to_the_words_goes_through() -> None:
    c = check_draft(SAID, draft(), shortlist(SAID, [], BOOK), [], BOOK)
    assert (c.amount_paise, c.problem, c.who) == (22000, None, Picked(SHUKLA, "in_book"))
    assert all(x.ok for x in c.checks)
    assert [x.kind for x in c.checks] == [
        "amount_said",
        "amount_read",
        "person_said",
        "person_fits",
    ]


def test_an_amount_the_words_do_not_hold_is_refused() -> None:
    """Part of the words ("दो सौ" of "दो सौ बीस"), or words never said."""
    c = check_draft(SAID, draft(amount_words="दो सौ"), [], [], BOOK)
    c2 = check_draft(SAID, draft(amount_words="तीन सौ", amount_rupees=300), [], [], BOOK)
    assert (c.problem, c.amount_paise) == ("amount_mismatch", None)
    assert (c2.problem, c2.amount_paise) == ("amount_not_said", None)


def test_an_amount_our_parser_reads_differently_is_refused() -> None:
    c = check_draft(SAID, draft(amount_rupees=2200), [], [], BOOK)
    assert (c.problem, c.amount_paise) == ("amount_mismatch", None)


def test_a_customer_the_model_was_never_shown_is_refused() -> None:
    c = check_draft(SAID, draft(customer_id="c-made-up"), [SHUKLA], [], BOOK)
    assert c.problem == "invented_customer" and c.amount_paise is None


def test_the_person_is_decided_by_our_code_not_by_the_models_pick() -> None:
    c = check_draft(SAID, draft(customer_id="c-204"), [SHUKLA, A204], [], BOOK)
    assert c.who == Picked(SHUKLA, "in_book")


def test_no_amount_said_is_no_amount() -> None:
    c = check_draft(
        SAID, draft(intent="unclear", amount_words=None, amount_rupees=None), [], [], BOOK
    )
    assert c.problem == "no_amount"


def test_offline_our_parser_reads_and_the_same_checks_decide_who() -> None:
    c = check_rules("Sharma ko dhaai sau udhaar", [], BOOK)
    assert (c.reader, c.intent, c.amount_paise) == ("rules", "udhaar", 25000)
    assert c.who == Picked(SHARMA, "in_book")
    assert check_rules("अनुभव को दो सौ", [], BOOK).who == Ask("several", ANUBHAVS)
