"""Chat, disputes and corrections (V5), the customer's own book and paying it
(V3), adding someone who can't scan (V6), and what the Soundbox hears (V7).

Over HTTP against the seed, inside a transaction that is rolled back.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from bahi import clock
from bahi.service import app
from bahi.service.deps import connection
from data import db
from data.world import HOME, uid

SHOP = str(uid("shop", HOME))
SHARMA = str(uid("customer", HOME, "sharma"))
SHARMA_PERSON = str(uid("person", "sharma"))
ANIL = str(uid("customer", HOME, "anil"))
ANIL_PERSON = str(uid("person", "anil"))
KAMLA = str(uid("customer", HOME, "kamla"))
BABLU = str(uid("customer", HOME, "bablu"))
RUKHSANA_PERSON = str(uid("person", "rukhsana"))
KAVITA_PERSON = str(uid("person", "kavita"))


@pytest.fixture
def api(tx: db.Conn) -> Iterator[TestClient]:
    def within_savepoint() -> Iterator[db.Conn]:
        with tx.transaction():
            yield tx

    app.dependency_overrides[connection] = within_savepoint
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def shop_thread(api: TestClient, customer: str) -> dict[str, Any]:
    r = api.get(f"/shops/{SHOP}/customers/{customer}/thread")
    assert r.status_code == 200, r.text
    return dict(r.json())


def my_thread(api: TestClient, person: str) -> dict[str, Any]:
    r = api.get(f"/people/{person}/shops/{SHOP}/thread")
    assert r.status_code == 200, r.text
    return dict(r.json())


def anils_entry(api: TestClient) -> dict[str, Any]:
    cards = [m for m in shop_thread(api, ANIL)["messages"] if m["card"]]
    return dict(cards[-1]["entry"])


def events(api: TestClient, after: str) -> list[dict[str, Any]]:
    r = api.get(f"/shops/{SHOP}/events", params={"after": after})
    return list(r.json()["events"])


# ── V5 · threads ─────────────────────────────────────────────────────────────


def test_every_entry_he_owes_has_its_card_in_his_thread(api: TestClient) -> None:
    t = shop_thread(api, SHARMA)
    cards = [m for m in t["messages"] if m["card"]]
    assert [c["entry"]["amount_paise"] for c in cards] == [20000]
    assert cards[0]["author"] == "bahi" and cards[0]["kind"] == "entry"
    assert (t["balance_paise"], t["day"]) == (20000, 4)


def test_a_new_entry_posts_its_card_and_it_shows_his_yes(api: TestClient) -> None:
    api.post(f"/shops/{SHOP}/entries", json={"amount_paise": 5000, "customer_id": SHARMA})
    card = [m for m in shop_thread(api, SHARMA)["messages"] if m["card"]][-1]
    assert card["entry"]["status"] == "recorded"
    eid = card["entry"]["id"]
    api.post(f"/entries/{eid}/confirm", json={"person_id": SHARMA_PERSON})
    card = [m for m in shop_thread(api, SHARMA)["messages"] if m["card"]][-1]
    assert card["entry"]["status"] == "confirmed", "the card is the entry as it is now"


def test_the_inbox_is_the_latest_first_and_counts_what_is_unread(
    api: TestClient,
) -> None:
    before = api.get(f"/shops/{SHOP}/inbox").json()
    assert before["unread"] == 0
    r = api.post(
        f"/shops/{SHOP}/thread", json={"person_id": ANIL_PERSON, "text": "Bhaiya 150?"}
    )
    assert r.status_code == 201, r.text
    after = api.get(f"/shops/{SHOP}/inbox").json()
    top = after["rows"][0]
    assert (top["display_name"], top["author"], top["unread"]) == ("Anil", "customer", 1)
    assert top["needs_reply"] is True and after["unread"] == 1
    api.post(f"/shops/{SHOP}/inbox/read")
    assert api.get(f"/shops/{SHOP}/inbox").json()["unread"] == 0


def test_the_shopkeeper_replies_in_words(api: TestClient) -> None:
    r = api.post(
        f"/shops/{SHOP}/customers/{ANIL}/thread", json={"text": "Haan Anil, 150."}
    )
    assert r.status_code == 201, r.text
    last = r.json()["messages"][-1]
    assert (last["author"], last["kind"], last["body"]) == (
        "shop",
        "text",
        "Haan Anil, 150.",
    )
    assert my_thread(api, ANIL_PERSON)["messages"][-1]["body"] == "Haan Anil, 150."


def test_nothing_is_sent_to_someone_kept_by_name(api: TestClient) -> None:
    r = api.post(f"/shops/{SHOP}/customers/{BABLU}/thread", json={"text": "Hello"})
    assert r.status_code == 409


def test_nobody_reads_a_thread_that_is_not_theirs(api: TestClient) -> None:
    stranger = str(uid("person", "nobody"))
    assert api.get(f"/people/{stranger}/shops/{SHOP}/thread").status_code == 404


def test_offline_the_munshi_suggests_nothing(api: TestClient) -> None:
    api.post(f"/shops/{SHOP}/thread", json={"person_id": ANIL_PERSON, "text": "150?"})
    r = api.post(f"/shops/{SHOP}/customers/{ANIL}/thread/suggest")
    assert r.json() == {"replies": []}


# ── V5 · a dispute, and its correction ───────────────────────────────────────


def test_that_is_not_right_then_a_correction_he_confirms(api: TestClient) -> None:
    start = clock.now().isoformat()
    entry = anils_entry(api)
    r = api.post(
        f"/entries/{entry['id']}/dispute",
        json={"person_id": ANIL_PERSON, "reason": "Sirf 100 ka liya tha."},
    )
    assert r.json()["status"] == "disputed"

    t = shop_thread(api, ANIL)
    line, reason = t["messages"][-2:]
    assert line["card"] is False and "is not right" in line["body"]
    assert (reason["author"], reason["body"]) == ("customer", "Sirf 100 ka liya tha.")
    assert api.get(f"/shops/{SHOP}/inbox").json()["rows"][0]["needs_reply"] is True
    assert "disputed" in [e["kind"] for e in events(api, start)]

    r = api.post(
        f"/shops/{SHOP}/entries/{entry['id']}/correct", json={"amount_paise": 10000}
    )
    assert r.status_code == 201, r.text
    fixed = r.json()
    assert (fixed["amount_paise"], fixed["corrects_entry_id"]) == (10000, entry["id"])

    cards = [m["entry"] for m in my_thread(api, ANIL_PERSON)["messages"] if m["card"]]
    old, new = cards[-2], cards[-1]
    assert old["status"] == "corrected"
    assert (new["status"], new["corrects_amount_paise"], new["button"]) == (
        "recorded",
        15000,
        "Yes, I owe ₹100",
    )
    r = api.post(f"/entries/{new['id']}/confirm", json={"person_id": ANIL_PERSON})
    assert r.json()["status"] == "confirmed"
    assert shop_thread(api, ANIL)["balance_paise"] == 10000


def test_only_a_disputed_entry_can_be_corrected(api: TestClient) -> None:
    entry = anils_entry(api)
    r = api.post(
        f"/shops/{SHOP}/entries/{entry['id']}/correct", json={"amount_paise": 100}
    )
    assert r.status_code == 409


def test_another_shop_cannot_correct_this_shops_entry(api: TestClient) -> None:
    entry = anils_entry(api)
    api.post(f"/entries/{entry['id']}/dispute", json={"person_id": ANIL_PERSON})
    other = str(uid("shop", "salim"))
    r = api.post(
        f"/shops/{other}/entries/{entry['id']}/correct", json={"amount_paise": 100}
    )
    assert r.status_code == 404


def test_kamlas_august_dispute_reads_as_it_happened(api: TestClient) -> None:
    said = [(m["author"], m["card"]) for m in shop_thread(api, KAMLA)["messages"]][:6]
    assert said == [
        ("bahi", True),  # ₹200 recorded
        ("bahi", False),  # she says it's not right
        ("customer", False),
        ("shop", False),
        ("bahi", True),  # the correction, ₹150
        ("bahi", False),  # paid
    ]


# ── V3 · his own book, across shops, and paying it ───────────────────────────


def test_sharma_owes_across_three_shops(api: TestClient) -> None:
    mine = api.get(f"/people/{SHARMA_PERSON}/udhaar").json()
    assert mine["total_paise"] == 20000 + 69000 + 35000
    by_shop = {s["shop"]["name"]: s for s in mine["shops"]}
    assert set(by_shop) == {"Ramesh Kirana Store", "Salim Medical", "Gupta Dairy"}
    ramesh = by_shop["Ramesh Kirana Store"]
    expired = [e for e in ramesh["entries"] if e["expired"]]
    assert [e["amount_paise"] for e in expired] == [18000], "kept, struck through"


def test_paying_settles_what_he_owes_here_and_the_shop_hears_it(
    api: TestClient,
) -> None:
    start = clock.now().isoformat()
    r = api.post(f"/shops/{SHOP}/pay", json={"person_id": SHARMA_PERSON})
    assert r.status_code == 200, r.text
    paid = r.json()
    assert paid["amount_paise"] == 20000
    assert {s["shop"]["name"] for s in paid["elsewhere"]} == {
        "Salim Medical",
        "Gupta Dairy",
    }
    assert shop_thread(api, SHARMA)["balance_paise"] == 0
    assert shop_thread(api, SHARMA)["messages"][-1]["body"] == "Paid ₹200 by UPI."
    heard = [(e["kind"], e["amount_paise"]) for e in events(api, start)]
    assert ("paid", 20000) in heard
    # nothing left here to pay
    assert (
        api.post(f"/shops/{SHOP}/pay", json={"person_id": SHARMA_PERSON}).status_code
        == 409
    )


def test_a_disputed_entry_is_not_paid_until_it_is_agreed(api: TestClient) -> None:
    entry = anils_entry(api)
    api.post(f"/entries/{entry['id']}/dispute", json={"person_id": ANIL_PERSON})
    assert (
        api.post(f"/shops/{SHOP}/pay", json={"person_id": ANIL_PERSON}).status_code == 409
    )


# ── V6 · someone who can't scan ──────────────────────────────────────────────


def test_a_number_finds_the_account_and_is_not_kept(api: TestClient, tx: db.Conn) -> None:
    r = api.get(f"/shops/{SHOP}/accounts", params={"q": "+91 98200 11223"})
    assert r.json() == {"person_id": KAVITA_PERSON, "name": "Kavita Rao", "here": None}
    assert api.get(f"/shops/{SHOP}/accounts", params={"q": "98765 43210"}).json()[
        "here"
    ] == ("invited")
    assert (
        api.get(f"/shops/{SHOP}/accounts", params={"q": "90000 00000"}).status_code == 404
    )
    with tx.cursor() as cur:
        cur.execute(
            "SELECT count(*) FROM information_schema.columns "
            "WHERE table_schema = 'public' AND column_name ~ 'phone|mobile|number'"
        )
        assert cur.fetchone() == (0,)


def test_an_invite_records_nothing_until_she_says_yes(api: TestClient) -> None:
    r = api.post(f"/shops/{SHOP}/customers/invite", json={"query": "kavita.rao@ptaxis"})
    assert r.status_code == 201, r.text
    kavita = r.json()
    assert kavita["joined"] == "invited"
    record = {"amount_paise": 5000, "customer_id": kavita["id"]}
    assert api.post(f"/shops/{SHOP}/entries", json=record).status_code == 409

    mine = api.get(f"/people/{KAVITA_PERSON}/udhaar").json()
    assert [i["shop"]["name"] for i in mine["invites"]] == ["Ramesh Kirana Store"]
    accept = api.post(f"/shops/{SHOP}/invite/accept", json={"person_id": KAVITA_PERSON})
    assert accept.status_code == 204
    assert api.post(f"/shops/{SHOP}/entries", json=record).status_code == 201
    mine = api.get(f"/people/{KAVITA_PERSON}/udhaar").json()
    assert (mine["invites"], mine["total_paise"]) == ([], 5000)


def test_inviting_twice_is_refused(api: TestClient) -> None:
    r = api.post(f"/shops/{SHOP}/customers/invite", json={"query": "9876543210"})
    assert r.status_code == 409 and "waiting" in r.json()["detail"]


def test_saying_no_to_an_invite_takes_it_away(api: TestClient) -> None:
    r = api.post(f"/shops/{SHOP}/invite/decline", json={"person_id": RUKHSANA_PERSON})
    assert r.status_code == 204
    assert api.get(f"/people/{RUKHSANA_PERSON}/udhaar").json()["invites"] == []


def test_no_phone_is_kept_by_name_only(api: TestClient) -> None:
    r = api.post(
        f"/shops/{SHOP}/customers", json={"display_name": "Ganpat", "tag": "Chawl 7"}
    )
    assert r.status_code == 201, r.text
    assert (r.json()["joined"], r.json()["tag"]) == ("name_only", "Chawl 7")
    record = {"amount_paise": 5000, "customer_id": r.json()["id"]}
    assert api.post(f"/shops/{SHOP}/entries", json=record).status_code == 201
    # no phone, so no thread: nobody would ever read it
    names = [
        row["display_name"] for row in api.get(f"/shops/{SHOP}/inbox").json()["rows"]
    ]
    assert "Ganpat" not in names


# ── V7 · what the Soundbox hears ─────────────────────────────────────────────


def test_the_first_ask_only_says_what_time_it_is(api: TestClient) -> None:
    out = api.get(f"/shops/{SHOP}/events").json()
    assert out["events"] == [] and out["now"]


def test_a_scan_a_yes_and_a_message_are_heard_in_order(api: TestClient) -> None:
    start = clock.now().isoformat()
    j = api.post(f"/join/{SHOP}", json={"person_id": SHARMA_PERSON}).json()
    e = api.post(
        f"/shops/{SHOP}/entries", json={"amount_paise": 5000, "scan_id": j["scan_id"]}
    )
    api.post(f"/entries/{e.json()['id']}/confirm", json={"person_id": SHARMA_PERSON})
    api.post(f"/shops/{SHOP}/thread", json={"person_id": SHARMA_PERSON, "text": "Thanks"})
    heard = [(x["kind"], x["display_name"]) for x in events(api, start)]
    assert heard == [
        ("scanned", "Sharma"),
        ("confirmed", "Sharma"),
        ("message", "Sharma"),
    ]
