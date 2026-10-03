"""M3 · Memory: what was said can hold a reminder, and nothing more.

Tonight's rule by hand; notes, Forget and shops kept apart over HTTP; and the
background worker with Sarvam and Cognee faked, so no test leaves the machine.
What memory may never do is tested as firmly as what it does: send a reminder,
reach another shop, or show the shopkeeper's notes to the customer.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient

from bahi import clock
from bahi.domain.book import Customer, Entry
from bahi.domain.tonight import Wait, tonight
from bahi.memory import worker
from bahi.munshi import writer
from bahi.service import app
from bahi.service.deps import connection
from bahi.store import memories, threads
from data import db
from data.world import HOME, uid

SHOP = str(uid("shop", HOME))
PATIL = str(uid("customer", HOME, "patil"))
PATIL_PERSON = str(uid("person", "patil"))
SALIM = str(uid("shop", "salim"))
SHARMA_AT_SALIM = str(uid("customer", "salim", "sharma"))
TODAY = date(2026, 10, 3)
TOMORROW = TODAY + timedelta(days=1)


# ── Tonight, by hand ─────────────────────────────────────────────────────────


def raju(status: str = "confirmed") -> Customer:
    """Past his longest gap: without a wait, he is sent one."""
    paid = [45, 35, 25, 15]
    return Customer(
        id="raju",
        display_name="Raju",
        tag=None,
        joined="linked",
        entries=(Entry("e", 100_00, 0, status, TODAY - timedelta(days=1), None),),
        paid_on=tuple(TODAY - timedelta(days=d) for d in paid),
    )


def plan(waits: dict[str, Wait]) -> tuple[bool, str, Wait | None]:
    (p,) = tonight([raju()], TODAY, {}, {}, waits).plans
    return p.send, p.why, p.wait


def test_his_promise_holds_the_reminder_until_the_day_he_named() -> None:
    promise = Wait(TOMORROW, "customer", "कल दे दूँगा")
    assert plan({"raju": promise}) == (False, "promised", promise)


def test_the_shopkeepers_note_holds_it_too() -> None:
    note = Wait(TODAY + timedelta(days=7), "shop", "salary on the 10th")
    assert plan({"raju": note}) == (False, "asked_to_wait", note)


def test_once_the_day_has_passed_the_reminder_goes() -> None:
    assert plan({"raju": Wait(TODAY, "customer", "aaj dunga")}) == (
        True,
        "past_longest_gap",
        None,
    )


def test_a_wait_never_sends_and_never_replaces_a_hold() -> None:
    wait = Wait(TOMORROW, "shop", "wait")
    (p,) = tonight([raju("disputed")], TODAY, {}, {}, {"raju": wait}).plans
    assert (p.send, p.why, p.wait) == (False, "disputed", None)


# ── over HTTP ────────────────────────────────────────────────────────────────


@pytest.fixture
def api(tx: db.Conn) -> Iterator[TestClient]:
    def within_savepoint() -> Iterator[db.Conn]:
        with tx.transaction():
            yield tx

    app.dependency_overrides[connection] = within_savepoint
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def note(api: TestClient, body: str, until: date | None = None, **kw: Any) -> Any:
    shop = kw.get("shop", SHOP)
    customer = kw.get("customer", PATIL)
    return api.post(
        f"/shops/{shop}/customers/{customer}/memories",
        json={"body": body, "until": until.isoformat() if until else None},
    )


def test_a_note_shows_on_his_page_and_holds_tonight(api: TestClient) -> None:
    before = api.get(f"/shops/{SHOP}/tonight").json()
    assert "Patil" in {p["display_name"] for p in before["plans"] if p["send"]}

    r = note(api, "Pension 10 tarikh ko aati hai", date(2026, 10, 10))
    assert r.status_code == 201, r.text
    (m,) = r.json()["memories"]
    assert (m["kind"], m["said_by"], m["until"]) == ("note", "shop", "2026-10-10")

    after = api.get(f"/shops/{SHOP}/tonight").json()
    patil = next(p for p in after["plans"] if p["display_name"] == "Patil")
    assert (patil["send"], patil["why"]) == (False, "asked_to_wait")
    assert patil["wait"]["body"] == "Pension 10 tarikh ko aati hai"
    assert after["sending_count"] == before["sending_count"] - 1


def test_forget_takes_it_off_his_page_and_off_tonight(api: TestClient) -> None:
    m = note(api, "wait", date(2026, 10, 10)).json()["memories"][0]
    assert api.delete(f"/shops/{SHOP}/memories/{m['id']}").status_code == 204
    assert api.get(f"/shops/{SHOP}/customers/{PATIL}").json()["memories"] == []
    tonight_ = api.get(f"/shops/{SHOP}/tonight").json()
    patil = next(p for p in tonight_["plans"] if p["display_name"] == "Patil")
    assert patil["send"]
    assert api.delete(f"/shops/{SHOP}/memories/{m['id']}").status_code == 404


@pytest.mark.parametrize(
    ("until", "why"),
    [(TODAY - timedelta(days=1), "passed"), (TODAY + timedelta(days=91), "three")],
)
def test_a_wait_is_from_today_to_three_months(
    api: TestClient, until: date, why: str
) -> None:
    r = note(api, "wait", until)
    assert r.status_code == 409 and why in r.json()["detail"]


def test_another_shops_customer_and_memory_are_out_of_reach(api: TestClient) -> None:
    assert note(api, "x", customer=SHARMA_AT_SALIM).status_code == 404
    theirs = note(api, "Salim's own note", shop=SALIM, customer=SHARMA_AT_SALIM)
    assert theirs.status_code == 201
    mid = theirs.json()["memories"][0]["id"]
    assert api.delete(f"/shops/{SHOP}/memories/{mid}").status_code == 404


def test_the_customer_never_sees_the_shopkeepers_notes(api: TestClient) -> None:
    note(api, "Nobody tells Patil this")
    mine = api.get(f"/people/{PATIL_PERSON}/udhaar").text
    thread = api.get(f"/people/{PATIL_PERSON}/shops/{SHOP}/thread").text
    assert "Nobody tells Patil this" not in mine + thread


# ── the worker, with Sarvam and Cognee faked ────────────────────────────────


class FakeMemory:
    def __init__(self) -> None:
        self.kept: dict[str, tuple[str, str]] = {}
        self.forgotten: list[str] = []

    def remember(self, shop_id: str, text: str, customer_id: str) -> str | None:
        cid = f"00000000-0000-4000-8000-{len(self.kept):012d}"
        self.kept[cid] = (shop_id, text)
        return cid

    def recall(self, shop_id: str, question: str) -> str:
        return "\n".join(t for s, t in self.kept.values() if s == shop_id)

    def forget(self, shop_id: str, cognee_id: str) -> None:
        self.forgotten.append(cognee_id)


def patil_writes(tx: db.Conn, text: str) -> str:
    return threads.post(tx, PATIL, "customer", "text", text, clock.now()).id


def test_his_promise_in_chat_is_read_and_remembered(
    tx: db.Conn, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        writer, "promise", lambda text, today: date(2026, 10, 5) if "5" in text else None
    )
    promised = patil_writes(tx, "5 तारीख को दे दूँगा")
    chatted = patil_writes(tx, "ठीक है भाई")
    assert worker.read_chat(tx, clock.now()) >= 2
    (m,) = memories.of_customer(tx, PATIL)
    assert (m.kind, m.said_by, m.until, m.message_id) == (
        "promise",
        "customer",
        date(2026, 10, 5),
        promised,
    )
    assert m.body == "5 तारीख को दे दूँगा"  # his own words, as he wrote them
    assert worker.read_chat(tx, clock.now()) == 0  # each message read once
    assert chatted  # read, and nothing kept from it


def test_new_memories_go_to_cognee_and_forgotten_ones_come_out(tx: db.Conn) -> None:
    fake = FakeMemory()
    now = clock.now()
    kept = memories.add(tx, SHOP, PATIL, "note", "pays at the auto stand", "shop", now)
    assert kept is not None
    assert worker.store(tx, fake, now) >= 1
    (cognee_id, (shop, text)) = next(iter(fake.kept.items()))
    assert shop == SHOP and "Patil" in text and "pays at the auto stand" in text
    assert memories.of_customer(tx, PATIL)[0].cognee_id == cognee_id

    memories.forget(tx, kept.id, SHOP, now)
    assert worker.unstore(tx, fake) == 1
    assert fake.forgotten == [cognee_id]
    assert worker.unstore(tx, fake) == 0


def test_a_promise_further_than_three_months_is_not_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from bahi.voice import sarvam

    monkeypatch.setenv("SARVAM_OFFLINE", "0")
    monkeypatch.setenv("SARVAM_API_KEY", "not-a-real-key")
    said: dict[str, Any] = {}
    monkeypatch.setattr(sarvam, "chat_json", lambda *a, **k: said)
    said.update(promise=True, pay_by="2026-10-05")
    assert writer.promise("5 ko dunga", TODAY) == date(2026, 10, 5)
    said.update(pay_by="2027-06-01")
    assert writer.promise("june mein", TODAY) is None
    said.update(pay_by="2026-09-01")
    assert writer.promise("pichle mahine", TODAY) is None
    said.update(promise=False, pay_by="2026-10-05")
    assert writer.promise("haan theek hai", TODAY) is None


def test_what_cognee_is_given_says_who_and_until_when(tx: db.Conn) -> None:
    now = datetime(2026, 10, 1, 11, 0, tzinfo=clock.IST)
    m = memories.add(
        tx, SHOP, PATIL, "promise", "5 को दूँगा", "customer", now, until=date(2026, 10, 5)
    )
    assert m is not None
    text = worker.text_of(m)
    assert "Patil / पाटिल (Auto stand)" in text and "01 Oct 2026" in text
    assert "05 Oct 2026" in text and "5 को दूँगा" in text
