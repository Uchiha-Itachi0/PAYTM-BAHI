"""The munshi, tested the way it is used: a shopkeeper with something to record.

Another model plays the shopkeeper, with a goal it keeps to itself ("₹200 udhaar
for Sharma, Room 19, B wing") and only answers what the munshi asks. The munshi
is the real one: the same brain, tools, checks and ledger, on the seeded book,
inside a transaction that is rolled back. Each run is scored on the end state,
the entry the book would hold, not on the munshi's words (the tau-bench method).

Costs Sarvam credits, so it runs on demand, never in `make check`:

    make munshi-eval            # every scenario twice
    uv run python -m bahi.munshi.eval 1 b_wing_names,doodh
"""

from __future__ import annotations

import sys
import time
from collections import Counter
from dataclasses import dataclass
from typing import Any

from bahi import clock, voice
from bahi.munshi import brain
from bahi.store import customers, db, memories
from bahi.store import munshi as store
from bahi.voice import sarvam
from data.world import HOME, uid

SHOP = str(uid("shop", HOME))
SIMULATOR = "sarvam-105b-conversations"
MOST_TURNS = 6

SHOPKEEPER = """You are playing a busy kirana shopkeeper in Mumbai, talking to your voice
munshi (assistant). Reply with only the words you say: short spoken Hindi in
Devanagari, a few words, as a speech recogniser would write them.
Your hidden goal: {goal}
Rules: answer only what the munshi asks; don't give every detail at once. When the
munshi reads back an entry that matches your goal exactly, say exactly: हाँ, लिख दो।
If anything in it is wrong, correct it briefly. {extra}"""


@dataclass(frozen=True, slots=True)
class Scenario:
    id: str
    first: str
    goal: str
    #: (customer as the book names them, kind, rupees), or None: nothing may be
    #: written. kind is udhaar, payment or correction.
    expect: tuple[str, str, int] | None
    extra: str = ""
    #: Names that must not be in the munshi's first reply: with three or more
    #: fitting, it says how many and asks before reading any out.
    unread: tuple[str, ...] = ()
    #: What he calls them, which his yes must leave remembered.
    nickname: str | None = None


B_WING = ("शर्मा", "आशा", "कामत", "राहुल", "रिजवान")

SCENARIOS = [
    Scenario(
        "b_wing_names",
        "बी विंग में जो रहते हैं, उनके नाम दो सौ लिख दो।",
        "udhaar ₹200 for Sharma, Room 19, B wing. You don't remember the name until "
        "you hear it.",
        ("Sharma", "udhaar", 200),
        "If the munshi offers to read out the names, say: हाँ, नाम बताओ।",
        unread=B_WING,
    ),
    Scenario(
        "b_wing_tell",
        "बी विंग में जो रहते हैं, उनके नाम दो सौ लिख दो।",
        "udhaar ₹200 for Sharma, Room 19, B wing.",
        ("Sharma", "udhaar", 200),
        "If the munshi offers to read out the names, say instead: नहीं, शर्मा जी को।",
        unread=B_WING,
    ),
    Scenario(
        "c_wing_ask",
        "सी विंग वाले को उधार देना है मुझे।",
        "udhaar ₹300 for Pawar, Room 17, C wing. You don't remember the name until "
        "you hear it.",
        ("Pawar", "udhaar", 300),
        "If the munshi offers to read out the names, say: हाँ, पढ़ दो।",
        unread=("पवार", "कदम", "सुनीता", "उषा", "कमला"),
    ),
    Scenario(
        "doodh",
        "दूध वाले भैया को तीन सौ लिख दो।",
        "udhaar ₹300 for the milk-van man (Yadav).",
        ("Yadav", "udhaar", 300),
    ),
    Scenario(
        "misheard",
        "पटर को दो सौ।",
        "udhaar ₹200 for Pawar, C wing.",
        ("Pawar", "udhaar", 200),
    ),
    Scenario(
        "not_in_book",
        "रमेश को पाँच सौ।",
        "udhaar ₹500 for Ramesh, a new customer who is NOT in the book yet.",
        None,
        "If the munshi says Ramesh is not in the book, say: अच्छा, रहने दो।",
    ),
    Scenario(
        "new_customer",
        "रमेश को पाँच सौ लिख दो।",
        "udhaar ₹500 for Ramesh, a NEW customer from Chawl 7 who is not in the book "
        "yet. You want him added.",
        ("Ramesh", "udhaar", 500),
        "If the munshi says Ramesh is not in the book, say: नया ग्राहक है, चॉल सात वाले।",
    ),
    Scenario(
        "nickname",
        "चिंटू को दो सौ रुपये का उधार।",
        "udhaar ₹200 for D'Souza of Chapel lane, whom you call चिंटू.",
        ("D'Souza", "udhaar", 200),
        "If the munshi says there is no चिंटू, or asks who that is, say: डिसूज़ा।",
        nickname="चिंटू",
    ),
    Scenario(
        "give_is_udhaar",
        "डिसूज़ा को सौ रुपये दे देना।",
        "udhaar ₹100 for D'Souza of Chapel lane: you are giving him goods on credit.",
        ("D'Souza", "udhaar", 100),
    ),
    Scenario(
        "take_back",
        "अनिल वाला डेढ़ सौ गलती से लिखा था, वो हटा दो।",
        "Take back Anil's ₹150 udhaar (Tailor shop): it was written by mistake, he "
        "took nothing. Nothing new is written and no money came in.",
        ("Anil", "removal", 150),
        "When the munshi reads back that Anil's ₹150 comes off, say: हाँ, हटा दो।",
    ),
    Scenario(
        "message",
        "शर्मा जी को बोल दो कल सुबह दुकान पे आ जाएं, उनका सामान आ गया है।",
        "Send Sharma (Room 19, B wing) a message from the shop: come tomorrow morning, "
        "their goods have arrived.",
        ("Sharma", "message", 0),
        "When the munshi reads the message back, say: हाँ, भेज दो।",
    ),
    Scenario(
        "details",
        "अनुभव शुक्ला actually सी विंग में रहते हैं, रूम 311।",
        "Change where Anubhav Shukla lives to Room 311, C wing. Nothing about money.",
        ("Anubhav Shukla", "details", 0),
        "When the munshi reads back the change, say: हाँ, बदल दो।",
    ),
    Scenario(
        "correction",
        "मिश्रा जी को चार सौ लिख दो।",
        "udhaar for Mishra ji (Room 9, B wing). You first said ₹400, but it was really "
        "₹300: when the munshi reads back ₹400, say नहीं नहीं, तीन सौ था।",
        ("Mishra ji", "udhaar", 300),
    ),
    Scenario(
        "fix_written",
        "शर्मा जी का दो सौ गलत लिख दिया था, डेढ़ सौ था। ठीक कर दो।",
        "Sharma (Room 19, B wing) already has ₹200 written, but it was really ₹150. "
        "You want that entry corrected, not a new one.",
        ("Sharma", "correction", 150),
    ),
    Scenario(
        "english",
        "Sharma took goods for 200, write it",
        "udhaar ₹200 for Sharma, Room 19, B wing. You speak English.",
        ("Sharma", "udhaar", 200),
        "When it matches, say exactly: हाँ, लिख दो।",
    ),
]


def shopkeeper(s: Scenario, said: list[tuple[str, str]], key: str) -> str:
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SHOPKEEPER.format(goal=s.goal, extra=s.extra)}
    ]
    for who, text in said:  # the munshi is the simulator's "user"
        messages.append(
            {"role": "assistant" if who == "shop" else "user", "content": text}
        )
    body = {"model": SIMULATOR, "temperature": 0, "messages": messages}
    reply = sarvam._post_json(sarvam.CHAT_URL, body, key=key, timeout=30)
    return str(reply["choices"][0]["message"].get("content") or "").strip()


def run(s: Scenario, key: str) -> dict[str, Any]:
    chat = lambda m, t: sarvam.munshi(m, t, key=key)  # noqa: E731
    with db.connect() as con:
        conversation: str | None = None
        said: list[tuple[str, str]] = []
        line, seconds, written, called = s.first, [], None, None
        for _ in range(MOST_TURNS):
            said.append(("shop", line))
            if "रहने दो" in line:
                break
            started = time.monotonic()
            o = brain.talk(con, SHOP, conversation, line, clock.now(), chat)
            seconds.append(time.monotonic() - started)
            conversation = o.conversation_id
            said.append(("munshi", o.reply or ""))
            if o.finished:
                break
            line = shopkeeper(s, said, key)
        d = store.latest_draft(con, conversation) if conversation else None
        if d is not None and d.status == "saved" and d.customer_id:
            c = customers.get(con, d.customer_id)
            written = (
                c.display_name if c else d.customer_id,
                d.kind,
                (d.amount_paise or 0) // 100,
            )
            nicks = memories.of_customer(con, d.customer_id)
            called = next((m.body for m in nicks if m.kind == "nickname"), None)
        con.rollback()
    first = next((text for who, text in said if who == "munshi"), "")
    early = [n for n in s.unread if n in first]
    return {
        "id": s.id,
        # A nickname the scenario names must be kept; one it doesn't name may be
        # kept too ("दूध वाले भैया" is what he calls Yadav), never a wrong one.
        "ok": written == s.expect
        and not early
        and (s.nickname is None or called == s.nickname),
        "early": early,
        "written": written,
        "called": called,
        "said": said,
        "s": seconds,
    }


#: Sarvam's rate limit: wait this long and run the scenario again, this often.
WAIT_S = 30.0
TRIES = 4


def patient(s: Scenario, key: str) -> dict[str, Any]:
    """The scenario, run again from the start after a rate limit, not lost."""
    for attempt in range(TRIES):
        try:
            return run(s, key)
        except sarvam.SarvamError as e:
            if "429" not in str(e) or attempt == TRIES - 1:
                raise
            time.sleep(WAIT_S)
    raise AssertionError("unreachable")


def main() -> None:
    key = voice.api_key()
    if key is None:
        sys.exit("needs SARVAM_API_KEY in api/.env")
    times = int(sys.argv[1]) if len(sys.argv) > 1 else 2
    only = set(sys.argv[2].split(",")) if len(sys.argv) > 2 else None
    results = [
        patient(s, key)
        for s in SCENARIOS
        if not only or s.id in only
        for _ in range(times)
    ]
    for r in results:
        early = f"  read before asking: {', '.join(r['early'])}" if r["early"] else ""
        called = f"  remembered: {r['called']}" if r["called"] else ""
        print(
            f"\n{'✓' if r['ok'] else '✗'} {r['id']}  written: {r['written']}"
            f"{called}{early}"
        )
        for who, text in r["said"]:
            print(f"   {'दुकानदार' if who == 'shop' else 'मुंशी'}: {text}")
    per = Counter(r["id"] for r in results if r["ok"])
    turn_s = sorted(x for r in results for x in r["s"])
    steady = sum(1 for s in {r["id"] for r in results} if per[s] == times)
    print(
        f"\n{sum(r['ok'] for r in results)}/{len(results)} right · "
        f"median reply {turn_s[len(turn_s) // 2]:.1f}s · "
        f"every run right: {steady}"
    )


if __name__ == "__main__":
    main()
