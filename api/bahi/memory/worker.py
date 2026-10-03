"""Memory's background work, a few seconds after the fact, in a thread of the API.

1. Read each new chat message from a customer for a day he promises to pay by
   (writer.promise, Sarvam). A promise is remembered, with his own words and the
   message it came from; everything else is only marked read.
2. Give each new memory to Cognee, as a sentence that says who and when, so a
   question can find it by meaning later.
3. Take each forgotten one out of Cognee.

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
from datetime import datetime

from bahi import clock, voice
from bahi.memory import cognee_client
from bahi.memory.cognee_client import Memory
from bahi.munshi import writer
from bahi.service import memory as keeping
from bahi.service.errors import Conflict, NotFound
from bahi.store import db, memories
from bahi.store.db import Conn
from bahi.store.memories import Memory as Kept

log = logging.getLogger(__name__)

#: How often it looks for work when there was none.
POLL_S = 3.0
#: After Cognee fails, how long before it is asked again.
BACK_OFF_S = 120.0
#: Per round: Cognee takes seconds a memory.
TO_STORE = 3
TO_READ = 10

_started = False
_start_lock = threading.Lock()
_quiet_until = 0.0


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
    wait = f" The shop stays quiet about his udhaar until {until}." if until else ""
    return f"The shopkeeper's note about customer {who}, on {on}: {m.body}{wait}"


def read_chat(con: Conn, now: datetime, limit: int = TO_READ) -> int:
    """Reads new customer messages for promises. The number read."""
    unread = memories.unread(con, limit)
    for u in unread:
        day = writer.promise(u.body, now.astimezone(clock.IST).date())
        if day is not None:
            try:
                keeping.keep(
                    con,
                    u.shop_id,
                    u.customer_id,
                    "promise",
                    u.body[:300],
                    "customer",
                    now,
                    until=day,
                    message_id=u.message_id,
                )
            except (Conflict, NotFound) as e:
                log.info("not remembered as a promise: %s", e)
        memories.read(con, u.message_id, now)
    return len(unread)


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
    """One round of all three. The amount of work done."""
    global _quiet_until
    done = 0
    with db.connect() as con:
        done += read_chat(con, clock.now())
        con.commit()
        memory = cognee_client.get()
        if memory is None or time.monotonic() < _quiet_until:
            return done
        try:
            done += store(con, memory, clock.now())
            con.commit()
            done += unstore(con, memory)
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
