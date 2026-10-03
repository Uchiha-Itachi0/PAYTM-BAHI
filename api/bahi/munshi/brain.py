"""The munshi's loop: his words in, the munshi's reply out, tools in between.

Each request adds his turn, then asks the model what to do: call tools (run here,
one at a time, their results added) or reply. At most MAX_STEPS model calls per
turn; if it is still calling tools after that, it is asked to reply without them.
Every message is stored as it happens, so the next request, an audit or a replay
sees exactly what the model saw.

A tap on the card is his answer too. It is written into the conversation as his
turn, the save is done by code (the same `tools.save` the munshi's
confirm_entry uses), and the munshi is then asked what to say about it.
"""

from __future__ import annotations

import json
import re
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from bahi import clock
from bahi.munshi import prompt, tools
from bahi.service import ledger
from bahi.service.errors import Conflict
from bahi.store import munshi as store
from bahi.store.db import Conn
from bahi.store.munshi import Draft

#: Model calls per turn, tools included. Our tests needed at most three.
MAX_STEPS = 5

Chat = Callable[[list[dict[str, Any]], list[dict[str, Any]]], dict[str, Any]]

_THINKING = re.compile(r"<think>.*?</think>", re.S)
_MARKDOWN = re.compile(r"[*_#`]+")


@dataclass
class Outcome:
    conversation_id: str
    reply: str | None = None
    reply_turn_id: str | None = None
    #: The card to show: one waiting for his yes, or one decided this turn.
    draft: Draft | None = None
    #: A card was saved or taken away this turn.
    finished: bool = False
    #: What the munshi did this turn, for the screen.
    done: list[str] = field(default_factory=list)


def _clean(message: dict[str, Any]) -> dict[str, Any]:
    """What is kept of the model's message: no reasoning, no empty fields."""
    out: dict[str, Any] = {"role": "assistant", "content": message.get("content") or None}
    if message.get("tool_calls"):
        out["tool_calls"] = [
            {
                "id": tc.get("id") or f"call-{i}",
                "type": "function",
                "function": {
                    "name": tc.get("function", {}).get("name", ""),
                    "arguments": tc.get("function", {}).get("arguments") or "{}",
                },
            }
            for i, tc in enumerate(message["tool_calls"])
        ]
    return out


def spoken(text: str) -> str:
    """The reply as it will be shown and said: no stray reasoning or markdown."""
    return _MARKDOWN.sub("", _THINKING.sub("", text)).strip()


def talk(
    con: Conn,
    shop_id: str,
    conversation_id: str | None,
    text: str,
    now: datetime,
    chat: Chat,
    *,
    heard: str | None = None,
) -> Outcome:
    """His turn: typed text, or `heard` from the mic (then `text` is the same)."""
    if conversation_id is None:
        conversation_id = store.start(con, shop_id, now)
    store.add_turn(
        con, conversation_id, {"role": "user", "content": text}, now, heard=heard
    )
    return _answer(con, shop_id, conversation_id, now, chat)


def tap(
    con: Conn,
    shop_id: str,
    conversation_id: str,
    draft_id: str,
    yes: bool,
    now: datetime,
    chat: Chat,
) -> Outcome:
    """He tapped the card (or its countdown ran out): yes saves it, no takes it away.
    Code does it; the munshi is told, and says what happened."""
    said = "(कार्ड पर हाँ दबाया)" if yes else "(कार्ड पर नहीं दबाया)"
    store.add_turn(con, conversation_id, {"role": "user", "content": said}, now)
    done: list[str] = []
    if yes:
        result = tools.save(con, shop_id, draft_id, now, done)
        name = "confirm_entry"
    else:
        ok = store.decide(con, draft_id, "cancelled", now)
        result = {"ok": ok, "cancelled": ok}
        name = "cancel_entry"
        done.append("Took the card away")
    call_id = f"tap-{draft_id[:8]}"
    store.add_turn(
        con,
        conversation_id,
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": call_id,
                    "type": "function",
                    "function": {"name": name, "arguments": "{}"},
                }
            ],
        },
        now,
    )
    store.add_turn(
        con,
        conversation_id,
        {
            "role": "tool",
            "tool_call_id": call_id,
            "content": json.dumps(result, ensure_ascii=False),
        },
        now,
    )
    out = _answer(con, shop_id, conversation_id, now, chat)
    out.done = done + out.done
    decided = store.draft(con, draft_id)
    if decided is not None and decided.status in ("saved", "cancelled"):
        out.draft, out.finished = decided, True
    return out


def _answer(
    con: Conn, shop_id: str, conversation_id: str, now: datetime, chat: Chat
) -> Outcome:
    shop = ledger.shop(con, shop_id)
    desk = tools.Desk.open(con, shop_id, conversation_id, now)
    system = {
        "role": "system",
        "content": prompt.system(
            shop.name, desk.people, now.astimezone(clock.IST).date()
        ),
    }
    out = Outcome(conversation_id)
    before = store.latest_draft(con, conversation_id)
    waiting_before = before.id if before and before.status == "shown" else None
    for step in range(MAX_STEPS):
        history = [t.message for t in store.turns(con, conversation_id)]
        offered = tools.TOOLS if step < MAX_STEPS - 1 else []
        started = time.monotonic()
        message = _clean(chat([system, *history], offered))
        ms = round((time.monotonic() - started) * 1000)
        if not offered:
            message.pop("tool_calls", None)
        turn = store.add_turn(con, conversation_id, message, now, ms=ms)
        calls = message.get("tool_calls") or []
        if not calls:
            out.reply = spoken(str(message.get("content") or "")) or None
            out.reply_turn_id = turn.id
            break
        for tc in calls:
            try:
                args = json.loads(tc["function"]["arguments"] or "{}")
            except json.JSONDecodeError:
                args = None
            result = (
                desk.run(tc["function"]["name"], args)
                if isinstance(args, dict)
                else {"error": "the arguments were not JSON"}
            )
            store.add_turn(
                con,
                conversation_id,
                {
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": json.dumps(result, ensure_ascii=False),
                },
                now,
            )
    out.done = desk.done
    latest = store.latest_draft(con, conversation_id)
    if latest is not None and latest.status == "shown":
        out.draft = latest
    elif (
        latest is not None
        and latest.id == waiting_before
        and latest.status in ("saved", "cancelled")
    ):
        out.draft, out.finished = latest, True
    return out


def edit(
    con: Conn,
    shop_id: str,
    conversation_id: str,
    draft_id: str,
    now: datetime,
    *,
    amount_rupees: int | None = None,
    new_name: str | None = None,
    new_tag: str | None = None,
) -> Outcome:
    """He fixed the waiting card on screen. No model is asked: the card changes
    and the conversation records what he changed, so the munshi knows next turn.
    Nothing is written until his yes."""
    d, problem = tools.edit_card(
        con,
        shop_id,
        draft_id,
        now,
        amount_rupees=amount_rupees,
        new_name=new_name,
        new_tag=new_tag,
    )
    if d is None:
        raise Conflict(problem or "that card can't be changed")
    parts = []
    if d.new_name:
        parts.append(d.new_name + (f", {d.new_tag}" if d.new_tag else ""))
    if d.amount_paise is not None:
        parts.append(f"₹{d.amount_paise // 100}")
    said = "(कार्ड पर खुद बदला: " + " · ".join(parts) + ")"
    store.add_turn(con, conversation_id, {"role": "user", "content": said}, now)
    return Outcome(conversation_id, draft=d, done=["You changed the card"])
