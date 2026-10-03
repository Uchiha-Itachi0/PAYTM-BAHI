"""The domain rules, with no database: money, rhythm, limitation, the book."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from bahi.domain.book import Customer, Entry, book, line
from bahi.domain.limitation import claimable_until, expired
from bahi.domain.money import rupees
from bahi.domain.rhythm import rhythm

TODAY = date(2026, 10, 3)


# ── money ────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("paise", "text"),
    [
        (0, "₹0"),
        (20000, "₹200"),
        (124000, "₹1,240"),
        (12400000, "₹1,24,000"),
        (1000000000, "₹1,00,00,000"),
        (1250, "₹12.50"),
        (5, "₹0.05"),
        (-20000, "-₹200"),
    ],
)
def test_rupees_uses_indian_grouping(paise: int, text: str) -> None:
    assert rupees(paise) == text


# ── rhythm ───────────────────────────────────────────────────────────────────


def days(*gaps: int, last: date = TODAY - timedelta(days=4)) -> list[date]:
    out = [last]
    for g in reversed(gaps):
        out.insert(0, out[0] - timedelta(days=g))
    return out


def test_rhythm_is_the_median_of_his_own_gaps() -> None:
    r = rhythm(days(9, 8, 10, 9, 12), TODAY)
    assert (r.n, r.median_gap, r.max_gap, r.day) == (5, 9, 12, 4)


def test_median_is_a_gap_he_actually_had() -> None:
    # Four gaps: a mean-of-middle median would say 8.5 days; median_low says 8.
    assert rhythm(days(7, 8, 9, 10), TODAY).median_gap == 8


def test_one_payment_that_clears_three_entries_is_one_payment() -> None:
    d = TODAY - timedelta(days=4)
    assert rhythm([d, d, d, d - timedelta(days=9)], TODAY).n == 1


def test_no_payments_is_no_rhythm_rather_than_a_guess() -> None:
    r = rhythm([], TODAY)
    assert (r.n, r.median_gap, r.day, r.enough) == (0, None, None, False)


def test_payments_after_today_are_ignored() -> None:
    assert rhythm([TODAY + timedelta(days=1)], TODAY).last_paid is None


# ── limitation ───────────────────────────────────────────────────────────────


def test_three_years_from_the_sale() -> None:
    assert claimable_until(date(2023, 7, 14), None) == date(2026, 7, 14)
    assert expired(date(2023, 7, 14), None, TODAY)
    assert not expired(date(2023, 7, 14), None, date(2026, 7, 14))


def test_an_acknowledgment_restarts_the_clock() -> None:
    assert claimable_until(date(2023, 7, 14), date(2024, 1, 5)) == date(2027, 1, 5)
    assert not expired(date(2023, 7, 14), date(2024, 1, 5), TODAY)


def test_29_february_lands_on_28_february() -> None:
    assert claimable_until(date(2024, 2, 29), None) == date(2027, 2, 28)


# ── the book ─────────────────────────────────────────────────────────────────


def entry(
    paise: int,
    status: str = "confirmed",
    on: date = TODAY,
    paid: int = 0,
    acked: bool = True,
) -> Entry:
    return Entry(f"e{paise}{status}{on}", paise, paid, status, on, on if acked else None)


def customer(
    *entries: Entry,
    gaps: tuple[int, ...] = (9, 8, 10, 9),
    day: int = 4,
    joined: str = "linked",
    name: str = "Sharma",
) -> Customer:
    return Customer(
        id=name,
        display_name=name,
        tag=None,
        joined=joined,  # type: ignore[arg-type]
        entries=entries,
        paid_on=tuple(days(*gaps, last=TODAY - timedelta(days=day))),
    )


def test_inside_his_own_gap_is_on_rhythm() -> None:
    ln = line(customer(entry(20000)), TODAY)
    assert ln is not None and (ln.chip, ln.day, ln.balance_paise) == (
        "on_rhythm",
        4,
        20000,
    )


def test_past_his_longest_gap_is_changed() -> None:
    ln = line(customer(entry(20000), day=11), TODAY)
    assert ln is not None and ln.chip == "changed"


def test_an_unanswered_entry_is_not_confirmed_and_still_counts() -> None:
    ln = line(customer(entry(15000, "recorded", acked=False)), TODAY)
    assert ln is not None and (ln.chip, ln.balance_paise) == ("not_confirmed", 15000)


def test_a_name_only_customer_is_read_by_his_rhythm() -> None:
    c = customer(entry(6000, "recorded", acked=False), joined="name_only")
    ln = line(c, TODAY)
    assert ln is not None and ln.chip == "on_rhythm"


def test_too_little_history_is_new() -> None:
    ln = line(customer(entry(30000), gaps=(13,)), TODAY)
    assert ln is not None and ln.chip == "new"


def test_expired_corrected_and_paid_entries_owe_nothing() -> None:
    c = customer(
        entry(18000, "recorded", on=date(2023, 7, 14), acked=False),
        entry(20000, "corrected"),
        entry(40000, "confirmed", paid=40000),
    )
    assert line(c, TODAY) is None


def test_a_part_payment_leaves_the_rest_owed() -> None:
    ln = line(customer(entry(40000, paid=15000)), TODAY)
    assert ln is not None and ln.balance_paise == 25000


def test_the_book_is_alphabetical_never_by_amount() -> None:
    b = book(
        [
            customer(entry(90000), name="zaheer"),
            customer(entry(1000), name="Amit"),
            customer(entry(50000), name="meena"),
        ],
        TODAY,
    )
    assert [ln.display_name for ln in b.lines] == ["Amit", "meena", "zaheer"]
    assert (b.owing_count, b.outstanding_paise) == (3, 141000)
