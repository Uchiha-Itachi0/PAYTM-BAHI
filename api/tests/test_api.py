"""The loop, over HTTP, against the seeded database.

Every request runs inside a savepoint of a transaction that is rolled back after
the test, so a failed request undoes itself exactly as it does in production
(one transaction per request) and the seed is never changed.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Iterator
from datetime import timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient

from bahi import clock
from bahi.service import app
from bahi.service.deps import connection
from data import contract, db
from data.world import HOME, uid

SHOP = str(uid("shop", HOME))
SHARMA = str(uid("customer", HOME, "sharma"))
SHARMA_PERSON = str(uid("person", "sharma"))
RUKHSANA = str(uid("customer", HOME, "rukhsana"))


@pytest.fixture
def api(tx: db.Conn) -> Iterator[TestClient]:
    def within_savepoint() -> Iterator[db.Conn]:
        with tx.transaction():
            yield tx

    app.dependency_overrides[connection] = within_savepoint
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def join(api: TestClient, name: str = "Kavita") -> tuple[str, dict[str, Any]]:
    person = str(uuid.uuid4())
    r = api.post(f"/join/{SHOP}", json={"person_id": person, "name": name})
    assert r.status_code == 201, r.text
    return person, r.json()


def record(api: TestClient, **body: Any) -> Any:
    return api.post(f"/shops/{SHOP}/entries", json=body)


# ── reading ──────────────────────────────────────────────────────────────────


def test_the_live_book_is_the_contract(api: TestClient, tx: db.Conn) -> None:
    r = api.get(f"/shops/{SHOP}/book")
    assert r.status_code == 200
    assert r.json() == json.loads(contract.SHOP.read_text(encoding="utf-8"))


def test_an_unchanged_book_is_a_304(api: TestClient) -> None:
    first = api.get(f"/shops/{SHOP}/book")
    again = api.get(
        f"/shops/{SHOP}/book", headers={"If-None-Match": first.headers["etag"]}
    )
    assert again.status_code == 304 and again.content == b""


# ── the loop ─────────────────────────────────────────────────────────────────


def test_scan_record_confirm_and_the_book_moves(api: TestClient) -> None:
    person, joined = join(api)
    assert joined["first_time"] is True
    scan = joined["scan_id"]

    waiting = api.get(f"/shops/{SHOP}/counter").json()["waiting"]
    assert [w["display_name"] for w in waiting] == ["Kavita"]

    r = record(api, scan_id=scan, amount_paise=20000, spoken_text="do sau")
    assert r.status_code == 201, r.text
    entry = r.json()
    assert (entry["status"], entry["button"]) == ("recorded", "Yes, I owe ₹200")

    # His phone polls the scan and finds the entry to confirm.
    s = api.get(f"/scans/{scan}").json()
    assert (s["state"], s["entry"]["id"]) == ("recorded", entry["id"])
    assert api.get(f"/shops/{SHOP}/counter").json()["waiting"] == []

    r = api.post(f"/entries/{entry['id']}/confirm", json={"person_id": person})
    assert r.status_code == 200 and r.json()["status"] == "confirmed"

    line = next(
        ln
        for ln in api.get(f"/shops/{SHOP}/book").json()["book"]["lines"]
        if ln["customer_id"] == entry["customer_id"]
    )
    assert (line["balance_paise"], line["chip"]) == (20000, "new")


def test_the_stored_wording_is_the_button_he_saw(api: TestClient, tx: db.Conn) -> None:
    person, joined = join(api)
    entry = record(api, scan_id=joined["scan_id"], amount_paise=12400000).json()
    api.post(f"/entries/{entry['id']}/confirm", json={"person_id": person})
    row = tx.execute(
        "SELECT wording FROM acknowledgments WHERE entry_id = %s", (entry["id"],)
    ).fetchone()
    assert row == (f"{entry['button']} to Ramesh Kirana Store",)
    assert entry["button"] == "Yes, I owe ₹1,24,000"


# ── refusals ─────────────────────────────────────────────────────────────────


def test_a_scan_is_used_once_and_the_loser_leaves_nothing(
    api: TestClient, tx: db.Conn
) -> None:
    _, joined = join(api)
    assert record(api, scan_id=joined["scan_id"], amount_paise=20000).status_code == 201
    second = record(api, scan_id=joined["scan_id"], amount_paise=30000)
    assert second.status_code == 409

    count = tx.execute(
        "SELECT count(*) FROM entries WHERE customer_id = %s", (joined["customer_id"],)
    ).fetchone()
    assert count == (1,)


def test_a_scan_older_than_three_minutes_cannot_be_used(
    api: TestClient, tx: db.Conn
) -> None:
    old = tx.execute(
        "INSERT INTO scans (customer_id, scanned_at) VALUES (%s, %s) RETURNING id::text",
        (SHARMA, clock.now() - timedelta(minutes=4)),
    ).fetchone()
    assert old is not None
    assert api.get(f"/scans/{old[0]}").json()["state"] == "expired"
    assert record(api, scan_id=old[0], amount_paise=20000).status_code == 409


def test_he_can_walk_away(api: TestClient) -> None:
    _, joined = join(api)
    assert api.post(f"/scans/{joined['scan_id']}/leave").status_code == 204
    assert api.get(f"/shops/{SHOP}/counter").json()["waiting"] == []
    assert record(api, scan_id=joined["scan_id"], amount_paise=20000).status_code == 409


def test_nothing_is_recorded_against_an_invitation(api: TestClient) -> None:
    r = record(api, customer_id=RUKHSANA, amount_paise=20000)
    assert r.status_code == 409 and "accepted" in r.json()["detail"]


def test_confirming_twice_is_refused(api: TestClient) -> None:
    person, joined = join(api)
    entry = record(api, scan_id=joined["scan_id"], amount_paise=20000).json()
    url = f"/entries/{entry['id']}/confirm"
    assert api.post(url, json={"person_id": person}).status_code == 200
    assert api.post(url, json={"person_id": person}).status_code == 409


def test_nobody_confirms_an_entry_that_is_not_theirs(api: TestClient) -> None:
    _, joined = join(api)
    entry = record(api, scan_id=joined["scan_id"], amount_paise=20000).json()
    stranger = str(uuid.uuid4())
    r = api.post(f"/entries/{entry['id']}/confirm", json={"person_id": stranger})
    assert r.status_code == 403


def test_a_disputed_entry_cannot_then_be_confirmed(api: TestClient) -> None:
    entry = record(api, customer_id=SHARMA, amount_paise=20000).json()
    r = api.post(
        f"/entries/{entry['id']}/dispute",
        json={"person_id": SHARMA_PERSON, "reason": "Sirf atta liya tha"},
    )
    assert r.json()["status"] == "disputed"
    r = api.post(f"/entries/{entry['id']}/confirm", json={"person_id": SHARMA_PERSON})
    assert r.status_code == 409


def test_an_amount_must_be_more_than_zero(api: TestClient) -> None:
    assert record(api, customer_id=SHARMA, amount_paise=0).status_code == 422


def test_a_first_visit_needs_a_name(api: TestClient) -> None:
    r = api.post(f"/join/{SHOP}", json={"person_id": str(uuid.uuid4())})
    assert r.status_code == 409


def test_an_invited_customer_who_scans_has_said_yes(api: TestClient, tx: db.Conn) -> None:
    person = str(uid("person", "rukhsana"))
    r = api.post(f"/join/{SHOP}", json={"person_id": person})
    assert r.status_code == 201 and r.json()["customer_id"] == RUKHSANA
    assert record(api, scan_id=r.json()["scan_id"], amount_paise=5000).status_code == 201
