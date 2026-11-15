"""The family circle: its rules as plain functions, then the loop over HTTP.

The seed has one circle: Rakesh Sharma, his wife Sunita and his son Rohan, with
his agreed udhaar at Ramesh Kirana and at Salim's on its list.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import psycopg
import pytest
from fastapi.testclient import TestClient

from bahi.domain import circle as rules
from bahi.service import app
from bahi.service.deps import connection
from data import db
from data.directory import ACCOUNTS
from data.world import HOME, uid

SHOP = str(uid("shop", HOME))
SHARMA = str(uid("customer", HOME, "sharma"))
RAKESH = str(uid("person", "sharma"))
SUNITA = str(uid("person", "sunita-sharma"))
ROHAN = str(uid("person", "rohan-sharma"))
KAVITA = str(uid("person", "kavita"))
FAMILY = str(uid("circle", "sharma-family"))
PHONE = {a.person_id: a.phone for a in ACCOUNTS}


# ── the rules ────────────────────────────────────────────────────────────────


def test_the_default_sends_a_new_udhaar_to_the_circle() -> None:
    assert rules.DEFAULT_ON_UDHAAR == "circle"
    assert rules.setting(None) == "circle"
    assert rules.setting("self") == "self"


def test_one_circle_takes_it_and_several_ask_which() -> None:
    assert rules.route(None, ["a"]) == rules.Route("share", "a")
    assert rules.route(None, ["a", "b"]) == rules.Route("choose")
    assert rules.route("self", ["a", "b"]) == rules.Route("keep")
    assert rules.route("circle", []) == rules.Route("none")


def test_a_member_pays_only_what_is_on_the_list() -> None:
    ok = {"payer_is_member": True, "on_the_list": True, "agreed": True}
    assert rules.why_not_pay(**ok, left_paise=200, amount_paise=200) is None
    assert rules.why_not_pay(**ok, left_paise=200, amount_paise=300) is not None
    assert rules.why_not_pay(**ok, left_paise=0, amount_paise=100) is not None
    left_the_circle = {**ok, "on_the_list": False}
    assert rules.why_not_pay(**left_the_circle, left_paise=200, amount_paise=100)
    outsider = {**ok, "payer_is_member": False}
    assert rules.why_not_pay(**outsider, left_paise=200, amount_paise=100)


def test_the_payer_is_recorded_and_never_becomes_the_debtor() -> None:
    assert rules.paid_by("sunita", "rakesh") == "sunita"
    assert rules.paid_by("rakesh", "rakesh") is None


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


def mine(api: TestClient, person: str) -> Any:
    r = api.get(f"/people/{person}/circles")
    assert r.status_code == 200, r.text
    return r.json()


def circle(api: TestClient, circle_id: str, person: str) -> Any:
    r = api.get(f"/circles/{circle_id}", params={"person_id": person})
    assert r.status_code == 200, r.text
    return r.json()


def agreed(api: TestClient, paise: int = 15000) -> str:
    """A new udhaar at Ramesh Kirana that Rakesh says yes to."""
    r = api.post(
        f"/shops/{SHOP}/entries", json={"customer_id": SHARMA, "amount_paise": paise}
    )
    assert r.status_code == 201, r.text
    eid = str(r.json()["id"])
    r = api.post(f"/entries/{eid}/confirm", json={"person_id": RAKESH})
    assert r.status_code == 200, r.text
    return eid


def listed(api: TestClient, circle_id: str, person: str = RAKESH) -> dict[str, Any]:
    return {e["entry_id"]: e for e in circle(api, circle_id, person)["entries"]}


def owed_here(api: TestClient, person: str = RAKESH) -> int:
    shops = api.get(f"/people/{person}/udhaar").json()["shops"]
    return int(next(s for s in shops if s["shop"]["id"] == SHOP)["balance_paise"])


def test_the_seeded_family_sees_one_circle_and_its_list(api: TestClient) -> None:
    for person in (RAKESH, SUNITA, ROHAN):
        m = mine(api, person)
        assert [c["name"] for c in m["circles"]] == ["Sharma family"]
        assert (m["on_udhaar"], m["chosen"]) == ("circle", False)
    c = circle(api, FAMILY, SUNITA)
    assert [p["name"] for p in c["members"]] == [
        "Rakesh Sharma",
        "Sunita Sharma",
        "Rohan Sharma",
    ]
    assert {e["shop"]["name"] for e in c["entries"]} == {
        "Ramesh Kirana Store",
        "Salim Medical",
    }
    assert all(
        e["debtor_name"] == "Rakesh Sharma" and e["state"] == "open" for e in c["entries"]
    )
    assert len(mine(api, RAKESH)["listed"]) == 2


def test_only_a_member_sees_a_circle(api: TestClient) -> None:
    r = api.get(f"/circles/{FAMILY}", params={"person_id": KAVITA})
    assert r.status_code == 403
    assert mine(api, KAVITA)["circles"] == []


def test_a_circle_is_made_from_mobile_numbers(api: TestClient) -> None:
    r = api.post(
        "/circles",
        json={"person_id": SUNITA, "name": "Rao and Sharma", "phones": [PHONE[KAVITA]]},
    )
    assert r.status_code == 201, r.text
    made = r.json()
    assert [m["name"] for m in made["members"]] == ["Sunita Sharma", "Kavita Rao"]
    assert made["members"][0]["made_it"] and made["entries"] == []
    added = [n for n in mine(api, KAVITA)["notices"] if n["kind"] == "added"]
    assert added and "Sunita Sharma added you to Rao and Sharma" in added[0]["body"]
    # A person can be in several circles.
    assert len(mine(api, SUNITA)["circles"]) == 2


def test_a_number_with_no_paytm_account_is_refused(api: TestClient) -> None:
    r = api.post(
        "/circles", json={"person_id": SUNITA, "name": "Nobody", "phones": ["9000000001"]}
    )
    assert r.status_code == 409


def add(api: TestClient, by: str, phone: str, circle_id: str = FAMILY) -> Any:
    body = {"person_id": by, "phone": phone}
    return api.post(f"/circles/{circle_id}/members", json=body)


def test_a_member_adds_someone_by_their_mobile_number(api: TestClient) -> None:
    r = add(api, SUNITA, PHONE[KAVITA])
    assert r.status_code == 200, r.text
    assert [m["name"] for m in r.json()["members"]][-1] == "Kavita Rao"
    # She sees the circle and its list now, and is told who added her.
    assert [c["name"] for c in mine(api, KAVITA)["circles"]] == ["Sharma family"]
    assert circle(api, FAMILY, KAVITA)["entries"]
    added = [n for n in mine(api, KAVITA)["notices"] if n["kind"] == "added"]
    assert added and "Sunita Sharma added you to Sharma family" in added[0]["body"]


def test_someone_already_in_the_circle_is_not_added_twice(api: TestClient) -> None:
    r = add(api, SUNITA, PHONE[ROHAN])
    assert r.status_code == 409
    assert "already in" in r.json()["detail"]
    assert len(circle(api, FAMILY, SUNITA)["members"]) == 3


def test_adding_a_number_with_no_paytm_account_is_refused(api: TestClient) -> None:
    assert add(api, SUNITA, "9000000001").status_code == 409


def test_only_a_member_can_add_someone(api: TestClient) -> None:
    assert add(api, KAVITA, PHONE[KAVITA]).status_code == 403


def test_someone_who_left_can_be_added_back(api: TestClient) -> None:
    r = api.post(f"/circles/{FAMILY}/leave", json={"person_id": ROHAN})
    assert r.status_code == 204
    assert add(api, SUNITA, PHONE[ROHAN]).status_code == 200
    assert [c["name"] for c in mine(api, ROHAN)["circles"]] == ["Sharma family"]


def test_a_new_member_s_udhaar_follows_the_default_setting(api: TestClient) -> None:
    assert add(api, RAKESH, PHONE[KAVITA]).status_code == 200
    m = mine(api, KAVITA)
    assert (m["on_udhaar"], m["chosen"]) == (rules.DEFAULT_ON_UDHAAR, False)


def test_a_circle_holds_at_most_its_limit(api: TestClient, tx: db.Conn) -> None:
    rows = tx.execute(
        "SELECT phone FROM paytm.accounts WHERE person_id <> ALL(%s::uuid[]) "
        "ORDER BY phone LIMIT %s",
        ([RAKESH, SUNITA, ROHAN], rules.MOST_MEMBERS - 2),
    ).fetchall()
    phones = [str(r[0]) for r in rows]
    for phone in phones[:-1]:
        assert add(api, RAKESH, phone).status_code == 200, phone
    assert len(circle(api, FAMILY, RAKESH)["members"]) == rules.MOST_MEMBERS
    r = add(api, RAKESH, phones[-1])
    assert r.status_code == 409 and "at most" in r.json()["detail"]


def test_by_default_a_new_udhaar_goes_to_the_one_circle(api: TestClient) -> None:
    eid = agreed(api)
    on = listed(api, FAMILY)
    assert eid in on and on[eid]["left_paise"] == 15000 and on[eid]["mine"]
    # Rakesh is told; the others are asked, on their own phones.
    assert any(
        n["kind"] == "shared" and n["entry_id"] == eid
        for n in mine(api, RAKESH)["notices"]
    )
    for other in (SUNITA, ROHAN):
        help_ = [n for n in mine(api, other)["notices"] if n["entry_id"] == eid]
        assert [n["kind"] for n in help_] == ["help"]
        assert (
            "Rakesh Sharma has a bill of ₹150 at Ramesh Kirana Store" in help_[0]["body"]
        )


def test_in_several_circles_he_picks_which_one(api: TestClient) -> None:
    r = api.post(
        "/circles", json={"person_id": RAKESH, "name": "Work", "phones": [PHONE[KAVITA]]}
    )
    work = r.json()["id"]
    eid = agreed(api)
    assert eid not in listed(api, FAMILY) and eid not in listed(api, work)
    choose = [n for n in mine(api, RAKESH)["notices"] if n["kind"] == "choose"]
    assert [n["entry_id"] for n in choose] == [eid]

    r = api.post(f"/circles/{work}/share", json={"person_id": RAKESH, "entry_id": eid})
    assert r.status_code == 200, r.text
    assert eid in listed(api, work)
    # The question is answered, and the entry can't be on a second list.
    assert not [n for n in mine(api, RAKESH)["notices"] if n["kind"] == "choose"]
    again = api.post(
        f"/circles/{FAMILY}/share", json={"person_id": RAKESH, "entry_id": eid}
    )
    assert again.status_code == 409


def test_kept_to_himself_it_stays_off_the_list_until_he_adds_it(api: TestClient) -> None:
    r = api.post(f"/people/{RAKESH}/circle-setting", json={"on_udhaar": "self"})
    assert r.status_code == 200 and r.json()["on_udhaar"] == "self" and r.json()["chosen"]
    eid = agreed(api)
    assert eid not in listed(api, FAMILY)
    assert [n["kind"] for n in mine(api, RAKESH)["notices"] if n["entry_id"] == eid] == [
        "kept"
    ]
    r = api.post(f"/circles/{FAMILY}/share", json={"person_id": RAKESH, "entry_id": eid})
    assert r.status_code == 200 and eid in listed(api, FAMILY)


def test_only_the_debtor_puts_an_entry_on_the_list(api: TestClient) -> None:
    r = api.post(f"/people/{RAKESH}/circle-setting", json={"on_udhaar": "self"})
    eid = agreed(api)
    r = api.post(f"/circles/{FAMILY}/share", json={"person_id": SUNITA, "entry_id": eid})
    assert r.status_code == 403


def test_a_member_pays_and_rakesh_stays_the_debtor(api: TestClient, tx: db.Conn) -> None:
    eid = agreed(api, 20000)
    before = owed_here(api)

    r = api.post(
        f"/circles/{FAMILY}/entries/{eid}/pay",
        json={"person_id": SUNITA, "amount_paise": 5000},
    )
    assert r.status_code == 200, r.text
    assert (r.json()["left_paise"], r.json()["debtor_name"]) == (15000, "Rakesh Sharma")

    row = tx.execute(
        "SELECT r.paid_by::text, c.person_id::text FROM repayments r "
        "JOIN entries e ON e.id = r.entry_id JOIN customers c ON c.id = e.customer_id "
        "WHERE r.entry_id = %s",
        (eid,),
    ).fetchone()
    assert row == (SUNITA, RAKESH), "paid by Sunita, still Rakesh's entry"
    assert owed_here(api) == before - 5000
    assert mine(api, SUNITA)["listed"] == [], "Sunita owes nothing for paying"
    paid = [n for n in mine(api, RAKESH)["notices"] if n["kind"] == "paid"]
    assert paid and "Sunita Sharma paid ₹50 of your udhaar" in paid[0]["body"]

    # The rest, by Rohan: paid in full, settled, and both payers shown.
    r = api.post(f"/circles/{FAMILY}/entries/{eid}/pay", json={"person_id": ROHAN})
    assert r.status_code == 200 and r.json()["amount_paise"] == 15000
    e = listed(api, FAMILY, SUNITA)[eid]
    assert e["state"] == "paid" and e["left_paise"] == 0
    assert [p["payer_name"] for p in e["payments"]] == ["Sunita Sharma", "Rohan Sharma"]
    assert api.get(f"/entries/{eid}").json()["status"] == "settled"


def about(api: TestClient, person: str, eid: str) -> list[dict[str, Any]]:
    return [n for n in mine(api, person)["notices"] if n["entry_id"] == eid]


def test_a_paid_bill_stops_asking_the_family_to_pay_it(api: TestClient) -> None:
    """Regression: after a member paid a bill in full, the others' "Pay it for
    them?" note still showed, with the old amount, on every refresh."""
    eid = agreed(api, 10000)
    assert [n["kind"] for n in about(api, ROHAN, eid)] == ["help"]

    # A part payment: the note stays, and asks for what is left, not the bill.
    r = api.post(
        f"/circles/{FAMILY}/entries/{eid}/pay",
        json={"person_id": SUNITA, "amount_paise": 4000},
    )
    assert r.status_code == 200, r.text
    help_ = about(api, ROHAN, eid)
    assert [n["kind"] for n in help_] == ["help"]
    assert "a bill of ₹60 at Ramesh Kirana Store" in help_[0]["body"]
    shared = [n for n in about(api, RAKESH, eid) if n["kind"] == "shared"]
    assert shared and "₹60" in shared[0]["body"]

    # The rest: nobody is asked to pay it any more; Rakesh's "paid" notes stay.
    r = api.post(f"/circles/{FAMILY}/entries/{eid}/pay", json={"person_id": SUNITA})
    assert r.status_code == 200, r.text
    for member in (SUNITA, ROHAN):
        assert about(api, member, eid) == []
    assert [n["kind"] for n in about(api, RAKESH, eid)] == ["paid", "paid"]


def test_a_bill_he_pays_himself_at_the_shop_stops_the_asks(api: TestClient) -> None:
    eid = agreed(api, 10000)
    owed = owed_here(api)
    r = api.post(f"/shops/{SHOP}/pay", json={"person_id": RAKESH, "amount_paise": owed})
    assert r.status_code == 200, r.text
    assert api.get(f"/entries/{eid}").json()["status"] == "settled"
    for member in (RAKESH, SUNITA, ROHAN):
        assert about(api, member, eid) == []


def test_a_bill_taken_off_the_list_stops_the_asks(api: TestClient) -> None:
    r = api.post(f"/people/{RAKESH}/circle-setting", json={"on_udhaar": "self"})
    assert r.status_code == 200
    eid = agreed(api, 10000)
    r = api.post(f"/circles/{FAMILY}/share", json={"person_id": RAKESH, "entry_id": eid})
    assert r.status_code == 200
    r = api.post(f"/circles/{FAMILY}/entries/{eid}/take-back", json={"person_id": RAKESH})
    assert r.status_code == 204
    assert about(api, SUNITA, eid) == []


def test_more_than_is_left_is_refused(api: TestClient) -> None:
    eid = agreed(api, 10000)
    r = api.post(
        f"/circles/{FAMILY}/entries/{eid}/pay",
        json={"person_id": SUNITA, "amount_paise": 10100},
    )
    assert r.status_code == 409


def test_someone_outside_the_circle_cannot_pay(api: TestClient) -> None:
    eid = agreed(api)
    r = api.post(f"/circles/{FAMILY}/entries/{eid}/pay", json={"person_id": KAVITA})
    assert r.status_code == 403


def test_after_he_leaves_only_he_can_pay_his_udhaar(api: TestClient) -> None:
    eid = agreed(api)
    before = owed_here(api)

    assert (
        api.post(f"/circles/{FAMILY}/leave", json={"person_id": RAKESH}).status_code
        == 204
    )
    assert mine(api, RAKESH)["circles"] == [] and mine(api, RAKESH)["listed"] == []
    assert listed(api, FAMILY, SUNITA) == {}, "his entries come off the list"
    assert not [n for n in mine(api, SUNITA)["notices"] if n["entry_id"] == eid]

    r = api.post(f"/circles/{FAMILY}/entries/{eid}/pay", json={"person_id": SUNITA})
    assert r.status_code == 409
    assert owed_here(api) == before, "the debt stays his"
    r = api.post(f"/shops/{SHOP}/pay", json={"person_id": RAKESH, "amount_paise": 15000})
    assert r.status_code == 200, r.text


def test_he_can_take_an_entry_back_off_the_list(api: TestClient) -> None:
    eid = agreed(api)
    r = api.post(f"/circles/{FAMILY}/entries/{eid}/take-back", json={"person_id": RAKESH})
    assert r.status_code == 204
    assert eid not in listed(api, FAMILY)
    r = api.post(f"/circles/{FAMILY}/entries/{eid}/pay", json={"person_id": SUNITA})
    assert r.status_code == 409


def test_the_shop_never_sees_the_circle(api: TestClient) -> None:
    eid = agreed(api)
    api.post(f"/circles/{FAMILY}/entries/{eid}/pay", json={"person_id": SUNITA})
    thread = api.get(f"/shops/{SHOP}/customers/{SHARMA}/thread").text
    for word in ("Sunita", "Sharma family", "circle"):
        assert word not in thread


def test_a_notice_is_put_aside_by_its_own_person(api: TestClient) -> None:
    eid = agreed(api)
    note = next(n for n in mine(api, SUNITA)["notices"] if n["entry_id"] == eid)
    path = f"/circle-notices/{note['id']}/done"
    assert api.post(path, json={"person_id": ROHAN}).status_code == 404
    assert api.post(path, json={"person_id": SUNITA}).status_code == 204
    assert note["id"] not in {n["id"] for n in mine(api, SUNITA)["notices"]}


def test_the_database_refuses_an_entry_nobody_said_yes_to(
    api: TestClient, tx: db.Conn
) -> None:
    r = api.post(
        f"/shops/{SHOP}/entries", json={"customer_id": SHARMA, "amount_paise": 9000}
    )
    waiting = r.json()["id"]
    with pytest.raises(psycopg.errors.RaiseException), tx.transaction():
        tx.execute(
            "INSERT INTO circle_shares (circle_id, entry_id, shared_by) "
            "VALUES (%s, %s, %s)",
            (FAMILY, waiting, RAKESH),
        )
