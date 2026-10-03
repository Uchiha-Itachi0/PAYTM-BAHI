"""Memory's background work, a few seconds after the fact, in a thread of the API.

1. Read each new chat message from a customer (writer.read, Sarvam): a day he
   promises to pay by (kept with his own words) and one line worth remembering
   (a complaint, a hardship, a request), each with the message it came from.
2. Work out each customer's payment pattern again (pure arithmetic, once a
   minute) and keep it as a sentence where it changed.
3. Give each new memory and changed pattern to Cognee, as sentences that say who
   and when, so a question can find them by meaning later.
4. Take each forgotten memory, and each pattern's old copy, out of Cognee.

Nothing here is on the way of a reply: saving a note, sending a chat message and
Tonight all work from the book's own table, with or without this. When Cognee
fails, the worker waits a while before trying again, rather than spending
credits on a loop.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from collections.abc import Collection
from datetime import date, datetime

from bahi import clock, voice
from bahi.memory import cognee_client
from bahi.memory.cognee_client import Memory
from bahi.munshi import writer
from bahi.service import memory as keeping
from bahi.service import pattern
from bahi.service.errors import Conflict, NotFound
from bahi.store import customers, db, memories, profiles
from bahi.store.db import Conn
from bahi.store.memories import Kind
from bahi.store.memories import Memory as Kept

log = logging.getLogger(__name__)

#: How often it looks for work when there was none.
POLL_S = 3.0
#: After Cognee fails, how long before it is asked again.
BACK_OFF_S = 120.0
#: Per round: Cognee takes seconds a memory.
TO_STORE = 3
TO_READ = 10

#: How often each customer's pattern is worked out again (pure arithmetic).
PROFILE_EVERY_S = 60.0

_started = False
_start_lock = threading.Lock()
_quiet_until = 0.0
_profiled_at = -PROFILE_EVERY_S


def text_of(m: Kept) -> str:
    """The memory as Cognee is given it: who, when, what, and how long to wait."""
    # The book's own names, both scripts, so an answer says them as the book does.
    names = m.display_name + (f" / {m.name_hi}" if m.name_hi else "")
    who = names + (f" ({m.tag})" if m.tag else "")
    on = m.remembered_at.astimezone(clock.IST).strftime("%d %b %Y")
    until = f"{m.until:%d %b %Y}" if m.until else None
    if m.kind == "promise":
        return (
            f'Customer {who} wrote in chat on {on}: "{m.body}". '
            f"He promised to pay by {until}."
        )
    if m.kind == "nickname":
        return f'The shopkeeper calls customer {who} "{m.body}".'
    if m.kind == "said":
        return f"From customer {who}'s chat on {on}: {m.body}"
    wait = f" The shop stays quiet about his udhaar until {until}." if until else ""
    return f"The shopkeeper's note about customer {who}, on {on}: {m.body}{wait}"


def read_chat(con: Conn, now: datetime, limit: int = TO_READ) -> int:
    """Reads new customer messages for a promise and for anything worth
    remembering. The number read."""
    unread = memories.unread(con, limit)
    for u in unread:
        got = writer.read(u.body, now.astimezone(clock.IST).date())
        kept: list[tuple[Kind, str, date | None]] = []
        if got.pay_by is not None:  # a promise keeps his own words
            kept.append(("promise", u.body[:300], got.pay_by))
        if got.said is not None:
            kept.append(("said", got.said, None))
        for kind, body, until in kept:
            try:
                keeping.keep(
                    con,
                    u.shop_id,
                    u.customer_id,
                    kind,
                    body,
                    "customer",
                    now,
                    until=until,
                    message_id=u.message_id,
                )
            except (Conflict, NotFound) as e:
                log.info("not remembered: %s", e)
        memories.read(con, u.message_id, now)
    return len(unread)


def write_profiles(con: Conn, now: datetime, only: Collection[str] | None = None) -> int:
    """Each customer's payment pattern, as a sentence, where it changed. Pure
    arithmetic over the book (service/pattern.py): cheap. The number changed.
    `only`: just these customers (the live check)."""
    today = now.astimezone(clock.IST).date()
    changed = 0
    for (shop_id,) in con.execute("SELECT id::text FROM shops").fetchall():
        people = {c.id: c for c in customers.of_shop(con, shop_id)}
        for cid, p in pattern.of_shop(con, shop_id, today).items():
            c = people.get(cid)
            if c is None or (not p.entries and not p.rhythm.last_paid):
                continue
            if only is not None and cid not in only:
                continue
            who = c.display_name + (f" / {c.name_hi}" if c.name_hi else "")
            who += f" ({c.tag})" if c.tag else ""
            changed += profiles.write(con, shop_id, cid, pattern.sentence(p, who), now)
    return changed


def store_profiles(
    con: Conn, memory: Memory, now: datetime, limit: int = TO_STORE
) -> int:
    """Gives changed patterns to Cognee, then takes out the copy it had before."""
    todo = profiles.to_store(con, limit)
    for p in todo:
        cognee_id = memory.remember(p.shop_id, p.body, p.customer_id)
        if p.stale_cognee_id and p.stale_cognee_id != cognee_id:
            memory.forget(p.shop_id, p.stale_cognee_id)
        profiles.stored(con, p.customer_id, cognee_id, now)
    return len(todo)


def store(con: Conn, memory: Memory, now: datetime, limit: int = TO_STORE) -> int:
    """Gives new memories to Cognee. The number stored."""
    todo = memories.to_store(con, limit)
    for m in todo:
        cognee_id = memory.remember(m.shop_id, text_of(m), m.customer_id)
        memories.stored(con, m.id, cognee_id, now)
    return len(todo)


def unstore(con: Conn, memory: Memory, limit: int = TO_STORE) -> int:
    """Takes forgotten memories out of Cognee. The number taken out."""
    todo = memories.to_unstore(con, limit)
    for m in todo:
        assert m.cognee_id is not None
        shared = con.execute(
            "SELECT 1 FROM memories WHERE cognee_id = %s AND id <> %s"
            " AND forgotten_at IS NULL",
            (m.cognee_id, m.id),
        ).fetchone()
        if not shared:  # the same words kept twice are one item in Cognee
            memory.forget(m.shop_id, m.cognee_id)
        memories.unstored(con, m.id)
    return len(todo)


def run_once() -> int:
    """One round of all of it. The amount of work done."""
    global _quiet_until, _profiled_at
    done = 0
    with db.connect() as con:
        done += read_chat(con, clock.now())
        con.commit()
        if time.monotonic() - _profiled_at >= PROFILE_EVERY_S:
            write_profiles(con, clock.now())
            con.commit()
            _profiled_at = time.monotonic()
        memory = cognee_client.get()
        if memory is None or time.monotonic() < _quiet_until:
            return done
        try:
            done += store(con, memory, clock.now())
            con.commit()
            done += unstore(con, memory)
            con.commit()
            done += store_profiles(con, memory, clock.now())
            con.commit()
        except Exception:
            con.rollback()
            _quiet_until = time.monotonic() + BACK_OFF_S
            log.exception("Cognee failed; asking again in %.0f s", BACK_OFF_S)
    return done


#: After a round fails outright (the database not migrated, Postgres down).
FAILED_ROUND_WAIT_S = 60.0


def _loop() -> None:
    while True:
        try:
            done = run_once()
        except Exception:
            log.exception(
                "memory worker round failed; next in %.0f s (make db-migrate?)",
                FAILED_ROUND_WAIT_S,
            )
            time.sleep(FAILED_ROUND_WAIT_S)
            continue
        time.sleep(0.2 if done else POLL_S)


def start() -> bool:
    """Starts the worker once per process, when there is anything it can do:
    voice online to read promises. MEMORY_WORKER=off keeps it off (the tests)."""
    global _started
    if os.environ.get("MEMORY_WORKER", "on").lower() in ("off", "0", "false"):
        return False
    if voice.offline() or voice.api_key() is None:
        return False
    with _start_lock:
        if _started:
            return True
        threading.Thread(target=_loop, name="memory-worker", daemon=True).start()
        _started = True
    log.info("memory worker started; Cognee %s", "on" if cognee_client.get() else "off")
    return True
