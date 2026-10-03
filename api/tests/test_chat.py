"""Chat, disputes and corrections (V5), the customer's own book and paying it
(V3), adding someone who can't scan (V6), and what the Soundbox hears (V7).

Over HTTP against the seed, inside a transaction that is rolled back.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from bahi import clock
from bahi.service import app
from bahi.service.deps import connection
from bahi.store import customers
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


def test_his_thread_carries_the_same_history_as_his_book(api: TestClient) -> None:
    """Every entry since he joined BAHI has its card, and every payment its line,
    as the app posts them: the chat and the book tell one story."""
    t = shop_thread(api, SHARMA)
    cards = [m for m in t["messages"] if m["card"]]
    book = api.get(f"/shops/{SHOP}/customers/{SHARMA}").json()
    assert len(cards) == book["pattern"]["entries"] - 1  # not the 2023 paper book
    assert cards[-1]["entry"]["amount_paise"] == 20000  # what he owes, last
    assert all(c["author"] == "bahi" and c["kind"] == "entry" for c in cards)
    paid = [m for m in t["messages"] if m["body"].startswith("Paid ")]
    assert len(paid) == book["pattern"]["payments"]
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
    assert line["card"] is False and "is not the right amount" in line["body"]
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


def test_not_mine_then_the_shop_takes_it_back(api: TestClient) -> None:
    """Anil says the ₹150 isn't his; the shop takes it back. It is kept, claims
    nothing, both sides see it, and he owes nothing for it."""
    entry = anils_entry(api)
    r = api.post(
        f"/entries/{entry['id']}/dispute",
        json={"person_id": ANIL_PERSON, "disputed_as": "not_mine"},
    )
    assert r.status_code == 200, r.text
    t = shop_thread(api, ANIL)
    assert "is not theirs" in t["messages"][-1]["body"]
    assert (t["balance_paise"], t["disputed_paise"]) == (0, 15000)

    r = api.post(f"/shops/{SHOP}/entries/{entry['id']}/remove")
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "removed"
    mine = my_thread(api, ANIL_PERSON)
    card = next(
        m["entry"]
        for m in mine["messages"]
        if m["card"] and m["entry"]["id"] == entry["id"]
    )
    assert card["status"] == "removed" and card["disputed_as"] == "not_mine"
    assert "took back ₹150" in mine["messages"][-1]["body"]
    t = shop_thread(api, ANIL)
    assert (t["balance_paise"], t["waiting_paise"], t["disputed_paise"]) == (0, 0, 0)
    # Taken back once; and nothing paid against can be taken back at all.
    assert api.post(f"/shops/{SHOP}/entries/{entry['id']}/remove").status_code == 409


def test_an_entry_with_a_payment_is_never_taken_back(
    api: TestClient, tx: db.Conn
) -> None:
    from bahi.service import ledger

    cid = customers.add(tx, SHOP, "Naya", clock.now())
    e = ledger.record(tx, SHOP, 10000, clock.now(), customer_id=UUID(cid))
    ledger.pay_cash(tx, cid, 4000, clock.now())
    r = api.post(f"/shops/{SHOP}/entries/{e.id}/remove")
    assert r.status_code == 409 and "already paid" in r.json()["detail"]


def test_the_shop_can_correct_an_entry_nobody_disputed(api: TestClient) -> None:
    """He finds the mistake himself, before Anil has answered."""
    entry = anils_entry(api)
    r = api.post(
        f"/shops/{SHOP}/entries/{entry['id']}/correct", json={"amount_paise": 10000}
    )
    assert r.status_code == 201, r.text
    cards = [m["entry"] for m in shop_thread(api, ANIL)["messages"] if m["card"]]
    assert (cards[-2]["status"], cards[-1]["amount_paise"]) == ("corrected", 10000)


def test_an_entry_paid_against_is_not_corrected(api: TestClient) -> None:
    sharma = [m["entry"] for m in shop_thread(api, SHARMA)["messages"] if m["card"]][-1]
    api.post(
        f"/shops/{SHOP}/pay", json={"person_id": SHARMA_PERSON, "amount_paise": 5000}
    )
    r = api.post(
        f"/shops/{SHOP}/entries/{sharma['id']}/correct", json={"amount_paise": 100}
    )
    assert r.status_code == 409 and "paid" in r.json()["detail"]


def test_a_correction_to_the_same_amount_is_refused(api: TestClient) -> None:
    entry = anils_entry(api)
    r = api.post(
        f"/shops/{SHOP}/entries/{entry['id']}/correct", json={"amount_paise": 15000}
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
    messages = shop_thread(api, KAMLA)["messages"]
    start = next(
        i
        for i, m in enumerate(messages)
        if m["card"] and m["entry"]["status"] == "corrected"
    )
    said = [(m["author"], m["card"]) for m in messages[start : start + 5]]
    assert said == [
        ("bahi", True),  # ₹200 recorded
        ("bahi", False),  # she says it's not right
        ("customer", False),
        ("shop", False),
        ("bahi", True),  # the correction, ₹150
    ]
    after = [m["body"] for m in messages[start + 5 :] if not m["card"]]
    assert after[0].startswith("Paid ")  # then paid, with the rest of that day


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
    body = shop_thread(api, SHARMA)["messages"][-1]["body"]
    assert body == "Paid ₹200 by UPI. Nothing left to pay."
    heard = [(e["kind"], e["amount_paise"]) for e in events(api, start)]
    assert ("paid", 20000) in heard
    # nothing left here to pay
    assert (
        api.post(f"/shops/{SHOP}/pay", json={"person_id": SHARMA_PERSON}).status_code
        == 409
    )


def test_he_can_pay_part_and_the_shop_hears_what_is_left(api: TestClient) -> None:
    start = clock.now().isoformat()
    r = api.post(
        f"/shops/{SHOP}/pay", json={"person_id": SHARMA_PERSON, "amount_paise": 5000}
    )
    assert r.status_code == 200, r.text
    assert (r.json()["amount_paise"], r.json()["left_paise"]) == (5000, 15000)
    t = shop_thread(api, SHARMA)
    assert t["balance_paise"] == 15000
    assert t["messages"][-1]["body"] == "Paid ₹50 by UPI. ₹150 still open."
    card = [m["entry"] for m in t["messages"] if m["card"]][-1]
    assert (card["status"], card["paid_paise"]) == ("confirmed", 5000)
    paid = [e for e in events(api, start) if e["kind"] == "paid"]
    assert [(e["amount_paise"], e["left_paise"]) for e in paid] == [(5000, 15000)]


def test_he_cannot_pay_more_than_he_owes(api: TestClient) -> None:
    r = api.post(
        f"/shops/{SHOP}/pay", json={"person_id": SHARMA_PERSON, "amount_paise": 50000}
    )
    assert r.status_code == 409 and "₹200" in r.json()["detail"]


def test_a_disputed_entry_is_not_paid_until_it_is_agreed(api: TestClient) -> None:
    entry = anils_entry(api)
    api.post(f"/entries/{entry['id']}/dispute", json={"person_id": ANIL_PERSON})
    assert (
        api.post(f"/shops/{SHOP}/pay", json={"person_id": ANIL_PERSON}).status_code == 409
    )


# ── V6 · someone who can't scan ──────────────────────────────────────────────


def test_a_number_finds_the_account_and_is_not_kept(api: TestClient, tx: db.Conn) -> None:
    def find(q: str) -> Any:
        return api.get(f"/shops/{SHOP}/accounts", params={"q": q})

    assert find("+91 98200 11223").json() == {
        "person_id": KAVITA_PERSON,
        "name": "Kavita Rao",
        "named": True,
        "here": None,
    }
    assert find("98765 43210").json()["here"] == "invited"
    # Any other mobile stands for a demo account; Paytm would name it, we can't.
    other = find("90000 12345").json()
    assert (other["named"], other["name"]) == (False, "Paytm account ••2345")
    assert find("12345").status_code == 404, "not a mobile number"
    assert find("nobody@nowhere").status_code == 404
    with tx.cursor() as cur:
        cur.execute(
            "SELECT count(*) FROM information_schema.columns "
            "WHERE table_schema = 'public' AND column_name ~ 'phone|mobile|number'"
        )
        assert cur.fetchone() == (0,)


def test_an_unnamed_account_is_invited_under_the_shops_name(api: TestClient) -> None:
    r = api.post(f"/shops/{SHOP}/customers/invite", json={"query": "90000 12345"})
    assert r.status_code == 409 and "what to call them" in r.json()["detail"]
    r = api.post(
        f"/shops/{SHOP}/customers/invite",
        json={"query": "90000 12345", "display_name": "Shreya", "tag": "Wing C 201"},
    )
    assert (r.json()["display_name"], r.json()["joined"]) == ("Shreya", "invited")


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
    # On her phone for her yes: waiting, not yet in what she owes.
    assert (mine["invites"], mine["total_paise"]) == ([], 0)
    assert mine["shops"][0]["waiting_paise"] == 5000


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


# ── someone kept by name gets a phone ────────────────────────────────────────


def by_name(api: TestClient, name: str = "Shreya") -> str:
    r = api.post(
        f"/shops/{SHOP}/customers", json={"display_name": name, "tag": "Wing C 201"}
    )
    cid = str(r.json()["id"])
    api.post(f"/shops/{SHOP}/entries", json={"amount_paise": 20000, "customer_id": cid})
    return cid


def test_every_customer_is_listed_with_what_they_owe(api: TestClient) -> None:
    everyone = {c["display_name"]: c for c in api.get(f"/shops/{SHOP}/customers").json()}
    assert (everyone["Sharma"]["balance_paise"], everyone["Sharma"]["joined"]) == (
        20000,
        "linked",
    )
    assert everyone["Bablu"]["joined"] == "name_only"
    assert everyone["Chhotu"]["balance_paise"] == 0, "square today, still in the book"


def test_one_customer_shows_their_entries(api: TestClient) -> None:
    c = api.get(f"/shops/{SHOP}/customers/{SHARMA}").json()
    assert (c["balance_paise"], c["day"], c["joined"]) == (20000, 4, "linked")
    assert c["entries"][0]["amount_paise"] == 20000


def test_the_shop_renames_someone_and_their_entries_stay(api: TestClient) -> None:
    cid = by_name(api)
    r = api.post(
        f"/shops/{SHOP}/customers/{cid}",
        json={"display_name": "Shreya Kapoor", "tag": "Room 201, C wing"},
    )
    c = r.json()
    assert (c["display_name"], c["tag"], c["balance_paise"]) == (
        "Shreya Kapoor",
        "Room 201, C wing",
        20000,
    )


def test_a_name_only_customer_is_invited_and_their_history_comes_with_them(
    api: TestClient,
) -> None:
    cid = by_name(api)
    r = api.post(f"/shops/{SHOP}/customers/{cid}/invite", json={"query": "90000 12345"})
    assert r.status_code == 200, r.text
    assert (r.json()["joined"], r.json()["invite_pending"]) == ("name_only", True)

    # Until she says yes, the shop still writes her udhaar by name.
    more = {"amount_paise": 5000, "customer_id": cid}
    assert api.post(f"/shops/{SHOP}/entries", json=more).status_code == 201

    shreya = next(p for p in api.get("/demo/phones").json() if p["name"] == "Shreya")
    assert shreya["state"] == "invited"
    pid = shreya["person_id"]
    mine = api.get(f"/people/{pid}/udhaar").json()
    assert [i["display_name"] for i in mine["invites"]] == ["Shreya"]

    assert (
        api.post(f"/shops/{SHOP}/invite/accept", json={"person_id": pid}).status_code
        == 204
    )
    c = api.get(f"/shops/{SHOP}/customers/{cid}").json()
    # Her history waits on her phone for her yes: not yet in the balance.
    assert (c["joined"], c["invite_pending"], c["balance_paise"]) == (
        "linked",
        False,
        0,
    )
    assert c["waiting_paise"] == 25000
    # Both entries reach her phone as cards, for her own yes.
    cards = [m["entry"] for m in my_thread(api, pid)["messages"] if m["card"]]
    assert [(e["amount_paise"], e["status"]) for e in cards] == [
        (20000, "recorded"),
        (5000, "recorded"),
    ]


def test_scanning_the_qr_is_saying_yes_to_the_invite(api: TestClient) -> None:
    cid = by_name(api)
    api.post(f"/shops/{SHOP}/customers/{cid}/invite", json={"query": "90000 12345"})
    pid = next(p for p in api.get("/demo/phones").json() if p["name"] == "Shreya")[
        "person_id"
    ]
    j = api.post(f"/join/{SHOP}", json={"person_id": pid, "name": "Shreya K"}).json()
    assert j["customer_id"] == cid, "the same row, not a second Shreya"
    assert api.get(f"/shops/{SHOP}/customers/{cid}").json()["joined"] == "linked"


def test_no_to_the_invite_keeps_them_in_the_book_by_name(api: TestClient) -> None:
    cid = by_name(api)
    api.post(f"/shops/{SHOP}/customers/{cid}/invite", json={"query": "90000 12345"})
    pid = next(p for p in api.get("/demo/phones").json() if p["name"] == "Shreya")[
        "person_id"
    ]
    assert (
        api.post(f"/shops/{SHOP}/invite/decline", json={"person_id": pid}).status_code
        == 204
    )
    c = api.get(f"/shops/{SHOP}/customers/{cid}").json()
    assert (c["joined"], c["invite_pending"], c["balance_paise"]) == (
        "name_only",
        False,
        20000,
    )


def test_the_shop_can_take_an_invite_back(api: TestClient) -> None:
    cid = by_name(api)
    api.post(f"/shops/{SHOP}/customers/{cid}/invite", json={"query": "90000 12345"})
    r = api.post(f"/shops/{SHOP}/customers/{cid}/invite/cancel")
    assert r.json()["invite_pending"] is False


def test_an_account_already_in_the_book_is_not_invited_twice(api: TestClient) -> None:
    cid = by_name(api)
    r = api.post(f"/shops/{SHOP}/customers/{cid}/invite", json={"query": "9819019019"})
    assert r.status_code == 409 and "Sharma" in r.json()["detail"]


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


def test_every_customer_with_a_phone_can_be_picked_once(api: TestClient) -> None:
    phones = api.get("/demo/phones").json()
    names = [p["name"] for p in phones]
    # 57 linked and Rukhsana invited at the demo shop, and Kavita and Tushar in no
    # book yet. Sharma is in three books and listed once.
    assert len(phones) == 60 and len({p["person_id"] for p in phones}) == 60
    assert names.count("Sharma") == 1
    sharma = next(p for p in phones if p["name"] == "Sharma")
    assert (sharma["shops"], sharma["tag"]) == (3, "Room 19, B wing")
    assert "Bablu" not in names, "kept by name only: no phone"
    by = {p["name"]: p["state"] for p in phones}
    assert (by["Rukhsana Shaikh"], by["Kavita Rao"], by["Patil"]) == (
        "invited",
        "paytm",
        "linked",
    )
    assert names == sorted(names, key=str.casefold)
