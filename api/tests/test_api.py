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
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from bahi import clock
from bahi.service import app
from bahi.service.deps import connection
from bahi.voice import said, sarvam
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


def test_scanning_again_while_waiting_is_the_same_visit(api: TestClient) -> None:
    """His phone reloaded the page: the counter still lists him once."""
    person, first = join(api)
    again = api.post(f"/join/{SHOP}", json={"person_id": person})
    assert again.json()["scan_id"] == first["scan_id"]
    waiting = api.get(f"/shops/{SHOP}/counter").json()["waiting"]
    assert [w["scan_id"] for w in waiting] == [first["scan_id"]]


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


# ── voice ────────────────────────────────────────────────────────────────────


def hear(api: TestClient, text: str) -> Any:
    r = api.post(f"/shops/{SHOP}/heard", json={"text": text})
    assert r.status_code == 200, r.text
    return r.json()


def test_with_one_person_waiting_the_amount_is_enough(api: TestClient) -> None:
    _, joined = join(api)
    h = hear(api, "do sau")
    assert h["amount_paise"] == 20000
    assert h["readback"] == {"roman": "do sau", "devanagari": "दो सौ"}
    assert h["who"]["kind"] == "picked" and h["who"]["how"] == "only_one"
    assert h["who"]["person"]["scan_id"] == joined["scan_id"]


def test_with_two_waiting_an_amount_alone_asks_who(api: TestClient) -> None:
    join(api, "Kavita")
    join(api, "Ravi")
    h = hear(api, "do sau")
    assert h["amount_paise"] == 20000
    assert h["who"]["kind"] == "ask" and h["who"]["why"] == "who"
    assert sorted(p["display_name"] for p in h["who"]["among"]) == ["Kavita", "Ravi"]


def test_with_two_waiting_the_name_picks_one(api: TestClient) -> None:
    _, kavita = join(api, "Kavita")
    join(api, "Ravi")
    h = hear(api, "Kavita, teen sau")
    assert h["who"]["how"] == "at_counter"
    assert h["who"]["person"]["scan_id"] == kavita["scan_id"]


def test_a_name_not_at_the_counter_is_found_in_the_book(api: TestClient) -> None:
    h = hear(api, "Sharma ko dhaai sau udhaar")
    assert h["amount_paise"] == 25000
    assert h["who"]["how"] == "in_book"
    assert h["who"]["person"] == {
        "customer_id": SHARMA,
        "display_name": "Sharma",
        "tag": "Room 19, B wing",
        "scan_id": None,
    }


def test_an_invited_customer_is_never_picked(api: TestClient) -> None:
    h = hear(api, "Rukhsana ko do sau")
    assert h["who"] == {"kind": "ask", "why": "not_found", "among": []}


def test_hearing_records_nothing(api: TestClient, tx: db.Conn) -> None:
    before = tx.execute("SELECT count(*) FROM entries").fetchone()
    hear(api, "Sharma ko do sau")
    assert tx.execute("SELECT count(*) FROM entries").fetchone() == before


def test_what_was_heard_records_like_anything_typed(api: TestClient) -> None:
    _, joined = join(api)
    h = hear(api, "saade teen sau de do")
    person = h["who"]["person"]
    r = record(
        api,
        scan_id=person["scan_id"],
        amount_paise=h["amount_paise"],
        spoken_text=h["transcript"],
    )
    assert r.status_code == 201
    assert (r.json()["amount_paise"], r.json()["spoken_text"]) == (
        35000,
        "saade teen sau de do",
    )


def test_a_demo_clip_is_heard_with_the_wifi_off(api: TestClient) -> None:
    join(api)
    wav = api.get("/voice/clips/do-sau.wav")
    assert wav.status_code == 200 and wav.headers["content-type"] == "audio/wav"
    r = api.post(
        f"/shops/{SHOP}/voice", files={"audio": ("clip.wav", wav.content, "audio/wav")}
    )
    assert r.status_code == 200, r.text
    h = r.json()
    assert h["source"] in {"clip_script", "sarvam_cached"}
    assert h["amount_paise"] == 20000 and h["who"]["how"] == "only_one"


def test_a_new_recording_with_voice_offline_is_refused_not_guessed(
    api: TestClient,
) -> None:
    r = api.post(
        f"/shops/{SHOP}/voice",
        files={"audio": ("x.webm", b"not heard before", "audio/webm")},
    )
    assert r.status_code == 503
    assert "Type the amount" in r.json()["detail"]


def test_a_browser_recording_reaches_sarvam_as_a_type_it_takes(
    api: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Chrome records "audio/webm;codecs=opus"; Sarvam refuses the ";codecs"."""
    monkeypatch.setenv("SARVAM_OFFLINE", "0")
    monkeypatch.setenv("SARVAM_API_KEY", "not-a-real-key")
    sent: list[str] = []

    def fake_post(url: str, **kw: Any) -> Any:
        if url != sarvam.URL:  # the reading: unreachable here, so our parser reads
            raise httpx.ConnectError("faked")
        sent.append(kw["files"]["file"][2])
        return httpx.Response(200, json={"transcript": "Sharma ko do sau"})

    monkeypatch.setattr(httpx, "post", fake_post)
    r = api.post(
        f"/shops/{SHOP}/voice",
        files={"audio": ("speech.webm", b"new audio", "audio/webm;codecs=opus")},
    )
    assert r.status_code == 200, r.text
    assert sent == ["audio/webm"]


def test_when_sarvam_refuses_the_screen_gets_a_plain_sentence(
    api: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SARVAM_OFFLINE", "0")
    monkeypatch.setenv("SARVAM_API_KEY", "not-a-real-key")
    refusal = httpx.Response(400, json={"error": {"message": "Invalid file type"}})
    monkeypatch.setattr(httpx, "post", lambda url, **kw: refusal)
    r = api.post(
        f"/shops/{SHOP}/voice", files={"audio": ("x.webm", b"new audio", "audio/webm")}
    )
    assert r.status_code == 502
    assert (
        r.json()["detail"]
        == "Sarvam couldn't hear that just now. Say it again, or type it."
    )


# ── the answer to "किसके लिए?" ────────────────────────────────────────────────


def answer(api: TestClient, text: str, among: list[str] | None = None) -> Any:
    r = api.post(f"/shops/{SHOP}/answer", json={"text": text, "among": among or []})
    assert r.status_code == 200, r.text
    return r.json()


def test_the_answer_to_how_much_is_read_with_what_came_before(
    api: TestClient,
) -> None:
    r = api.post(f"/shops/{SHOP}/heard", json={"text": "do sau", "before": "Sharma ko"})
    h = r.json()
    assert h["transcript"] == "Sharma ko do sau"
    assert h["amount_paise"] == 20000
    assert h["who"]["person"]["customer_id"] == SHARMA


def test_a_spoken_answer_to_how_much_is_read_with_what_came_before(
    api: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SARVAM_OFFLINE", "0")
    monkeypatch.setenv("SARVAM_API_KEY", "not-a-real-key")
    monkeypatch.setattr(sarvam, "heard", lambda *a, **kw: ("दो सौ रुपये", "hi-IN"))
    monkeypatch.setattr(
        sarvam,
        "chat_json",
        lambda *a, **kw: (_ for _ in ()).throw(sarvam.SarvamError("x")),
    )
    r = api.post(
        f"/shops/{SHOP}/voice",
        files={"audio": ("a.webm", b"answer", "audio/webm")},
        data={"before": "Sharma ko"},
    )
    h = r.json()
    assert h["transcript"] == "Sharma ko दो सौ रुपये"
    assert (h["amount_paise"], h["who"]["person"]["customer_id"]) == (20000, SHARMA)


def test_an_answer_names_someone_in_the_book(api: TestClient) -> None:
    a = answer(api, "Sharma ji ke liye")
    assert a["who"]["kind"] == "picked"
    assert a["who"]["person"]["customer_id"] == SHARMA


@pytest.mark.parametrize(
    ("said", "tag"),
    [
        ("Shukla", "Room 1006, B wing"),
        ("शुक्ला वाले", "Room 1006, B wing"),
        ("204 wala", "Room 204, A wing"),
        ("दो सौ चार वाले", "Room 204, A wing"),
        ("Jain", "Medical shop"),
    ],
)
def test_the_answer_to_kaunse_anubhav_picks_among_them(
    api: TestClient, said: str, tag: str
) -> None:
    four = anubhavs(api)
    a = answer(api, said, list(four.values()))
    assert a["who"]["kind"] == "picked", a["who"]
    assert a["who"]["person"]["customer_id"] == four[tag]


def test_the_shop_describes_him_and_that_is_enough(api: TestClient) -> None:
    h = hear(api, "Chai tapri wale ko do sau")
    assert h["who"]["kind"] == "picked"
    assert h["who"]["person"]["display_name"] == "Bablu"
    assert h["who"]["person"]["tag"] == "Chai tapri"


def test_an_answer_can_describe_him_too(api: TestClient) -> None:
    book = api.get(f"/shops/{SHOP}/customers").json()
    offered = [
        c["id"] for c in book if c["display_name"] in ("Bhosale", "Iqbal bhai", "Bablu")
    ]
    a = answer(api, "चाय टपरी", offered)
    assert a["who"]["kind"] == "picked" and a["who"]["person"]["display_name"] == "Bablu"


def test_an_answer_is_looked_for_only_among_those_offered(api: TestClient) -> None:
    a = answer(api, "Sharma", list(anubhavs(api).values()))
    assert a["who"]["kind"] == "ask"


def test_the_one_at_the_counter_answers_to_his_name(api: TestClient) -> None:
    _, kavita = join(api, "Kavita")
    join(api, "Ravi")
    a = answer(api, "Kavita")
    assert a["who"]["how"] == "at_counter"
    assert a["who"]["person"]["scan_id"] == kavita["scan_id"]


def test_an_answer_records_nothing(api: TestClient, tx: db.Conn) -> None:
    before = tx.execute("SELECT count(*) FROM entries").fetchone()
    answer(api, "Sharma")
    assert tx.execute("SELECT count(*) FROM entries").fetchone() == before


def test_a_spoken_answer_is_heard_with_the_names_offered(
    api: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SARVAM_OFFLINE", "0")
    monkeypatch.setenv("SARVAM_API_KEY", "not-a-real-key")
    four = anubhavs(api)
    listened: list[list[str]] = []

    def fake(
        audio: bytes,
        content_type: str,
        *,
        key: str,
        keyterms: Any = (),
        language: str | None = None,
    ) -> tuple[str, str | None]:
        listened.append(list(keyterms))
        return "शुक्ला वाले", "hi-IN"

    monkeypatch.setattr(sarvam, "heard", fake)
    r = api.post(
        f"/shops/{SHOP}/answer/voice",
        files={"audio": ("a.webm", b"answer", "audio/webm")},
        data={"among": ",".join(four.values())},
    )
    assert r.status_code == 200, r.text
    assert r.json()["who"]["person"]["customer_id"] == four["Room 1006, B wing"]
    assert sorted(listened[0]) == sorted(
        ["Anubhav", "Anubhav", "Anubhav Jain", "Anubhav Shukla"]
    )


# ── the readback, in Sarvam's voice ─────────────────────────────────────────


@pytest.fixture
def default_voice(monkeypatch: pytest.MonkeyPatch) -> None:
    """The voice the committed readbacks were spoken in."""
    monkeypatch.delenv("SARVAM_TTS_SPEAKER", raising=False)


@pytest.mark.usefixtures("default_voice")
def test_the_demos_readbacks_play_with_the_wifi_off(api: TestClient) -> None:
    for path in (
        "/voice/say/22000.wav",
        "/voice/say/25000.wav",
        "/voice/ask/who.wav",
        "/voice/ask/how_much.wav",
        "/voice/ask/kind.wav",
        "/voice/ask/again.wav",
    ):
        r = api.get(path)
        assert r.status_code == 200, path
        assert r.headers["content-type"] == "audio/wav" and r.content[:4] == b"RIFF"


@pytest.mark.usefixtures("default_voice")
def test_an_amount_never_spoken_waits_for_sarvam_when_offline(api: TestClient) -> None:
    r = api.get("/voice/say/123400.wav")
    assert r.status_code == 503


def test_the_counter_asks_only_its_three_questions(api: TestClient) -> None:
    assert api.get("/voice/ask/sharma.wav").status_code == 404


@pytest.mark.parametrize("paise", [0, 1250, -500])
def test_only_whole_rupees_are_said_back(api: TestClient, paise: int) -> None:
    assert api.get(f"/voice/say/{paise}.wav").status_code == 404


def test_an_amount_is_spoken_by_sarvam_once_then_kept(
    api: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("SARVAM_OFFLINE", "0")
    monkeypatch.setenv("SARVAM_API_KEY", "not-a-real-key")
    monkeypatch.setenv("SARVAM_TTS_SPEAKER", "priya")
    monkeypatch.setattr(said, "LIVE", tmp_path)
    asked: list[tuple[str, str]] = []

    def fake_speak(text: str, *, key: str, voice: str) -> bytes:
        asked.append((text, voice))
        return b"RIFF fake wav"

    monkeypatch.setattr(sarvam, "speak", fake_speak)
    first = api.get("/voice/say/123400.wav")
    again = api.get("/voice/say/123400.wav")
    assert first.status_code == again.status_code == 200
    assert first.content == again.content == b"RIFF fake wav"
    assert asked == [(said.amount_words(123400), "priya")]
    assert said.amount_words(123400).endswith("रुपये")


def test_the_demo_clips_are_listed(api: TestClient) -> None:
    slugs = [c["slug"] for c in api.get("/voice/clips").json()]
    assert "do-sau" in slugs and "sharma-dhaai-sau" in slugs


# ── four Anubhavs (offline: our parser reads, our code decides) ──────────────


def anubhavs(api: TestClient) -> dict[str, str]:
    """tag -> customer id, for the seed's four Anubhavs."""
    book = api.get(f"/shops/{SHOP}/customers").json()
    return {c["tag"]: c["id"] for c in book if c["display_name"].startswith("Anubhav")}


def test_a_name_four_customers_have_asks_which_one(api: TestClient) -> None:
    h = hear(api, "Anubhav ko do sau bees")
    assert h["reader"] == "rules" and h["fallback"] == "offline"
    assert h["amount_paise"] == 22000
    assert h["who"]["kind"] == "ask" and h["who"]["why"] == "several"
    among = {p["customer_id"]: p["tag"] for p in h["who"]["among"]}
    assert among == {v: k for k, v in anubhavs(api).items()}


@pytest.mark.parametrize(
    ("said", "tag"),
    [
        ("Anubhav Shukla ko do sau bees", "Room 1006, B wing"),
        ("अनुभव शुक्ला को दो सौ बीस", "Room 1006, B wing"),
        ("Anubhav Jain ko teen sau", "Medical shop"),
    ],
)
def test_a_surname_or_a_room_picks_one_anubhav(
    api: TestClient, said: str, tag: str
) -> None:
    h = hear(api, said)
    assert h["who"]["kind"] == "picked", h["who"]
    assert h["who"]["person"]["customer_id"] == anubhavs(api)[tag]


def test_offline_a_room_number_is_an_amount_to_our_parser_so_it_asks(
    api: TestClient,
) -> None:
    """Our parser reads 204 and sau as two amounts, so it refuses rather than
    guess, and asks which Anubhav. Sarvam-105B tells a room from an amount."""
    h = hear(api, "204 wale Anubhav ko sau")
    assert (h["problem"], h["amount_paise"]) == ("unclear_amount", None)
    assert h["who"]["why"] == "several"


def test_the_anubhav_at_the_counter_is_the_one(api: TestClient) -> None:
    _, joined = join(api, "Anubhav")
    h = hear(api, "Anubhav ko do sau")
    assert h["who"]["how"] == "at_counter"
    assert h["who"]["person"]["scan_id"] == joined["scan_id"]


# ── online: Sarvam-105B reads, faked here; our checks are real ───────────────


@pytest.fixture
def sarvam_105b(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    """Voice online with a fake Sarvam-105B. Append the answers it should give."""
    monkeypatch.setenv("SARVAM_OFFLINE", "0")
    monkeypatch.setenv("SARVAM_API_KEY", "not-a-real-key")
    answers: list[dict[str, Any]] = []

    def fake(system: str, user: str, schema: Any, *, key: str, name: str) -> Any:
        assert "SHORTLIST" in system and json.loads(user)["transcript"]
        if not answers:
            raise sarvam.SarvamError("could not reach Sarvam: faked")
        return answers.pop(0)

    monkeypatch.setattr(sarvam, "chat_json", fake)
    return answers


def reading(**kw: Any) -> dict[str, Any]:
    return {
        "intent": "udhaar",
        "customer_id": None,
        "candidates": [],
        "amount_words": "do sau bees",
        "amount_rupees": 220,
        "person_words": "Anubhav Shukla",
        "reason": "",
    } | kw


def test_sarvam_reads_and_our_checks_pass_it(
    api: TestClient, sarvam_105b: list[dict[str, Any]]
) -> None:
    sarvam_105b.append(reading())
    h = hear(api, "Anubhav Shukla ko do sau bees de do")
    assert (h["reader"], h["fallback"], h["intent"]) == ("sarvam", None, "udhaar")
    assert h["amount_paise"] == 22000 and h["problem"] is None
    assert h["who"]["person"]["tag"] == "Room 1006, B wing"
    assert [(c["kind"], c["ok"]) for c in h["checks"]] == [
        ("amount_said", True),
        ("amount_read", True),
        ("person_said", True),
        ("person_fits", True),
    ]
    assert h["checks"][1]["says"] == "our parser reads “do sau bees” as ₹220 too"


def test_online_a_room_number_said_picks_one_anubhav(
    api: TestClient, sarvam_105b: list[dict[str, Any]]
) -> None:
    sarvam_105b.append(
        reading(amount_words="sau", amount_rupees=100, person_words="204 wale Anubhav")
    )
    h = hear(api, "204 wale Anubhav ko sau")
    assert h["amount_paise"] == 10000
    assert h["who"]["person"]["customer_id"] == anubhavs(api)["Room 204, A wing"]


def test_an_amount_sarvam_states_that_is_not_in_the_words_is_never_sent(
    api: TestClient, sarvam_105b: list[dict[str, Any]]
) -> None:
    sarvam_105b.append(reading(amount_words="teen sau", amount_rupees=300))
    h = hear(api, "Anubhav Shukla ko do sau bees de do")
    assert (h["problem"], h["amount_paise"], h["readback"]) == (
        "amount_not_said",
        None,
        None,
    )


def test_a_customer_sarvam_was_never_shown_is_refused(
    api: TestClient, sarvam_105b: list[dict[str, Any]]
) -> None:
    sarvam_105b.append(reading(customer_id="c99"))
    h = hear(api, "Anubhav Shukla ko do sau bees de do")
    assert (h["problem"], h["amount_paise"]) == ("invented_customer", None)


def test_a_payment_is_read_as_a_payment(
    api: TestClient, sarvam_105b: list[dict[str, Any]]
) -> None:
    sarvam_105b.append(
        reading(
            intent="payment",
            amount_words="do sau",
            amount_rupees=200,
            person_words="Sharma",
        )
    )
    h = hear(api, "Sharma ne do sau diye")
    assert (h["intent"], h["amount_paise"]) == ("payment", 20000)
    assert h["who"]["person"]["customer_id"] == SHARMA


def test_when_sarvam_does_not_answer_our_parser_reads(
    api: TestClient, sarvam_105b: list[dict[str, Any]]
) -> None:
    h = hear(api, "Sharma ko dhaai sau udhaar")
    assert (h["reader"], h["fallback"]) == ("rules", "no_answer")
    assert h["amount_paise"] == 25000 and h["who"]["person"]["customer_id"] == SHARMA


def test_a_new_customer_is_kept_in_devanagari_too(
    api: TestClient, tx: db.Conn, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SARVAM_OFFLINE", "0")
    monkeypatch.setenv("SARVAM_API_KEY", "not-a-real-key")
    monkeypatch.setattr(sarvam, "transliterate", lambda text, *, key: "कविता")
    _, joined = join(api, "Kavita")
    row = tx.execute(
        "SELECT name_hi FROM customers WHERE id = %s", (joined["customer_id"],)
    ).fetchone()
    assert row == ("कविता",)


def test_offline_a_new_customer_is_kept_by_the_roman_name(
    api: TestClient, tx: db.Conn
) -> None:
    _, joined = join(api, "Kavita")
    row = tx.execute(
        "SELECT name_hi FROM customers WHERE id = %s", (joined["customer_id"],)
    ).fetchone()
    assert row == (None,)


# ── she asks (the customer's own amount) ─────────────────────────────────────


def she_asks(
    api: TestClient, person: str, scan: str, rupees: int, note: str | None = None
) -> Any:
    return api.post(
        f"/scans/{scan}/ask",
        json={"person_id": person, "amount_rupees": rupees, "note": note},
    )


def he_answers(api: TestClient, scan: str, said: str, rupees: int | None = None) -> Any:
    return api.post(
        f"/shops/{SHOP}/scans/{scan}/answer",
        json={"answer": said, "amount_rupees": rupees},
    )


def test_her_ask_and_his_yes_are_agreed_by_both(api: TestClient, tx: db.Conn) -> None:
    person, joined = join(api)
    scan = joined["scan_id"]
    asked = she_asks(api, person, scan, 200, "atta and oil")
    assert asked.status_code == 200, asked.text
    assert asked.json()["state"] == "waiting" and asked.json()["asked_paise"] == 20000

    # The pop-up has it, and the Soundbox is told the amount.
    (row,) = api.get(f"/shops/{SHOP}/counter").json()["waiting"]
    assert (row["asked_paise"], row["asked_note"]) == (20000, "atta and oil")
    since = (clock.now() - timedelta(minutes=1)).isoformat()
    kinds = api.get(f"/shops/{SHOP}/events", params={"after": since}).json()["events"]
    assert any(e["kind"] == "asked" and e["amount_paise"] == 20000 for e in kinds)

    e = he_answers(api, scan, "yes").json()
    assert (e["amount_paise"], e["status"], e["note"]) == (
        20000,
        "confirmed",
        "atta and oil",
    )
    wording = tx.execute(
        "SELECT wording FROM acknowledgments WHERE entry_id = %s", (e["id"],)
    ).fetchone()
    assert wording is not None and wording[0].startswith("I'm taking ₹200 udhaar from")
    state = api.get(f"/scans/{scan}").json()
    assert (state["state"], state["answer"]) == ("recorded", "yes")
    assert api.get(f"/shops/{SHOP}/counter").json()["waiting"] == []


def test_his_no_writes_nothing(api: TestClient, tx: db.Conn) -> None:
    person, joined = join(api)
    scan = joined["scan_id"]
    she_asks(api, person, scan, 200)
    assert he_answers(api, scan, "no").status_code == 200
    assert api.get(f"/scans/{scan}").json()["state"] == "declined"
    assert api.get(f"/shops/{SHOP}/counter").json()["waiting"] == []
    assert record(api, scan_id=scan, amount_paise=20000).status_code == 409
    assert he_answers(api, scan, "yes").status_code == 409


def test_a_different_amount_waits_for_her_own_yes(api: TestClient) -> None:
    person, joined = join(api)
    scan = joined["scan_id"]
    she_asks(api, person, scan, 200, "atta and oil")
    e = he_answers(api, scan, "change", 150).json()
    assert (e["amount_paise"], e["status"], e["note"]) == (
        15000,
        "recorded",
        "atta and oil",
    )
    assert api.get(f"/scans/{scan}").json()["answer"] == "changed"


def test_the_keypad_with_her_amount_answers_her_ask(api: TestClient) -> None:
    person, joined = join(api)
    she_asks(api, person, joined["scan_id"], 200)
    e = record(api, scan_id=joined["scan_id"], amount_paise=20000).json()
    assert e["status"] == "confirmed"


def test_only_she_can_ask_on_her_scan(api: TestClient) -> None:
    _, joined = join(api)
    r = she_asks(api, str(uuid.uuid4()), joined["scan_id"], 200)
    assert r.status_code == 403


def test_an_ask_keeps_her_at_the_counter_for_ten_minutes(
    api: TestClient, tx: db.Conn
) -> None:
    person, joined = join(api)
    scan = joined["scan_id"]
    she_asks(api, person, scan, 200)
    tx.execute(
        "UPDATE scans SET scanned_at = scanned_at - interval '5 minutes', "
        "asked_at = asked_at - interval '5 minutes' WHERE id = %s",
        (scan,),
    )
    assert api.get(f"/scans/{scan}").json()["state"] == "waiting"
    assert len(api.get(f"/shops/{SHOP}/counter").json()["waiting"]) == 1
    tx.execute(
        "UPDATE scans SET asked_at = asked_at - interval '6 minutes' WHERE id = %s",
        (scan,),
    )
    assert api.get(f"/scans/{scan}").json()["state"] == "expired"
