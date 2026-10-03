"""Tonight: who gets a reminder tomorrow, and why everyone else is left alone.

The decision is arithmetic over each customer's own history (domain/tonight.py),
tested here by hand and on the seed. The reminder's words may come from the
munshi, but our check holds them to the one figure the book gave.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date, time, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient

from bahi.domain.book import Customer, Entry
from bahi.domain.tonight import send_hour, tonight
from bahi.munshi.writer import fits
from bahi.service import app
from bahi.service.deps import connection
from data import db
from data.world import HOME, uid

SHOP = str(uid("shop", HOME))
PATIL = str(uid("customer", HOME, "patil"))
TODAY = date(2026, 10, 3)


def person(
    key: str,
    paid: list[int],
    *,
    joined: str = "linked",
    status: str = "confirmed",
) -> Customer:
    """Someone who paid `paid` days ago (oldest first) and owes ₹100 today."""
    return Customer(
        id=key,
        display_name=key.title(),
        tag=None,
        joined=joined,  # type: ignore[arg-type]
        entries=(Entry("e-" + key, 100_00, 0, status, TODAY - timedelta(days=1), None),),
        paid_on=tuple(TODAY - timedelta(days=d) for d in paid),
    )


# ── the decision, by hand ────────────────────────────────────────────────────


def test_past_his_longest_gap_he_is_sent_one() -> None:
    # gaps 10, 10, 10; last paid 15 days ago: past anything he has done
    t = tonight([person("raju", [45, 35, 25, 15])], TODAY, {}, {})
    assert [(p.send, p.why) for p in t.plans] == [(True, "past_longest_gap")]
    assert t.for_day == TODAY + timedelta(days=1)


def test_inside_his_own_gap_he_is_left_alone() -> None:
    # usual gap 18; day 11 is normal for him, however long it looks
    t = tonight([person("meena", [65, 47, 29, 11])], TODAY, {}, {})
    assert [(p.send, p.why) for p in t.plans] == [(False, "inside_gap")]


def test_an_entry_he_has_not_said_yes_to_waits() -> None:
    t = tonight([person("anil", [45, 35, 25, 15], status="recorded")], TODAY, {}, {})
    assert t.plans[0].why == "not_confirmed" and not t.plans[0].send


def test_an_entry_he_says_is_wrong_waits_for_the_chat() -> None:
    t = tonight([person("kamla", [45, 35, 25, 15], status="disputed")], TODAY, {}, {})
    assert t.plans[0].why == "disputed"


def test_too_little_history_is_not_read() -> None:
    t = tonight([person("nikhil", [30, 15])], TODAY, {}, {})
    assert t.plans[0].why == "too_new"


def test_nobody_kept_by_name_only_is_ever_messaged() -> None:
    t = tonight(
        [person("bablu", [45, 35, 25, 15], joined="name_only", status="recorded")],
        TODAY,
        {},
        {},
    )
    assert (t.plans[0].send, t.plans[0].why) == (False, "no_phone")


def test_one_reminder_a_gap_never_a_stream() -> None:
    raju = person("raju", [45, 35, 25, 15])
    t = tonight([raju], TODAY, {}, {"raju": TODAY - timedelta(days=3)})
    assert t.plans[0].why == "reminded"
    t = tonight([raju], TODAY, {}, {"raju": TODAY - timedelta(days=10)})
    assert t.plans[0].send


def test_someone_who_owes_nothing_is_not_on_the_list() -> None:
    paid_up = Customer("x", "X", None, "linked", (), (TODAY,))
    assert tonight([paid_up], TODAY, {}, {}).plans == ()


def test_the_hour_is_when_he_usually_pays_within_the_day() -> None:
    assert send_hour([time(10, 5), time(10, 40), time(10, 20)]) == time(10, 0)
    assert send_hour([time(18, 35), time(18, 50), time(18, 40)]) == time(18, 30)
    assert send_hour([time(22, 15)]) == time(20, 0), "never at night"
    assert send_hour([time(6, 0)]) == time(9, 0), "never before nine"
    assert send_hour([]) == time(10, 0)


# ── the munshi's words, held to the book's figure ────────────────────────────


@pytest.mark.parametrize(
    ("text", "ok"),
    [
        ("Patil bhai, ₹960 ka udhaar hai. Koi dikkat ho to bata dena.", True),
        ("पाटिल भाई, ₹960 का उधार है। कोई दिक्कत हो तो बताना।", True),
        ("Patil bhai, Rs. 960 ka udhaar hai.", True),
        ("Patil bhai, ₹1,960 ka udhaar hai.", False),
        ("Patil bhai, ₹960 ka udhaar hai. 5 tarikh tak de dena.", False),
        ("Patil bhai, ₹960, ५ तारीख तक।", False),
        ("", False),
        ("Patil bhai " * 40, False),
    ],
)
def test_a_reminder_names_his_balance_and_no_other_figure(text: str, ok: bool) -> None:
    assert fits(text, 960_00) is ok


# ── on the seed, over HTTP ───────────────────────────────────────────────────


@pytest.fixture
def api(tx: db.Conn) -> Iterator[TestClient]:
    def within_savepoint() -> Iterator[db.Conn]:
        with tx.transaction():
            yield tx

    app.dependency_overrides[connection] = within_savepoint
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def sending(out: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {p["display_name"]: p for p in out["plans"] if p["send"]}


def test_four_of_thirty_eight(api: TestClient) -> None:
    out = api.get(f"/shops/{SHOP}/tonight").json()
    assert (out["sending_count"], out["owing_count"]) == (4, 38)
    assert set(sending(out)) == {"Patil", "Iqbal bhai", "Raju", "Salma"}
    held = {p["display_name"]: p["why"] for p in out["plans"] if not p["send"]}
    assert held["Sharma"] == "inside_gap"
    assert held["Anil"] == "not_confirmed"
    assert held["Nikhil"] == "too_new"
    assert list(held.values()).count("inside_gap") == 31


def test_reading_tonight_writes_nothing(api: TestClient) -> None:
    out = api.get(f"/shops/{SHOP}/tonight").json()
    assert all(p["reminder"] is None for p in out["plans"])


def test_the_run_writes_each_reminder_once_at_his_hour(api: TestClient) -> None:
    first = sending(api.post(f"/shops/{SHOP}/tonight").json())
    patil = first["Patil"]["reminder"]
    assert patil["status"] == "planned" and patil["written"] == "words"
    assert "₹960" in patil["body"]
    assert patil["send_at"].startswith("2026-10-04T10:00")
    again = sending(api.post(f"/shops/{SHOP}/tonight").json())
    assert again["Patil"]["reminder"]["id"] == patil["id"]


def test_a_stopped_reminder_never_goes(api: TestClient) -> None:
    patil = sending(api.post(f"/shops/{SHOP}/tonight").json())["Patil"]["reminder"]
    r = api.post(f"/shops/{SHOP}/reminders/{patil['id']}/stop")
    assert r.json()["status"] == "stopped"
    assert api.post(f"/shops/{SHOP}/tonight/send-now").json() == {"sent": 3}
    thread = api.get(f"/shops/{SHOP}/customers/{PATIL}/thread").json()
    assert not [m for m in thread["messages"] if m["kind"] == "reminder"]


def test_he_rewrites_a_reminder_and_picks_its_hour(api: TestClient) -> None:
    patil = sending(api.post(f"/shops/{SHOP}/tonight").json())["Patil"]["reminder"]
    words = "Patil ji, jab ho sake tab aa jana."
    r = api.post(
        f"/shops/{SHOP}/reminders/{patil['id']}", json={"body": words, "at": "18:30"}
    )
    assert r.status_code == 200, r.text
    assert (r.json()["body"], r.json()["written"]) == (words, "shop")
    assert r.json()["send_at"].startswith("2026-10-04T18:30")
    # Never at night, whoever sets the hour.
    late = api.post(f"/shops/{SHOP}/reminders/{patil['id']}", json={"at": "23:00"})
    assert late.status_code == 409
    api.post(f"/shops/{SHOP}/tonight/send-now")
    thread = api.get(f"/shops/{SHOP}/customers/{PATIL}/thread").json()
    sent = [m["body"] for m in thread["messages"] if m["kind"] == "reminder"]
    assert sent == [words]


def test_a_pause_holds_him_and_stops_tomorrows(api: TestClient) -> None:
    patil = sending(api.post(f"/shops/{SHOP}/tonight").json())["Patil"]["reminder"]
    r = api.post(f"/shops/{SHOP}/customers/{PATIL}/pause", json={"until": "2026-10-20"})
    assert r.status_code == 204, r.text
    out = api.get(f"/shops/{SHOP}/tonight").json()
    p = next(p for p in out["plans"] if p["display_name"] == "Patil")
    assert (p["send"], p["why"]) == (False, "asked_to_wait")
    assert p["reminder"]["id"] == patil["id"] and p["reminder"]["status"] == "stopped"
    far = api.post(f"/shops/{SHOP}/customers/{PATIL}/pause", json={"until": "2027-06-01"})
    assert far.status_code == 409, "three months at most, like any wait"


def test_send_now_posts_it_in_his_thread_once(api: TestClient) -> None:
    api.post(f"/shops/{SHOP}/tonight")
    assert api.post(f"/shops/{SHOP}/tonight/send-now").json() == {"sent": 4}
    assert api.post(f"/shops/{SHOP}/tonight/send-now").json() == {"sent": 0}
    thread = api.get(f"/shops/{SHOP}/customers/{PATIL}/thread").json()
    sent = [m for m in thread["messages"] if m["kind"] == "reminder"]
    assert len(sent) == 1 and sent[0]["author"] == "bahi"
    # Sent today, so tomorrow's list shows it as sent, and holds him after.
    out = api.get(f"/shops/{SHOP}/tonight").json()
    patil = next(p for p in out["plans"] if p["display_name"] == "Patil")
    assert (patil["send"], patil["why"]) == (False, "reminded")
    assert patil["reminder"]["status"] == "sent"
    assert out["sending_count"] == 4


def test_only_reminders_whose_hour_has_come_are_sent(api: TestClient) -> None:
    api.post(f"/shops/{SHOP}/tonight")
    # tomorrow's reminders: nobody's hour has come today
    assert api.post(f"/shops/{SHOP}/tonight/send").json() == {"sent": 0}
