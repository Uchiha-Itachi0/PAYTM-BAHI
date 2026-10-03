"""The seed says what the demo needs it to say, read back through the domain code."""

from __future__ import annotations

import json
from datetime import date

from bahi.domain.book import Book, book
from bahi.domain.rhythm import rhythm
from bahi.store import book as store
from data import contract, db
from data.generate import plan
from data.world import HOME, TODAY, uid


def home_book(con: db.Conn) -> Book:
    return book(store.load(con, str(uid("shop", HOME))), TODAY)


def test_the_plan_is_identical_every_time() -> None:
    assert plan() == plan()


def test_the_contract_is_the_database_not_a_hand_edit(con: db.Conn) -> None:
    on_disk = json.loads(contract.CONTRACT.read_text(encoding="utf-8"))
    assert on_disk == contract.build(con)


def test_the_book_adds_up(con: db.Conn) -> None:
    b = home_book(con)
    assert (b.customer_count, b.invited_count, b.owing_count) == (60, 1, 38)


def test_only_the_four_written_in_have_changed(con: db.Conn) -> None:
    changed = {ln.display_name for ln in home_book(con).lines if ln.chip == "changed"}
    assert changed == {"Patil", "Iqbal bhai", "Raju", "Salma"}


def test_everyone_generated_sits_inside_their_own_rhythm(con: db.Conn) -> None:
    crowd = {str(uid("customer", HOME, f"crowd-{i:02d}")) for i in range(47)}
    owing = [ln for ln in home_book(con).lines if ln.customer_id in crowd]
    assert len(owing) == 27
    for ln in owing:
        assert ln.chip == "on_rhythm", ln.display_name
        assert ln.rhythm.n >= 3, ln.display_name


def test_sharma_pays_every_nine_days_and_today_is_day_four(con: db.Conn) -> None:
    ln = next(x for x in home_book(con).lines if x.display_name == "Sharma")
    assert (ln.rhythm.median_gap, ln.rhythm.max_gap, ln.day, ln.chip) == (
        9,
        12,
        4,
        "on_rhythm",
    )
    assert ln.balance_paise == 20000


def test_patil_has_gone_past_anything_he_has_done_before(con: db.Conn) -> None:
    ln = next(x for x in home_book(con).lines if x.display_name == "Patil")
    assert (ln.rhythm.max_gap, ln.day, ln.balance_paise) == (30, 40, 96000)


def test_sharmas_2023_entry_is_kept_but_owes_nothing(con: db.Conn) -> None:
    sharma = next(
        c for c in store.load(con, str(uid("shop", HOME))) if c.display_name == "Sharma"
    )
    old = [e for e in sharma.entries if e.recorded_on == date(2023, 7, 14)]
    assert len(old) == 1 and not old[0].claimable(TODAY)


def test_sharma_owes_across_three_shops(con: db.Conn) -> None:
    person = uid("person", "sharma")
    with con.cursor() as cur:
        cur.execute(
            "SELECT shop_id::text, id::text FROM customers WHERE person_id = %s",
            (person,),
        )
        rows = cur.fetchall()
    assert len(rows) == 3

    total = 0
    for shop, cid in rows:
        ln = next(
            x for x in book(store.load(con, shop), TODAY).lines if x.customer_id == cid
        )
        total += ln.balance_paise
    assert total == 20000 + 69000 + 35000


def test_nothing_is_recorded_against_an_invitation(con: db.Conn) -> None:
    with con.cursor() as cur:
        cur.execute(
            """
            SELECT count(*) FROM entries e JOIN customers c ON c.id = e.customer_id
            WHERE c.person_id IS NOT NULL AND c.linked_at IS NULL
            """
        )
        assert cur.fetchone() == (0,)


def test_a_name_only_customer_never_confirms(con: db.Conn) -> None:
    with con.cursor() as cur:
        cur.execute(
            """
            SELECT count(*) FROM acknowledgments a
            JOIN entries e ON e.id = a.entry_id
            JOIN customers c ON c.id = e.customer_id
            WHERE c.person_id IS NULL
            """
        )
        assert cur.fetchone() == (0,)


def test_the_dispute_left_the_wrong_amount_corrected_and_the_right_one_paid(
    con: db.Conn,
) -> None:
    with con.cursor() as cur:
        cur.execute(
            """
            SELECT w.amount_paise, w.status, r.amount_paise, r.status
            FROM entries r JOIN entries w ON w.id = r.corrects_entry_id
            """
        )
        assert cur.fetchall() == [(20000, "corrected", 15000, "settled")]


def test_a_gap_is_counted_in_days_he_paid(con: db.Conn) -> None:
    """Rows paid in one go share a day, and count once."""
    sharma = next(
        c for c in store.load(con, str(uid("shop", HOME))) if c.display_name == "Sharma"
    )
    assert rhythm(sharma.paid_on, TODAY).n == len(set(sharma.paid_on)) - 1
