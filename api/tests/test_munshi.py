"""The munshi, with Sarvam replaced by a script.

Each test scripts what the model says: which tools it calls, with what, and what
it replies. The tools, the checks, the drafts and the ledger are the real ones,
on the seeded database, rolled back after each test. So these hold the code to
its rules whatever a model does: it cannot write an entry, cannot put someone it
never looked up on a card, cannot approve its own card, and a double tap is one
entry.
"""

from __future__ import annotations

import io
import json
import time
import wave
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
    assert ".wav?lang=hi-IN" in out["say_url"]
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


def unpaid_open(tx: db.Conn) -> list[Any]:
    """Sharma's entries that could be taken back: open, nothing paid, and not
    past the limitation line."""
    from bahi.domain.limitation import expired

    today = clock.now().date()
    return [
        e
        for e in entries.of_customer(tx, SHARMA)
        if e.status in ("recorded", "confirmed", "disputed")
        and e.paid_paise == 0
        and not expired(
            e.recorded_at.date(),
            e.acknowledged_at.date() if e.acknowledged_at else None,
            today,
        )
    ]


def test_the_munshi_takes_back_an_entry_written_by_mistake(
    api: TestClient, model: Script, tx: db.Conn
) -> None:
    """ "शर्मा वाला दो सौ गलती से लिखा, हटा दो": a removal card, never a जमा."""
    (open_,) = unpaid_open(tx)
    results: list[Any] = []
    model.then(
        tool("find_customer", {"name": "शर्मा"}),
        tool(
            "propose_removal",
            lambda found: {"customer_id": first_found(found), "amount_rupees": 0},
        ),
        tool("counter", keeping(results, {})),
        reply("शर्मा जी का दो सौ उधार हटाना है, पक्का?"),
    )
    out = say(api, "शर्मा वाला दो सौ गलती से लिखा, हटा दो")
    assert results[0]["ok"] is True, "an amount of zero means: he didn't say one"
    card = out["card"]
    assert (card["kind"], card["amount_paise"], card["reasons"]) == (
        "removal",
        open_.amount_paise,
        ["removal"],
    )
    model.then(reply("हटा दिया।"))
    done = tap(api, out)
    assert done["card"]["status"] == "saved"
    assert entries.get(tx, open_.id).status == "removed"  # type: ignore[union-attr]
    assert any(d.startswith("Took back: Sharma") for d in done["done"])


def test_a_card_the_book_refuses_comes_off_the_screen(
    api: TestClient, model: Script, tx: db.Conn
) -> None:
    from bahi.service import ledger

    (open_,) = unpaid_open(tx)
    model.then(
        tool("find_customer", {"name": "शर्मा"}),
        tool("propose_removal", lambda found: {"customer_id": first_found(found)}),
        reply("पक्का?"),
    )
    out = say(api, "शर्मा वाला हटा दो")
    everything = ledger.left_to_pay(tx, SHARMA, clock.now().date())
    ledger.pay_cash(tx, SHARMA, everything, clock.now())  # paid before his yes
    model.then(reply("ये एंट्री का कुछ हिस्सा चुक गया है, इसलिए हट नहीं सकती।"))
    done = tap(api, out)
    assert done["card"]["status"] == "cancelled", "nothing waits on a yes it can't get"
    assert entries.get(tx, open_.id).status == "settled"  # type: ignore[union-attr]


def test_the_munshi_changes_where_someone_lives(
    api: TestClient, model: Script, tx: db.Conn
) -> None:
    model.then(
        tool("find_customer", {"name": "शर्मा"}),
        tool(
            "propose_details",
            lambda found: {
                "customer_id": first_found(found),
                "description": "Room 3, C wing",
            },
        ),
        reply("शर्मा जी, अब रूम 3, सी विंग, पक्का?"),
    )
    out = say(api, "शर्मा जी actually सी विंग रूम तीन में रहते हैं")
    card = out["card"]
    assert (card["kind"], card["change_tag"], card["change_name"]) == (
        "details",
        "Room 3, C wing",
        None,
    )
    model.then(reply("बदल दिया।"))
    tap(api, out)
    c = customers.get(tx, SHARMA)
    assert c is not None and (c.display_name, c.tag) == ("Sharma", "Room 3, C wing")


def test_a_message_goes_only_with_his_yes(
    api: TestClient, model: Script, tx: db.Conn
) -> None:
    from bahi.store import threads

    def said() -> list[str]:
        t = threads.of_customer(tx, SHARMA)
        return (
            [m.body for m in threads.messages(tx, t.id) if m.author == "shop"]
            if t
            else []
        )

    before = said()
    text = "शर्मा जी, कल दुकान पर आ जाना, सामान आ गया है।"
    model.then(
        tool("find_customer", {"name": "शर्मा"}),
        tool(
            "propose_message",
            lambda found: {"customer_id": first_found(found), "text": text},
        ),
        reply("भेज दूँ?"),
    )
    out = say(api, "शर्मा को बोल दो कल आ जाए, सामान आ गया है")
    assert (out["card"]["kind"], out["card"]["message"]) == ("message", text)
    assert said() == before, "a card sends nothing"
    model.then(reply("भेज दिया।"))
    tap(api, out)
    assert said() == [*before, text]


def test_the_card_says_only_what_he_said_for_it(api: TestClient, model: Script) -> None:
    model.then(*shows_sharma(200), reply("लिख दिया।"))
    out = say(api, "शर्मा को दो सौ")
    tap(api, out)
    model.then(*shows_sharma(50), reply("..."))
    card = say(api, "अब शर्मा को पचास और", out["conversation_id"])["card"]
    assert card["spoken_text"] == "अब शर्मा को पचास और"


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
    assert r.status_code == 409 and "can be paid" in r.json()["detail"]


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


# ── names: a count, until he asks to hear them ───────────────────────────────


def keeping(results: list[Any], args: dict[str, Any]) -> Callable[[Any], dict[str, Any]]:
    """A step that keeps the last tool result, then calls with `args`."""

    def step(result: Any) -> dict[str, Any]:
        results.append(result)
        return args

    return step


def test_three_or_more_are_a_count_until_he_has_been_asked(
    api: TestClient, model: Script
) -> None:
    results: list[Any] = []
    wing = {"description": "B wing"}
    model.then(
        tool("find_customer", wing),
        # The model tries to read them out in the same breath: refused.
        tool("find_customer", keeping(results, {**wing, "read_names": True})),
        tool("counter", keeping(results, {})),
        reply("बी विंग में कई लोग हैं। नाम बताऊँ, या आप बताएँगे किसके लिए?"),
    )
    out = say(api, "बी विंग वाले को दो सौ")
    counted, too_soon = results
    assert counted["count"] >= 3 and "customers" not in counted
    assert "नाम बताऊँ" in counted["next"]
    assert "customers" not in too_soon and too_soon["names"].startswith("not yet")

    # He heard the count and asked for the names: now they come back, each with
    # its place and never a balance.
    results.clear()
    model.then(
        tool("find_customer", {**wing, "read_names": True}),
        tool("counter", keeping(results, {})),
        reply("..."),
    )
    say(api, "पढ़ दो", out["conversation_id"])
    (named,) = results
    assert named["count"] == counted["count"]
    assert len(named["customers"]) == min(named["count"], 8)
    assert all(c["name"] and "owes" not in c for c in named["customers"])


def test_a_long_list_is_read_eight_at_a_time_then_the_rest_after_the_last(
    api: TestClient, model: Script, tx: db.Conn
) -> None:
    now = clock.now()
    for n in (50, 51, 52):
        customers.add(tx, SHOP, f"Naya {n}", now, tag=f"Room {n}, B wing")
    results: list[Any] = []
    wing = {"description": "B wing"}
    model.then(tool("find_customer", wing), reply("बी विंग में कई लोग हैं। नाम बताऊँ?"))
    out = say(api, "बी विंग वाले को दो सौ")
    model.then(
        tool("find_customer", {**wing, "read_names": True}),
        tool("find_customer", keeping(results, {**wing, "read_names": True, "skip": 8})),
        tool("counter", keeping(results, {})),
        reply("..."),
    )
    say(api, "पढ़ दो, फिर बाकी भी", out["conversation_id"])
    first, rest = results
    total = first["count"]
    assert total > 8
    # Eight, and how many are left, with how to ask for them.
    assert len(first["customers"]) == 8 and first["more"] == total - 8
    assert "skip 8" in first["next"] and "more" in first["next"]
    # The rest, starting after the last one read: nobody twice, nobody missed.
    assert len(rest["customers"]) == total - 8 and "more" not in rest
    ids = [c["id"] for c in first["customers"] + rest["customers"]]
    assert len(set(ids)) == total


def test_names_he_never_heard_the_count_of_are_not_read(
    api: TestClient, model: Script
) -> None:
    results: list[Any] = []
    model.then(
        tool("find_customer", {"description": "B wing", "read_names": True}),
        tool("counter", keeping(results, {})),
        reply("..."),
    )
    say(api, "बी विंग वाले को दो सौ")
    (first,) = results
    assert first["count"] >= 3 and "customers" not in first


def test_someone_picked_from_several_waits_for_a_clear_yes(
    api: TestClient, model: Script
) -> None:
    """He heard five names and said only an amount: the model picked one. That
    card doesn't go by itself in three seconds; it waits for his yes."""
    wing = {"description": "B wing"}
    model.then(
        tool("find_customer", wing),
        reply("बी विंग में कई लोग हैं। नाम बताऊँ?"),
    )
    out = say(api, "बी विंग वाले को दो सौ")
    model.then(
        tool("find_customer", {**wing, "read_names": True}),
        tool(
            "propose_entry",
            lambda found: {
                "customer_id": first_found(found),
                "kind": "udhaar",
                "amount_rupees": 200,
            },
        ),
        reply("..., दो सौ रुपये उधार, पक्का?"),
    )
    card = say(api, "पढ़ दो, दो सौ", out["conversation_id"])["card"]
    assert card["reasons"] == ["one_of_several"]

    # Looked up by the name he says, alone: the quick card, as ever.
    model.then(*shows_sharma(200))
    card = say(api, "शर्मा जी को", out["conversation_id"])["card"]
    assert card["display_name"] == "Sharma" and card["reasons"] == []


def test_a_sound_with_no_words_never_reaches_the_munshi(
    api: TestClient, model: Script, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The mic caught a cough, and Sarvam heard no words: the munshi isn't asked
    (Sarvam refuses an empty turn), and he is told plainly."""
    from bahi import voice

    monkeypatch.setattr(voice, "hear", lambda *a, **k: voice.Transcript("  ", "sarvam"))
    r = api.post(
        f"/shops/{SHOP}/munshi/voice",
        files={"audio": ("speech.webm", b"a cough", "audio/webm")},
    )
    assert r.status_code == 422 and "Didn't catch any words" in r.json()["detail"]
    assert model.calls == 0


# ── the munshi's voice ───────────────────────────────────────────────────────

NAMES = (
    "अनुभव, रूम 311 बी विंग; आशा, रूम 7 बी विंग; कामत, रूम 13 बी विंग; "
    "मिश्र जी, रूम 9 बी विंग; राहुल, रूम 6 बी विंग; रिजवान, रूम 18 बी विंग। "
    "इनमें से कौन हैं?"
)


def wav(seconds: float) -> bytes:
    out = io.BytesIO()
    with wave.open(out, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(24000)
        w.writeframes(b"\0\0" * int(24000 * seconds))
    return out.getvalue()


@pytest.fixture
def voice_on(monkeypatch: pytest.MonkeyPatch, tmp_path: Any) -> list[str]:
    """Sarvam's voice, faked: each sentence takes a moment and a second of audio."""
    from bahi.voice import said, sarvam

    monkeypatch.setenv("SARVAM_OFFLINE", "0")
    monkeypatch.setenv("SARVAM_API_KEY", "not-a-real-key")
    monkeypatch.setattr(said, "LIVE", tmp_path)
    asked: list[str] = []

    def speak(
        text: str, *, key: str, voice: str, timeout: float, language: str = "hi-IN"
    ) -> bytes:
        assert timeout == sarvam.SENTENCE_TTS_TIMEOUT_S
        asked.append(text)
        time.sleep(0.05)
        return wav(1.0)

    monkeypatch.setattr(sarvam, "speak", speak)
    return asked


def test_a_long_reply_is_said_whole_in_one_voice(voice_on: list[str]) -> None:
    """Never in pieces: each request to Sarvam is voiced afresh, and two halves of
    one sentence sound like two people."""
    from bahi.voice import said

    path = said.sentence(NAMES)
    assert voice_on == [NAMES]
    with wave.open(str(path)) as w:
        assert w.getnframes() == 24000
    said.sentence(NAMES)  # kept: never asked for twice
    assert voice_on == [NAMES]


def test_the_reply_is_said_before_the_screen_asks_and_only_once(
    api: TestClient, model: Script, voice_on: list[str]
) -> None:
    model.then(reply(NAMES))
    out = say(api, "पढ़ दो")
    r = api.get(out["say_url"])
    assert r.status_code == 200 and r.headers["content-type"] == "audio/wav"
    assert voice_on == [NAMES]


# ── memory (M3) ──────────────────────────────────────────────────────────────


def kept_by(results: list[Any]) -> Callable[[Any], dict[str, Any]]:
    return keeping(results, {})


def test_it_cannot_remember_about_someone_it_never_looked_up(
    api: TestClient, model: Script
) -> None:
    results: list[Any] = []
    model.then(
        tool("remember", {"customer_id": SHARMA[:8], "note": "x"}),
        tool("counter", kept_by(results)),
        reply("..."),
    )
    say(api, "शर्मा जी का याद रखना")
    assert results[0]["ok"] is False and "find_customer" in results[0]["problem"]


def test_a_note_it_keeps_is_on_his_card_and_holds_tonight(
    api: TestClient, model: Script
) -> None:
    patil = str(uid("customer", HOME, "patil"))
    results: list[Any] = []
    model.then(
        tool("find_customer", {"name": "पाटिल"}),
        tool(
            "remember",
            lambda found: {
                "customer_id": first_found(found),
                "note": "पेंशन 10 तारीख को आती है, तब तक मत भेजना",
                "until": "2026-10-10",
            },
        ),
        tool("customer_card", keeping(results, {"customer_id": patil[:8]})),
        tool("tonight", keeping(results, {})),
        tool("counter", keeping(results, {})),
        reply("याद रख लिया।"),
    )
    out = say(api, "पाटिल की पेंशन 10 को आती है, तब तक मत भेजना")
    remembered, card, tomorrow = results
    assert remembered["ok"] and remembered["quiet_until"] == "2026-10-10"
    assert card["remembered"][0]["said"].startswith("पेंशन 10 तारीख")
    held = tomorrow["held_for_what_was_said"]
    assert [h["why"] for h in held] == ["your note"]
    assert "Patil" not in {r["name"] for r in tomorrow["reminders_tomorrow"]}
    assert any("Remembered about Patil" in d for d in out["done"])


def test_asked_when_someone_will_pay_it_reads_how_they_pay(
    api: TestClient, model: Script
) -> None:
    results: list[Any] = []
    model.then(
        tool("find_customer", {"name": "पाटिल"}),
        tool(
            "customer_card",
            lambda found: {"customer_id": first_found(found)},
        ),
        tool("counter", keeping(results, {})),
        reply("मेरे हिसाब से…"),
    )
    say(api, "पाटिल कब पैसे देगा?")
    (card,) = results
    how = card["how_they_pay"]
    assert how["usually_pays_every_days"] and how["likely_next"]
    assert how["right_now"].startswith("late by their own rhythm")
    assert how["likely_next"] == "no date from their rhythm: they are past it"
    assert "guess" in card["next"] and "passed" in card["next"]


def test_who_pays_this_week_is_worked_out_not_guessed(
    api: TestClient, model: Script, tx: db.Conn
) -> None:
    from bahi.store import memories

    raju = str(uid("customer", HOME, "raju"))
    memories.add(
        tx,
        SHOP,
        raju,
        "promise",
        "6 को दूँगा",
        "customer",
        clock.now(),
        until=clock.today() + timedelta(days=3),
    )
    results: list[Any] = []
    model.then(
        tool("expected_payments", {}),
        tool("counter", keeping(results, {})),
        reply("…"),
    )
    say(api, "इस हफ़्ते कौन देने वाला है?")
    (week,) = results
    assert [p["name"] for p in week["promised_in_chat"]] == ["राजू"]
    assert "पाटिल" in {p["name"] for p in week["late_by_their_rhythm"]}
    everyone = week["promised_in_chat"] + week["due_by_their_rhythm"]
    assert all("amount" not in str(p) and "₹" not in str(p) for p in everyone)


def test_recall_asks_cognee_and_falls_back_to_the_books_own_list(
    api: TestClient, model: Script, tx: db.Conn
) -> None:
    from bahi.memory import cognee_client
    from bahi.store import memories

    memories.add(tx, SHOP, SHARMA, "note", "pays through his son", "shop", clock.now())
    results: list[Any] = []
    ask = {"question": "शर्मा जी कैसे पैसे देते हैं?"}
    model.then(tool("recall", ask), tool("counter", keeping(results, {})), reply("..."))
    say(api, "शर्मा जी कैसे देते हैं?")
    assert results[0]["searched"] == "the book's list"
    assert "pays through his son" in results[0]["found"]

    class Remembers:
        def remember(self, *a: Any) -> str | None:
            return None

        def recall(self, shop_id: str, question: str) -> str:
            return f"cognee found: {question}"

        def forget(self, *a: Any) -> None:
            return None

    cognee_client.use(Remembers())
    try:
        results.clear()
        model.then(
            tool("recall", ask), tool("counter", keeping(results, {})), reply("...")
        )
        say(api, "शर्मा जी कैसे देते हैं?")
    finally:
        cognee_client.use(None)
    assert results[0]["searched"] == "cognee"
    assert results[0]["found"] == f"cognee found: {ask['question']}"


def test_a_nickname_he_confirmed_finds_them_again_only_as_a_hint(
    api: TestClient, model: Script
) -> None:
    def sharma_as(called: str | None) -> Step:
        return tool(
            "propose_entry",
            lambda found: {
                "customer_id": first_found(found),
                "kind": "udhaar",
                "amount_rupees": 100,
                **({"called": called} if called else {}),
            },
        )

    model.then(
        tool("find_customer", {"name": "शर्मा"}),
        sharma_as("बड़े भैया"),
        reply("शर्मा जी, सौ रुपये उधार, पक्का?"),
        reply("लिख दिया।"),
    )
    out = say(api, "बड़े भैया यानी शर्मा जी को सौ")
    assert tap(api, out)["card"]["status"] == "saved"

    results: list[Any] = []
    model.then(
        tool("find_customer", {"name": "बड़े भैया"}),
        sharma_as(None),
        tool("counter", keeping(results, {})),
        reply("शर्मा जी, रूम 19? पक्का?"),
    )
    card = say(api, "बड़े भैया को सौ")["card"]
    assert card["display_name"] == "Sharma"
    assert card["reasons"] == ["weak_match"]  # a hint: his clear yes decides


def test_a_name_that_found_nobody_then_someone_is_decided_before_the_card(
    api: TestClient, model: Script, tx: db.Conn
) -> None:
    # "चिंटू को सौ" finds nobody; asked who, he says "शर्मा". The card waits until
    # the model says whether चिंटू was Sharma: a turn later it forgot to (live,
    # 3 Oct), and the nickname was lost.
    from bahi.store import memories

    model.then(tool("find_customer", {"name": "चिंटू"}), reply("कौन चिंटू?"))
    first = say(api, "चिंटू को सौ")
    results: list[Any] = []
    sharma = {"customer_id": "", "kind": "udhaar", "amount_rupees": 100}

    def to_sharma(found: Any) -> dict[str, Any]:
        results.append(found)
        sharma["customer_id"] = first_found(found)
        return sharma

    def as_chintu(refused: Any) -> dict[str, Any]:
        results.append(refused)
        return {**sharma, "called": "चिंटू"}

    model.then(
        tool("find_customer", {"name": "शर्मा"}),
        tool("propose_entry", to_sharma),
        tool("propose_entry", as_chintu),
        tool("counter", keeping(results, {})),
        reply("शर्मा जी, जिन्हें आप चिंटू कहते हैं, सौ रुपये उधार, पक्का?"),
        reply("लिख दिया।"),
    )
    out = say(api, "शर्मा जी", first["conversation_id"])
    found, refused, shown = results
    assert "चिंटू" in found["he_said_earlier"]
    assert refused["ok"] is False and "called 'चिंटू'" in refused["problem"]
    assert shown["ok"] is True and shown["he_calls_them"] == "चिंटू"
    assert out["card"]["called"] == "चिंटू"

    saved = tap(api, out)
    assert "Remembered: you call Sharma चिंटू" in saved["done"]
    nicks = [m.body for m in memories.of_customer(tx, SHARMA) if m.kind == "nickname"]
    assert nicks == ["चिंटू"]


def test_he_can_say_the_name_that_found_nobody_was_someone_else(
    api: TestClient, model: Script, tx: db.Conn
) -> None:
    from bahi.store import memories

    model.then(tool("find_customer", {"name": "चिंटू"}), reply("कौन चिंटू?"))
    first = say(api, "चिंटू को सौ")
    model.then(
        tool("find_customer", {"name": "शर्मा"}),
        tool(
            "propose_entry",
            lambda found: {
                "customer_id": first_found(found),
                "kind": "udhaar",
                "amount_rupees": 100,
                "called": "",
            },
        ),
        reply("शर्मा जी, सौ रुपये उधार, पक्का?"),
        reply("लिख दिया।"),
    )
    out = say(api, "नहीं, शर्मा जी को", first["conversation_id"])
    assert out["card"]["called"] is None
    tap(api, out)
    assert not [m for m in memories.of_customer(tx, SHARMA) if m.kind == "nickname"]


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


def test_a_place_nobody_lives_in_finds_nobody_not_everyone_with_a_wing() -> None:
    # "वी-विंग", a misheard B wing: "wing" alone tells nobody apart.
    assert refs(None, "V wing") == []
    assert refs("V", "V wing") == []
    assert refs(None, "B wing") == ["sharma", "asha"]
    assert refs(None, "Room 4, A wing") == ["rekha"]


def test_a_place_given_as_a_name_is_read_as_a_place() -> None:
    assert refs("बी विंग", None) == ["sharma", "asha"]
    assert refs("C wing", None) == ["pawar"]
    assert refs("रमेश", None) == []


def test_a_full_description_beats_a_faint_name() -> None:
    assert refs("दूध वाले भैया", "Milk van") == ["yadav"]


def test_a_misheard_name_comes_back_weak() -> None:
    (only,) = find(BOOK, "पटर", None).found
    assert only.person.ref == "pawar" and not only.strong


def test_nobody_fits_says_so() -> None:
    s = find(BOOK, "रमेश", None)
    assert s.found == () and s.note and "nobody" in s.note


def test_the_reply_is_said_in_its_own_language() -> None:
    from bahi.voice import language_of

    assert language_of("शर्मा जी, दो सौ रुपये उधार, पक्का?") == "hi-IN"
    assert language_of("शर्मा, दोनशे रुपये उधार, नक्की?", "mr-IN") == "mr-IN"
    assert language_of("சர்மா, இருநூறு ரூபாய், சரியா?") == "ta-IN"
    assert language_of("Sharma, two hundred rupees udhaar, okay?") == "en-IN"
    assert language_of("₹200") == "hi-IN"


def test_a_whole_name_finds_that_person_not_everyone_with_the_first_name() -> None:
    book = [
        Person("a1", "Anubhav", "Room 311, B wing", "अनुभव", "रूम 311, बी विंग"),
        Person("a2", "Anubhav Jain", "Medical shop", "अनुभव जैन", "मेडिकल शॉप"),
        Person("a3", "Anubhav Shukla", "Room 1006, B wing", "अनुभव शुक्ला", None),
    ]

    def refs(name: str, description: str | None = None) -> list[str]:
        return [f.person.ref for f in find(book, name, description).found]

    assert refs("अनुभव शुक्ला") == ["a3"]
    # Even with the new address he is moving him to, which another Anubhav has.
    assert refs("अनुभव शुक्ला", "Room 311, C wing") == ["a3"]
    assert refs("अनुभव") == ["a1", "a2", "a3"], "the first name alone: all three"
