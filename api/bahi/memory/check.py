"""A live check of memory: real Sarvam, real OpenAI, real Cognee, on the check
databases only. `make memory-check`.

The tests fake Sarvam and Cognee (tests/test_memory.py). This runs the real
thing, end to end, the way the demo will:

1. The shopkeeper tells the munshi a note, with a day: Tonight holds him.
2. A customer writes a promise in chat: the worker reads it (Sarvam), Tonight
   holds him too.
3. The worker gives both to Cognee (Sarvam extracts, OpenAI embeds, Postgres
   keeps).
4. A customer's complaint is kept too, and each customer's payment pattern is
   written; all of it goes to Cognee.
5. Questions: who pays this week (Cognee), a customer's card with his note, when
   Patil will pay (a guess from his pattern), who complains (Cognee).
6. Forget takes the promise out of Cognee.

The book's changes are rolled back; Cognee's check database is wiped before
and after. It refuses to run against anything but *_check databases.
"""

from __future__ import annotations

import sys
import time
from typing import Any
from urllib.parse import urlparse, urlunparse

from bahi import clock, voice
from bahi.memory import cognee_client, settings, worker
from bahi.munshi import brain
from bahi.service import memory as keeping
from bahi.service import tonight
from bahi.store import db, memories, threads
from bahi.voice import sarvam
from data.world import HOME, uid

SHOP = str(uid("shop", HOME))
IQBAL = str(uid("customer", HOME, "iqbal"))
RAJU = str(uid("customer", HOME, "raju"))
PATIL = str(uid("customer", HOME, "patil"))
SALMA = str(uid("customer", HOME, "salma"))

failed: list[str] = []


def check(what: str, ok: bool, detail: Any = "") -> None:
    print(f"  {'✓' if ok else '✗'} {what}" + (f"  ({detail})" if detail else ""))
    if not ok:
        failed.append(what)


def check_url() -> str:
    url = settings.url()
    if url is None:
        sys.exit("needs MEMORY_DATABASE_URL in api/.env")
    u = urlparse(url)
    name = u.path.lstrip("/")
    return urlunparse(
        u._replace(path="/" + (name if name.endswith("_check") else name + "_check"))
    )


def main() -> None:
    if "check" not in db.url():
        sys.exit("run against the check database: DATABASE_URL=postgresql:///bahi_check")
    if not settings.enabled():
        sys.exit(
            "memory is off: needs SARVAM_OFFLINE=0, SARVAM_API_KEY and OPENAI_API_KEY"
        )
    key = voice.api_key()
    assert key is not None

    def chat(m: list[dict[str, Any]], t: list[dict[str, Any]]) -> dict[str, Any]:
        return sarvam.munshi(m, t, key=key)

    memory = cognee_client.Cognee(check_url())
    cognee_client.use(memory)
    started = time.monotonic()
    print("wiping the check memory…")
    memory.wipe()
    now = clock.now()

    with db.connect() as con:
        print("\n1. The shopkeeper's note")
        o = brain.talk(
            con,
            SHOP,
            None,
            "इकबाल भाई की सैलरी 10 तारीख को आती है, तब तक उन्हें याद मत दिलाना।",
            now,
            chat,
        )
        print(f"     मुंशी: {o.reply}   [{' | '.join(o.done)}]")
        notes = [m for m in memories.of_customer(con, IQBAL) if m.kind == "note"]
        check("the munshi kept a note for Iqbal", bool(notes))
        check(
            "with a day to stay quiet until, the 10th or after",
            bool(notes) and notes[0].until is not None and notes[0].until.day >= 10,
            notes[0].until if notes else None,
        )

        print("\n2. A customer's promise in chat")
        threads.post(con, RAJU, "customer", "text", "भैया 6 तारीख को पक्का दे दूँगा", now)
        worker.read_chat(con, now)
        promises = [m for m in memories.of_customer(con, RAJU) if m.kind == "promise"]
        check("Sarvam read Raju's promise", bool(promises))
        check(
            "for the 6th",
            bool(promises)
            and promises[0].until is not None
            and promises[0].until.day == 6,
            promises[0].until if promises else None,
        )

        e = tonight.work_out(con, SHOP, now)
        why = {p.display_name: p.why for p in e.tonight.plans}
        check(
            "Tonight holds Iqbal for the note", why.get("Iqbal bhai") == "asked_to_wait"
        )
        check("Tonight holds Raju for his promise", why.get("Raju") == "promised")
        check(
            "and still sends the other two",
            {p.display_name for p in e.tonight.sending} == {"Patil", "Salma"},
            sorted(p.display_name for p in e.tonight.sending),
        )

        print("\n3. What else a customer says, and how each pays")
        threads.post(
            con,
            SALMA,
            "customer",
            "text",
            "भैया तेल बहुत महंगा दे रहे हो, हर बार ज़्यादा लगाते हो",
            now,
        )
        worker.read_chat(con, now)
        said = [m for m in memories.of_customer(con, SALMA) if m.kind == "said"]
        check("Sarvam kept Salma's complaint", bool(said), said[0].body if said else None)
        wrote = worker.write_profiles(con, now, only={IQBAL, RAJU, PATIL, SALMA})
        check("their payment patterns written", wrote == 4, wrote)

        print("\n4. Into Cognee")
        t = time.monotonic()
        stored = 0
        while n := worker.store(con, memory, clock.now()):
            stored += n
        while n := worker.store_profiles(con, memory, clock.now()):
            stored += n
        check(f"stored {stored} in {time.monotonic() - t:.1f}s", stored >= 7)
        ids = [m.cognee_id for m in memories.of_shop(con, SHOP)]
        check("each has its own Cognee id", all(ids) and len(set(ids)) == len(ids))

        print("\n5. Asking")
        o = brain.talk(con, SHOP, None, "इस हफ़्ते कौन कौन पैसे देने वाला है?", now, chat)
        print(f"     मुंशी: {o.reply}   [{' | '.join(o.done)}]")
        check(
            "it worked it out or searched memory",
            any("Searched memory" in d or "likely to pay" in d for d in o.done),
        )
        check("and names Raju", "राजू" in (o.reply or "") or "Raju" in (o.reply or ""))
        o = brain.talk(con, SHOP, None, "इकबाल भाई का क्या सीन है?", now, chat)
        print(f"     मुंशी: {o.reply}   [{' | '.join(o.done)}]")
        check(
            "his card carries the note (the 10th)",
            any(t in (o.reply or "") for t in ("10", "दस")),
        )
        o = brain.talk(con, SHOP, None, "पाटिल कब तक पैसे देगा?", now, chat)
        print(f"     मुंशी: {o.reply}   [{' | '.join(o.done)}]")
        check("asked when Patil pays, it read his card", "Opened Patil's card" in o.done)
        check(
            "and gives it as a guess",
            "हिसाब" in (o.reply or "") or "लगता" in (o.reply or ""),
        )
        check(
            "without a date that has passed (September)",
            "सितंबर" not in (o.reply or "") or "आखिरी" in (o.reply or ""),
        )
        o = brain.talk(con, SHOP, None, "कौन सबसे ज़्यादा शिकायत करता है?", now, chat)
        print(f"     मुंशी: {o.reply}   [{' | '.join(o.done)}]")
        check(
            "asked who complains, it names Salma",
            "सलमा" in (o.reply or "") or "Salma" in (o.reply or ""),
        )

        print("\n6. Forget")
        if promises:
            keeping.forget(con, SHOP, promises[0].id, clock.now())
            worker.unstore(con, memory)
            found = memory.recall(SHOP, "राजू ने कब देने का वादा किया?")
            check("Raju's promise is gone from Cognee", "6 तारीख" not in found)
        con.rollback()

    memory.wipe()
    print(
        f"\n{'all good' if not failed else f'{len(failed)} failed'}"
        f" · {time.monotonic() - started:.0f}s"
    )
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
