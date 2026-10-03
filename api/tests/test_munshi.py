"""The munshi, with Sarvam replaced by a script.

Each test scripts what the model says: which tools it calls, with what, and what
it replies. The tools, the checks, the drafts and the ledger are the real ones,
on the seeded database, rolled back after each test. So these hold the code to
its rules whatever a model does: it cannot write an entry, cannot put someone it
never looked up on a card, cannot approve its own card, and a double tap is one
entry.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from datetime import timedelta
from typing import Any
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from bahi import clock
from bahi.domain.find import find
from bahi.domain.who import Person
from bahi.service import app, ledger
from bahi.service.deps import connection
from bahi.service.errors import Conflict
from bahi.service.routes import munshi as route
from bahi.store import customers, entries
from data import db
from data.world import HOME, uid

SHOP = str(uid("shop", HOME))
SHARMA = str(uid("customer", HOME, "sharma"))

#: One scripted model message: a tool call (its args may be worked out from the
#: last tool result), or a reply.
Step = dict[str, Any]


def tool(
    name: str, args: dict[str, Any] | Callable[[Any], dict[str, Any]] | None = None
) -> Step:
    return {"tool": name, "args": args or {}}


def reply(text: str) -> Step:
    return {"reply": text}


def first_found(result: Any) -> str:
    return str(result["customers"][0]["id"])


class Script:
    """The model, played from a list. Each call takes the next step."""

    def __init__(self) -> None:
        self.steps: list[Step] = []
        self.calls = 0

    def then(self, *steps: Step) -> Script:
        self.steps.extend(steps)
        return self

    def __call__(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> dict[str, Any]:
        step = self.steps.pop(0)
        self.calls += 1
        if "reply" in step:
            return {"role": "assistant", "content": step["reply"]}
        last = next(
            (json.loads(m["content"]) for m in reversed(messages) if m["role"] == "tool"),
            None,
        )
        args = step["args"](last) if callable(step["args"]) else step["args"]
        return {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": f"call-{self.calls}",
                    "type": "function",
                    "function": {"name": step["tool"], "arguments": json.dumps(args)},
                }
            ],
        }


@pytest.fixture
def model(monkeypatch: pytest.MonkeyPatch) -> Script:
    script = Script()
    monkeypatch.setattr(route, "chat", lambda: script)
    return script


@pytest.fixture
def api(tx: db.Conn) -> Iterator[TestClient]:
    def within_savepoint() -> Iterator[db.Conn]:
        with tx.transaction():
            yield tx

    app.dependency_overrides[connection] = within_savepoint
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def say(api: TestClient, text: str, conversation: str | None = None) -> dict[str, Any]:
    r = api.post(
        f"/shops/{SHOP}/munshi", json={"text": text, "conversation_id": conversation}
    )
    assert r.status_code == 200, r.text
    return dict(r.json())


def tap(api: TestClient, out: dict[str, Any], answer: str = "yes") -> dict[str, Any]:
    card = out["card"]
    r = api.post(
        f"/shops/{SHOP}/munshi/{out['conversation_id']}/cards/{card['draft_id']}/{answer}"
    )
    assert r.status_code == 200, r.text
    return dict(r.json())


def sharmas_entries(tx: db.Conn) -> list[int]:
    return [e.amount_paise for e in entries.of_customer(tx, SHARMA)]


def shows_sharma(amount: int, kind: str = "udhaar") -> list[Step]:
    return [
        tool("find_customer", {"name": "शर्मा"}),
        tool(
            "propose_entry",
            lambda found: {
                "customer_id": first_found(found),
                "kind": kind,
                "amount_rupees": amount,
            },
        ),
        reply("शर्मा, रूम 19, बी विंग, दो सौ रुपये उधार, पक्का?"),
    ]


# ── the loop ─────────────────────────────────────────────────────────────────


def test_a_card_then_a_tap_writes_the_entry_and_says_it_was_sent(
    api: TestClient, model: Script, tx: db.Conn
) -> None:
    before = sharmas_entries(tx)
    model.then(*shows_sharma(200))
    out = say(api, "शर्मा जी को दो सौ लिख दो")
    card = out["card"]
    assert card["display_name"] == "Sharma"
    assert card["amount_paise"] == 200_00
    assert card["status"] == "shown" and card["reasons"] == []
    assert card["spoken_text"] == "शर्मा जी को दो सौ लिख दो"
    assert out["reply"].endswith("पक्का?")
    assert out["say_url"].endswith(".wav")
    assert sharmas_entries(tx) == before, "a card is not an entry"

    model.then(reply("लिख दिया और शर्मा जी के फोन पर भेज दिया।"))
    done = tap(api, out)
    assert done["finished"] is True
    assert done["card"]["status"] == "saved" and done["card"]["on_bahi"] is True
    assert sharmas_entries(tx) == [*before, 200_00]
    # the munshi was told what code did, and from that said it was sent
    assert "भेज" in done["reply"]


def test_a_spoken_yes_goes_through_confirm_entry(
    api: TestClient, model: Script, tx: db.Conn
) -> None:
    before = sharmas_entries(tx)
    model.then(*shows_sharma(200))
    out = say(api, "शर्मा जी को दो सौ")
    model.then(tool("confirm_entry"), reply("लिख दिया।"))
    done = say(api, "हाँ", out["conversation_id"])
    assert done["finished"] is True and done["card"]["status"] == "saved"
    assert sharmas_entries(tx) == [*before, 200_00]


def test_tapping_yes_twice_writes_one_entry(
    api: TestClient, model: Script, tx: db.Conn
) -> None:
    before = sharmas_entries(tx)
    model.then(*shows_sharma(200))
    out = say(api, "शर्मा जी को दो सौ")
    model.then(reply("लिख दिया।"), reply("पहले ही लिख दिया है।"))
    tap(api, out)
    tap(api, out)
    assert sharmas_entries(tx) == [*before, 200_00]


def test_no_takes_the_card_away_and_writes_nothing(
    api: TestClient, model: Script, tx: db.Conn
) -> None:
    before = sharmas_entries(tx)
    model.then(*shows_sharma(200))
    out = say(api, "शर्मा जी को दो सौ")
    model.then(reply("ठीक है, नहीं लिखा।"))
    done = tap(api, out, "no")
    assert done["card"]["status"] == "cancelled" and done["finished"] is True
    assert sharmas_entries(tx) == before


# ── what the munshi cannot do ────────────────────────────────────────────────


def test_it_cannot_put_someone_it_never_looked_up_on_a_card(
    api: TestClient, model: Script
) -> None:
    model.then(
        tool(
            "propose_entry",
            {
                "customer_id": SHARMA.replace("-", "")[:6],
                "kind": "udhaar",
                "amount_rupees": 200,
            },
        ),
        reply("पहले ढूँढता हूँ।"),
    )
    out = say(api, "शर्मा जी को दो सौ")
    assert out["card"] is None


def test_it_cannot_approve_its_own_card_in_the_same_breath(
    api: TestClient, model: Script, tx: db.Conn
) -> None:
    before = sharmas_entries(tx)
    model.then(*shows_sharma(200)[:2], tool("confirm_entry"), reply("पक्का?"))
    out = say(api, "शर्मा जी को दो सौ")
    assert out["card"]["status"] == "shown"
    assert sharmas_entries(tx) == before


def test_a_large_amount_waits_for_a_clear_yes(api: TestClient, model: Script) -> None:
    model.then(*shows_sharma(8000))
    out = say(api, "शर्मा जी को आठ हज़ार")
    assert "large" in out["card"]["reasons"]


def test_money_back_cannot_be_more_than_he_owes(api: TestClient, model: Script) -> None:
    model.then(*shows_sharma(9_99_999, "paid_back")[:2], reply("इतना बाकी नहीं है।"))
    out = say(api, "शर्मा जी ने बहुत पैसे दिए")
    assert out["card"] is None


def test_without_sarvam_the_munshi_says_so(api: TestClient) -> None:
    r = api.post(f"/shops/{SHOP}/munshi", json={"text": "शर्मा जी को दो सौ"})
    assert r.status_code == 503
    assert "by hand" in r.json()["detail"]


# ── someone new, and tomorrow's list ─────────────────────────────────────────


def added(tx: db.Conn, name: str) -> list[customers.CustomerRef]:
    return [c for c in customers.of_shop(tx, SHOP) if c.display_name == name]


def test_someone_not_in_the_book_is_added_by_name_on_his_yes(
    api: TestClient, model: Script, tx: db.Conn
) -> None:
    model.then(
        tool("find_customer", {"name": "रमेश"}),
        reply("रमेश बुक में नहीं हैं। नया ग्राहक जोड़ूँ?"),
    )
    out = say(api, "रमेश को पाँच सौ")
    model.then(
        tool(
            "propose_new_customer",
            {"name": "Ramesh", "description": "Chawl 7", "amount_rupees": 500},
        ),
        reply("रमेश, चॉल 7, नए ग्राहक, पाँच सौ उधार, पक्का?"),
    )
    out = say(api, "हाँ, चॉल सात वाले", out["conversation_id"])
    card = out["card"]
    assert (card["new"], card["customer_id"], card["display_name"]) == (
        True,
        None,
        "Ramesh",
    )
    assert card["reasons"] == ["new_customer"], "someone new always waits for a yes"
    assert added(tx, "Ramesh") == [], "a card adds nobody"

    model.then(reply("रमेश को जोड़ दिया और पाँच सौ लिख दिया।"))
    done = tap(api, out)
    assert done["card"]["status"] == "saved" and done["card"]["customer_id"]
    (ramesh,) = added(tx, "Ramesh")
    assert (ramesh.joined, ramesh.tag) == ("name_only", "Chawl 7")
    assert [e.amount_paise for e in entries.of_customer(tx, ramesh.id)] == [500_00]


def test_a_card_can_only_add_someone(api: TestClient, model: Script, tx: db.Conn) -> None:
    model.then(
        tool("find_customer", {"name": "गणपत"}),
        tool("propose_new_customer", {"name": "Ganpat"}),
        reply("गणपत को नए ग्राहक की तरह जोड़ूँ, पक्का?"),
    )
    out = say(api, "नया ग्राहक जोड़ो, गणपत")
    assert (out["card"]["kind"], out["card"]["amount_paise"]) == ("customer", None)
    model.then(reply("जोड़ दिया।"))
    tap(api, out)
    (ganpat,) = added(tx, "Ganpat")
    assert entries.of_customer(tx, ganpat.id) == []


def test_nobody_is_added_before_a_search(api: TestClient, model: Script) -> None:
    model.then(
        tool("propose_new_customer", {"name": "Ramesh", "amount_rupees": 500}),
        reply("पहले ढूँढता हूँ।"),
    )
    assert say(api, "रमेश को पाँच सौ")["card"] is None


def test_a_name_already_in_the_book_is_asked_about_not_doubled(
    api: TestClient, model: Script, tx: db.Conn
) -> None:
    model.then(
        tool("find_customer", {"name": "Sharma", "description": "Chawl 9"}),
        tool("propose_new_customer", {"name": "Sharma", "amount_rupees": 200}),
        reply("बुक में एक शर्मा हैं, रूम 19, बी विंग। वही हैं?"),
    )
    out = say(api, "चॉल नौ वाले शर्मा को दो सौ")
    assert out["card"] is None
    assert len(added(tx, "Sharma")) == 1


def test_tomorrows_list_is_read_from_the_code_not_made_up(
    api: TestClient, model: Script
) -> None:
    seen: dict[str, Any] = {}

    def remember(result: Any) -> dict[str, Any]:
        seen.update(result)
        return {}

    model.then(tool("tonight"), tool("counter", remember), reply("कल चार लोगों को।"))
    say(api, "कल किसको याद दिलाना है?")
    names = {r["name"] for r in seen["reminders_tomorrow"]}
    assert names == {"पाटिल", "इकबाल भाई", "राजू", "सलमा"}
    assert (seen["owing"], seen["left_alone"]) == (38, 34)


def test_the_munshi_corrects_an_entry_rather_than_writing_a_new_one(
    api: TestClient, model: Script, tx: db.Conn
) -> None:
    before = sharmas_entries(tx)
    model.then(
        tool("find_customer", {"name": "शर्मा"}),
        tool(
            "propose_correction",
            lambda found: {
                "customer_id": first_found(found),
                "wrong_amount_rupees": 200,
                "right_amount_rupees": 150,
            },
        ),
        reply("शर्मा, दो सौ की जगह एक सौ पचास, पक्का?"),
    )
    out = say(api, "शर्मा का दो सौ गलत लिखा, एक सौ पचास था")
    card = out["card"]
    assert (card["kind"], card["amount_paise"], card["corrects_amount_paise"]) == (
        "correction",
        150_00,
        200_00,
    )
    assert card["reasons"] == ["correction"], "a correction always waits for a yes"
    assert sharmas_entries(tx) == before, "a card corrects nothing"

    model.then(reply("सुधार दिया, शर्मा जी अपने फोन पर हाँ करेंगे।"))
    done = tap(api, out)
    assert done["card"]["status"] == "saved"
    after = {e.id: e for e in entries.of_customer(tx, SHARMA)}
    new = after[done["card"]["entry_id"]]
    assert (new.amount_paise, new.status) == (150_00, "recorded")
    assert new.corrects_entry_id is not None
    assert after[new.corrects_entry_id].status == "corrected"
    assert len(after) == len(before) + 1, "one new entry: the correction"


def test_with_no_wrong_amount_and_one_open_entry_that_is_the_one(
    api: TestClient, model: Script
) -> None:
    model.then(
        tool("find_customer", {"name": "शर्मा"}),
        tool(
            "propose_correction",
            lambda found: {"customer_id": first_found(found), "right_amount_rupees": 250},
        ),
        reply("पक्का?"),
    )
    card = say(api, "शर्मा वाला ढाई सौ था")["card"]
    assert (card["corrects_amount_paise"], card["amount_paise"]) == (200_00, 250_00)


def test_a_wrong_amount_he_never_wrote_is_asked_about(
    api: TestClient, model: Script
) -> None:
    seen: dict[str, Any] = {}

    def remember(result: Any) -> dict[str, Any]:
        seen.update(result)
        return {}

    model.then(
        tool("find_customer", {"name": "शर्मा"}),
        tool(
            "propose_correction",
            lambda found: {
                "customer_id": first_found(found),
                "wrong_amount_rupees": 700,
                "right_amount_rupees": 300,
            },
        ),
        tool("counter", remember),
        reply("शर्मा के नाम सात सौ नहीं, दो सौ लिखा है।"),
    )
    assert say(api, "शर्मा का सात सौ गलत है")["card"] is None
    assert seen["ok"] is False
    assert [e["amount"] for e in seen["open_entries"]] == ["दो सौ रुपये"]


# ── he fixes the card on screen ─────────────────────────────────────────────


def edit(api: TestClient, out: dict[str, Any], **body: Any) -> Any:
    card = out["card"]
    return api.post(
        f"/shops/{SHOP}/munshi/{out['conversation_id']}/cards/{card['draft_id']}/edit",
        json=body,
    )


def test_he_fixes_the_amount_on_the_card_and_his_tap_writes_that(
    api: TestClient, model: Script, tx: db.Conn
) -> None:
    before = sharmas_entries(tx)
    model.then(*shows_sharma(200))
    out = say(api, "शर्मा जी को दो सौ")
    r = edit(api, out, amount_rupees=250)
    assert r.status_code == 200, r.text
    assert (r.json()["card"]["amount_paise"], model.calls) == (250_00, 3), "no model"
    model.then(reply("लिख दिया।"))
    tap(api, out)
    assert sharmas_entries(tx) == [*before, 250_00]


def test_he_names_someone_new_on_the_card_and_adds_their_udhaar(
    api: TestClient, model: Script, tx: db.Conn
) -> None:
    model.then(
        tool("find_customer", {"name": "श्रेया"}),
        tool(
            "propose_new_customer", {"name": "Shreya", "description": "Room 4 A wing C"}
        ),
        reply("श्रेया को जोड़ दूँ?"),
    )
    out = say(api, "श्रेया को पाँच सौ रुपये, रूम नंबर चार विंग सी")
    assert out["card"]["kind"] == "customer"
    card = edit(api, out, amount_rupees=500, new_tag="Room 4, C wing").json()["card"]
    assert (card["kind"], card["amount_paise"], card["tag"]) == (
        "udhaar",
        500_00,
        "Room 4, C wing",
    )
    model.then(reply("जोड़ दिया और लिख दिया।"))
    tap(api, out)
    (shreya,) = added(tx, "Shreya")
    assert shreya.tag == "Room 4, C wing"
    assert [e.amount_paise for e in entries.of_customer(tx, shreya.id)] == [500_00]


def test_a_card_is_fixed_within_the_same_limits(api: TestClient, model: Script) -> None:
    model.then(*shows_sharma(100, "paid_back"))
    out = say(api, "शर्मा जी ने सौ दिए")
    r = edit(api, out, amount_rupees=5000)
    assert r.status_code == 409 and "owe only" in r.json()["detail"]


def test_a_decided_card_is_not_changed(api: TestClient, model: Script) -> None:
    model.then(*shows_sharma(200), reply("लिख दिया।"))
    out = say(api, "शर्मा जी को दो सौ")
    tap(api, out)
    assert edit(api, out, amount_rupees=300).status_code == 409


def test_out_of_credits_says_so_plainly(
    api: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from bahi.voice import sarvam

    def broke(*_: Any, **__: Any) -> Any:
        raise sarvam.OutOfCredits("Sarvam said 402: No credits available.")

    monkeypatch.setattr(route, "chat", lambda: broke)
    r = api.post(f"/shops/{SHOP}/munshi", json={"text": "शर्मा जी को दो सौ"})
    assert r.status_code == 503 and "no credits" in r.json()["detail"]


# ── money back, oldest first ─────────────────────────────────────────────────


def test_cash_pays_the_oldest_open_entry_first(tx: db.Conn) -> None:
    now = clock.now()
    cid = customers.add(tx, SHOP, "Naya grahak", now)
    first = ledger.record(tx, SHOP, 100_00, now, customer_id=UUID(cid))
    second = ledger.record(
        tx, SHOP, 50_00, now + timedelta(seconds=1), customer_id=UUID(cid)
    )
    later = now + timedelta(seconds=2)
    assert ledger.pay_cash(tx, cid, 120_00, later) == [first.id, second.id]
    after = {e.id: e for e in entries.of_customer(tx, cid)}
    assert after[first.id].status == "settled"
    assert after[second.id].status == "recorded" and after[second.id].paid_paise == 20_00
    with pytest.raises(Conflict):
        ledger.pay_cash(tx, cid, 31_00, now + timedelta(seconds=2))


# ── the search ───────────────────────────────────────────────────────────────

BOOK = [
    Person("sharma", "Sharma", "Room 19, B wing", "शर्मा", "रूम 19, बी विंग"),
    Person("asha", "Asha", "Room 7, B wing", "आशा", "रूम 7, बी विंग"),
    Person("rekha", "Rekha", "Room 4, A wing", "रेखा", "रूम 4, ए विंग"),
    Person("yadav", "Yadav", "Milk van", "यादव", "मिल्क वैन"),
    Person("bhosale", "Bhosale", "Chawl 6", "भोसले", "चॉल 6"),
    Person("pawar", "Pawar", "Room 17, C wing", "पवार", "रूम 17, सी विंग"),
]


def refs(name: str | None, description: str | None) -> list[str]:
    return [f.person.ref for f in find(BOOK, name, description).found]


def test_a_description_finds_everyone_it_fits_and_only_them() -> None:
    assert refs(None, "B wing") == ["sharma", "asha"]
    assert refs(None, "Room 19, B wing") == ["sharma"]


def test_a_full_description_beats_a_faint_name() -> None:
    assert refs("दूध वाले भैया", "Milk van") == ["yadav"]


def test_a_misheard_name_comes_back_weak() -> None:
    (only,) = find(BOOK, "पटर", None).found
    assert only.person.ref == "pawar" and not only.strong


def test_nobody_fits_says_so() -> None:
    s = find(BOOK, "रमेश", None)
    assert s.found == () and s.note and "nobody" in s.note
