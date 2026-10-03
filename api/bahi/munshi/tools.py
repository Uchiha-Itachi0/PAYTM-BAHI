"""The munshi's tools: what it can look up, and the only way it can change anything.

Reading tools look at the real book. `propose_entry` puts a draft card on the
screen, and it is checked here, in code:

- the customer came back from a search in this conversation, is in this shop, and
  has not been invited without saying yes;
- the amount is whole rupees above zero, and a जमा is no more than he owes;
- the card needs an explicit yes (no three-second countdown) when the name only
  sounded a little like his, the model picked him from several who fit (no
  search gave him back alone), the amount is ₹5,000 or more, or it is three
  times what he usually takes.

`propose_correction` puts the right amount for an entry already written on the
card; his yes records it as a new entry pointing at the wrong one, and the
customer confirms it. `propose_new_customer` puts someone who isn't in the book
yet on the card, only after a search found nobody by that name; his yes adds them
by name only, then writes the entry. `tonight` reads out tomorrow's reminders,
decided by code.

When three or more fit a search, `find_customer` says only how many. The names
come back when the munshi searches again with `read_names`, and only after the
shopkeeper has heard the count, in a later turn: he is always asked first.

`confirm_entry` turns the waiting card into the entry, once, and only after the
shopkeeper has answered it. Every result is plain JSON the munshi reads, and
tells it what to do next when that isn't obvious.

Customers are named to the munshi by the first six letters of their id: short
enough to copy without a slip, and looked up again here in this shop's book.
"""

from __future__ import annotations

import json
import logging
import statistics
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any
from uuid import UUID

from bahi import voice
from bahi.domain import book as book_domain
from bahi.domain import limitation
from bahi.domain.find import Found, find
from bahi.domain.money import rupees
from bahi.domain.who import Person
from bahi.memory import cognee_client
from bahi.service import ledger, pattern
from bahi.service import memory as keeping
from bahi.service import tonight as tonight_service
from bahi.service.errors import Conflict, NotFound
from bahi.store import book as book_store
from bahi.store import customers, entries, memories, scans
from bahi.store import munshi as store
from bahi.store.customers import CustomerRef
from bahi.store.db import Conn
from bahi.store.memories import Memory
from bahi.voice.said import amount_words

#: A card at or above this waits for an explicit yes.
LARGE_PAISE = 5_000_00
#: A card this many times his usual udhaar waits for an explicit yes.
UNUSUAL_TIMES = 3
#: His usual needs at least this many past entries.
USUAL_FROM = 3
#: Nothing this large is taken from a conversation at all.
MOST_PAISE = 1_00_000_00
#: A search lists at most this many.
LISTED = 8
SHORT = 6
#: A note the munshi keeps is at most this long; a nickname, this.
NOTE_CHARS = 300
NICKNAME_CHARS = 40
#: What a customer's card carries of what is remembered about them; and what a
#: recall reads when Cognee is off.
RECALLED = 5
RECALLED_ALL = 30

log = logging.getLogger(__name__)

#: The munshi's words for the two kinds. Not "जमा": that also means "deposit",
#: and "put it on his account" was read as one.
KIND = {"udhaar": "udhaar", "paid_back": "payment"}
KIND_HI = {"udhaar": "उधार", "payment": "जमा", "correction": "सुधार"}
#: How a search result says it only half fits.
WEAK_MATCHES = ("name sounds a little like it", "description partly fits")

TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "find_customer",
            "description": "Look up customers in the shop's book by name and/or "
            "description. Returns who fits, how well, and what to do next.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "The person's name or surname as heard, "
                        "e.g. 'शर्मा'. Only a name, never a place or work.",
                    },
                    "description": {
                        "type": "string",
                        "description": "Where they live or what they do, in the "
                        "book's words, e.g. 'B wing', 'Room 19', 'Pan stall'. Numbers as "
                        "digits.",
                    },
                    "read_names": {
                        "type": "boolean",
                        "description": "true only after the shopkeeper asked you to "
                        "read the names out (पढ़ दो, नाम बताओ, read them). When three "
                        "or more fit, the names come back only then.",
                    },
                    "skip": {
                        "type": "integer",
                        "description": "When he wants the rest of a list you are "
                        "reading out: how many of its names you have already read.",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "counter",
            "description": "Who is at the counter now: customers who scanned the shop's "
            "udhaar QR in the last few minutes.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "customer_card",
            "description": "What one customer owes, and how long since they last paid. "
            "Only when the shopkeeper asks about it.",
            "parameters": {
                "type": "object",
                "properties": {"customer_id": {"type": "string"}},
                "required": ["customer_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "propose_entry",
            "description": "Show the entry on the shopkeeper's screen for his yes. "
            "Only when exactly one customer, the amount and उधार-or-जमा are clear. "
            "Nothing is written yet.",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_id": {"type": "string"},
                    "kind": {
                        "type": "string",
                        "enum": ["udhaar", "paid_back"],
                        "description": "udhaar: the customer takes goods now and pays "
                        "later. paid_back: the customer handed money to the shop to "
                        "clear what he owes. If his words don't say which, ask first.",
                    },
                    "amount_rupees": {"type": "number"},
                    "called": {
                        "type": "string",
                        "description": "The name he used for them, only if it isn't "
                        "the book's name for them (a nickname, e.g. 'पप्पू'). His yes "
                        "to the card remembers it.",
                    },
                },
                "required": ["customer_id", "kind", "amount_rupees"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "propose_correction",
            "description": "An entry already written for this customer has the wrong "
            "amount: show the correction on his screen for his yes. Only when he says "
            "an earlier entry was wrong. Never write a new udhaar for a mistake. "
            "Nothing is written yet.",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_id": {"type": "string"},
                    "right_amount_rupees": {
                        "type": "number",
                        "description": "What the entry should have said.",
                    },
                    "wrong_amount_rupees": {
                        "type": "number",
                        "description": "What was written by mistake, if he said it.",
                    },
                },
                "required": ["customer_id", "right_amount_rupees"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "propose_new_customer",
            "description": "Put someone who is NOT in the book yet on the card, to add "
            "them by name only (and, with an amount, their first udhaar). Only after "
            "find_customer found nobody by this name and the shopkeeper wants them "
            "added. Nothing is written yet.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Their name in English letters, as the book "
                        "writes names, e.g. रमेश → Ramesh.",
                    },
                    "description": {
                        "type": "string",
                        "description": "Where they live or what they do, written "
                        "the way the book writes descriptions, e.g. 'Room 4, C wing' "
                        "for रूम नंबर चार विंग सी, or 'Chawl 7'. Empty if he didn't "
                        "say.",
                    },
                    "amount_rupees": {
                        "type": "number",
                        "description": "The udhaar he asked to write for them, if "
                        "he said one anywhere in this conversation (श्रेया को पाँच "
                        "सौ → 500). The card then adds them and writes it in one yes.",
                    },
                },
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "remember",
            "description": "Keep a note the shopkeeper tells you about a customer: "
            "when they get paid, how they pay, anything he asks you to remember. Not "
            "for money: udhaar and जमा are entries. If he asks BAHI to wait before "
            "reminding them, give until. The customer is never shown it.",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_id": {
                        "type": "string",
                        "description": "From find_customer.",
                    },
                    "note": {
                        "type": "string",
                        "description": "The note, short, in his words and language.",
                    },
                    "until": {
                        "type": "string",
                        "description": "YYYY-MM-DD: the last day to stay quiet about "
                        "their udhaar, when he asks to wait (salary on the 10th → the "
                        "10th). Leave out otherwise.",
                    },
                },
                "required": ["customer_id", "note"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "expected_payments",
            "description": "Who is likely to pay in the next few days, worked out now "
            "from the book: their own rhythm, their promises in chat, and your notes. "
            "For 'who pays this week?'. Never guess dates yourself.",
            "parameters": {
                "type": "object",
                "properties": {
                    "days": {
                        "type": "integer",
                        "description": "How many days ahead, from today. Default 7.",
                    }
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "recall",
            "description": "Search what BAHI remembers in this shop (his notes, "
            "customers' promises in chat, nicknames) by meaning, for a question like "
            "'who promised to pay this week?' or 'how does Kamla pay?'. For one "
            "customer's notes, customer_card has them already.",
            "parameters": {
                "type": "object",
                "properties": {"question": {"type": "string"}},
                "required": ["question"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "tonight",
            "description": "Who gets a reminder tomorrow and why, and how many are "
            "left alone. Decided by the book's own arithmetic. Only when he asks.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "confirm_entry",
            "description": "The shopkeeper said yes to the card on screen: write it "
            "and send it to the customer's phone. Returns what happened.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "cancel_entry",
            "description": "The shopkeeper said no to the card on screen: take it away.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
]


def short(customer_id: str) -> str:
    return customer_id.replace("-", "")[:SHORT]


@dataclass
class Desk:
    """One request's view of the shop, for the tools to work on."""

    con: Conn
    shop_id: str
    conversation_id: str
    now: datetime
    #: Seq of his latest turn. A card shown before it has been answered.
    his_seq: int
    #: Everything he has said in this conversation, for the entry's spoken_text.
    his_words: str
    refs: dict[str, CustomerRef] = field(default_factory=dict)
    people: list[Person] = field(default_factory=list)
    #: Customer ids a search or the counter has shown the munshi, and whether
    #: only by a weak match.
    seen: dict[str, bool] = field(default_factory=dict)
    #: A search has been made in this conversation.
    searched: bool = False
    #: Who was in each search of three or more whose count he has already been
    #: told, before his latest turn: only those names can be read out now.
    told: set[frozenset[str]] = field(default_factory=set)
    #: Customers some search, or the counter, gave back alone. Anyone else on a
    #: card was picked from several, by the model, and waits for a clear yes.
    alone: set[str] = field(default_factory=set)
    #: What happened, for the screen: "Looked for 'B wing': 8".
    done: list[str] = field(default_factory=list)

    @classmethod
    def open(cls, con: Conn, shop_id: str, conversation_id: str, now: datetime) -> Desk:
        turns = store.turns(con, conversation_id)
        his = [t for t in turns if t.role == "user"]
        desk = cls(
            con,
            shop_id,
            conversation_id,
            now,
            his_seq=his[-1].seq if his else -1,
            his_words=" · ".join(
                str(t.message.get("content") or "")
                for t in his
                if t.message.get("content")
            )[-400:],
        )
        desk.refs = {
            c.id: c for c in customers.of_shop(con, shop_id) if c.joined != "invited"
        }
        desk.people = [
            Person(c.id, c.display_name, c.tag, c.name_hi, c.tag_hi)
            for c in desk.refs.values()
        ]
        for t in turns:
            if t.role == "tool":
                desk._remember(t.message.get("content"), before=t.seq < desk.his_seq)
        return desk

    def _remember(self, content: Any, *, before: bool) -> None:
        try:
            result = json.loads(content) if isinstance(content, str) else None
        except json.JSONDecodeError:
            return
        if not isinstance(result, dict):
            return
        if "looked_for" in result:
            self.searched = True
            asked = result["looked_for"] or {}
            if before and "customers" not in result and result.get("count", 0) >= 3:
                self.told.add(self._who(asked.get("name"), asked.get("description")))
        rows = result.get("customers", []) or []
        for c in rows:
            cid = self.resolve(str(c.get("id", "")))
            if cid:
                weak = c.get("match") in WEAK_MATCHES
                self.seen[cid] = self.seen.get(cid, True) and weak
                if len(rows) == 1 and result.get("count") == 1:
                    self.alone.add(cid)

    def _who(self, name: str | None, description: str | None) -> frozenset[str]:
        return frozenset(f.person.ref for f in find(self.people, name, description).found)

    def resolve(self, given: str) -> str | None:
        """A short id (or a full one) back to the customer's id, in this shop only."""
        given = given.strip().lower().replace("-", "")
        if len(given) < SHORT:
            return None
        hits = [cid for cid in self.refs if cid.replace("-", "").startswith(given)]
        return hits[0] if len(hits) == 1 else None

    # ── the tools ────────────────────────────────────────────────────────────

    def run(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        tools: dict[str, Callable[..., dict[str, Any]]] = {
            "find_customer": self.find_customer,
            "counter": self.counter,
            "customer_card": self.customer_card,
            "propose_entry": self.propose_entry,
            "propose_correction": self.propose_correction,
            "propose_new_customer": self.propose_new_customer,
            "tonight": self.tonight,
            "remember": self.remember,
            "recall": self.recall,
            "expected_payments": self.expected_payments,
            "confirm_entry": self.confirm_entry,
            "cancel_entry": self.cancel_entry,
        }
        tool = tools.get(name)
        if tool is None:
            return {"error": f"there is no tool {name}"}
        try:
            return tool(**args)
        except TypeError as e:
            return {"error": f"wrong arguments for {name}: {e}"}

    def _say(self, cid: str) -> tuple[str, str]:
        c = self.refs[cid]
        return c.name_hi or c.display_name, c.tag_hi or c.tag or ""

    def _owes(self, cid: str) -> tuple[int, int | None]:
        """(what he owes in paise, days since he last paid), from the book's own
        arithmetic."""
        for c in book_store.load(self.con, self.shop_id):
            if c.id == cid:
                ln = book_domain.line(c, self.now.date())
                return (ln.balance_paise, ln.day) if ln else (0, None)
        return 0, None

    def _counter_ids(self) -> set[str]:
        return {w.customer_id for w in scans.waiting(self.con, self.shop_id, self.now)}

    def find_customer(
        self,
        name: str | None = None,
        description: str | None = None,
        read_names: bool = False,
        skip: int = 0,
    ) -> dict[str, Any]:
        search = find(self.people, name, description)
        here = self._counter_ids()
        found = search.found
        self.searched = True
        out: dict[str, Any] = {
            "looked_for": {"name": name, "description": description},
            "count": len(found),
        }
        looked = " · ".join(x for x in (name, description) if x)
        if not found and name:
            called = self._called(name, description)
            if called is not None:
                self.done.append(f"Looked for {looked}: a name you've used before")
                return called
        asked = read_names is True or str(read_names).lower() == "true"
        who = frozenset(f.person.ref for f in found)
        if len(found) >= 3 and not (asked and who in self.told):
            # The shopkeeper's rule: with three or more, say how many and let him
            # choose. The names come back only once he has heard the count and
            # answered it, in a later turn, so they can't be read out before he
            # asks, whatever the model decides.
            out["next"] = (
                f"{len(found)} fit. Say only how many, and ask: नाम बताऊँ, या आप "
                "बताएँगे किसके लिए? Then wait for his answer. If he wants the "
                "names, call find_customer again with the same words and read_names "
                "true. If he says a name or a place, look that up."
            )
            if asked:
                out["names"] = "not yet: he hasn't been asked"
            self.done.append(f"Looked for {looked}: {len(found)} found")
            return out

        def row(f: Found) -> dict[str, Any]:
            cid = f.person.ref
            said, about = self._say(cid)
            r: dict[str, Any] = {"id": short(cid), "name": said, "about": about}
            if f.name_score:
                r["match"] = (
                    "name sounds the same"
                    if f.name_strong
                    else "name sounds a little like it"
                )
            elif f.fits:
                r["match"] = (
                    "description fits" if f.fits >= 1 else "description partly fits"
                )
            if cid in here:
                r["at_counter"] = True
            # What he owes is only in customer_card, asked for on purpose: a search
            # said aloud at the counter must not carry anyone's balance.
            return r

        # Three or more reach here only when he asked for the names: a page of
        # LISTED at a time, how many are left said after it, and the next page
        # starts after the last name read.
        first = min(max(_whole(skip), 0), len(found)) if len(found) >= 3 else 0
        shown = found[first : first + LISTED]
        left = len(found) - first - len(shown)
        out["customers"] = [row(f) for f in shown]
        if len(found) == 1:
            self.alone.add(found[0].person.ref)
        for f in shown:
            weak = not f.strong
            self.seen[f.person.ref] = self.seen.get(f.person.ref, True) and weak
        if len(found) >= 3:
            out["reading"] = f"{first + 1} to {first + len(shown)} of {len(found)}"
        if left:
            out["more"] = left
        if search.note:
            out["note"] = search.note
        if len(found) == 1 and not found[0].strong:
            out["next"] = (
                "Only a weak match: say his name and place back and ask if that's "
                "who he means."
            )
        elif len(found) == 2:
            out["next"] = "Two fit: name both with what tells them apart, and ask which."
        elif not found:
            out["next"] = (
                "Nobody fits. Say so plainly and ask who he means. Speech can "
                "mishear a letter or a number (वी for बी): if a description in the "
                "book sounds like his words, ask whether he meant that one. If he "
                "says they are new, offer to add them with propose_new_customer."
            )
        elif left:
            out["next"] = (
                f"He asked for the names: read these {len(shown)}, each with its "
                "place only, never what they owe. Then say there are "
                f"{left} more names, and ask which one or whether to read more. If "
                "he wants more, call find_customer again with the same words, "
                f"read_names true and skip {first + len(shown)}: the next ones, "
                "after the last name you read."
            )
        elif len(found) >= 3:
            out["next"] = (
                "He asked for the names: read each with its place only, never what "
                "they owe, then ask which one."
                + (" These are the last of them." if first else "")
            )
        self.done.append(f"Looked for {looked}: {len(found)} found")
        return out

    def counter(self) -> dict[str, Any]:
        waiting = scans.waiting(self.con, self.shop_id, self.now)
        rows = []
        rows_of = [w.customer_id for w in waiting if w.customer_id in self.refs]
        for w in waiting:
            if w.customer_id in self.refs:
                said, about = self._say(w.customer_id)
                rows.append({"id": short(w.customer_id), "name": said, "about": about})
                self.seen[w.customer_id] = False
        self.done.append(f"Checked the counter: {len(rows)} waiting")
        out: dict[str, Any] = {"count": len(rows), "customers": rows}
        if len(rows) == 1:
            self.alone.update(rows_of)
            out["next"] = "One person is at the counter; if he named nobody, it is them."
        return out

    def customer_card(self, customer_id: str) -> dict[str, Any]:
        cid = self.resolve(customer_id)
        if cid is None:
            return {"error": "no such customer here; use an id from find_customer"}
        said, about = self._say(cid)
        owed, day = self._owes(cid)
        self.done.append(f"Opened {self.refs[cid].display_name}'s card")
        out: dict[str, Any] = {
            "name": said,
            "about": about,
            "owes": amount_words(owed) if owed else "कुछ बाकी नहीं",
            "days_since_last_paid": day,
        }
        kept = memories.of_customer(self.con, cid)
        told = sum(1 for m in kept if m.kind == "said")
        p = pattern.of_customer(self.con, self.shop_id, cid, self.now.date())
        out["how_they_pay"] = pattern.facts(p, told)
        if kept:
            out["remembered"] = [_remembered(m) for m in kept[:RECALLED]]
        out["next"] = (
            "Answer only what he asked: what they owe, if that is all he asked. Only "
            "when he asks when they will pay, or what kind of customer they are, use "
            "how_they_pay: a guess (मेरे हिसाब से…) with the reason in a few words, "
            "never a promise. Owing nothing, there is nothing to expect. Their "
            "promise, or a note about when they get money, outranks their rhythm. "
            "Never give a date that has passed. If something remembered bears on "
            "it, say it as said (आपने बताया था…, उन्होंने लिखा था…)."
        )
        return out

    def propose_entry(
        self,
        customer_id: str,
        kind: str,
        amount_rupees: float,
        called: str | None = None,
    ) -> dict[str, Any]:
        cid = self.resolve(customer_id)
        if cid is None:
            return {
                "ok": False,
                "problem": "no such customer here; look them up with find_customer",
            }
        if cid not in self.seen:
            return {
                "ok": False,
                "problem": "look this customer up with find_customer first",
            }
        kind_en = KIND.get(kind)
        if kind_en is None:
            return {"ok": False, "problem": "kind must be udhaar or paid_back; ask him"}
        paise, problem = _paise(amount_rupees)
        if problem is not None:
            return {"ok": False, "problem": problem}
        owed, _ = self._owes(cid)
        if kind_en == "payment" and paise > owed:
            words = amount_words(owed) if owed else "कुछ नहीं"
            return {
                "ok": False,
                "problem": f"he owes only {words}; tell the shopkeeper and ask",
            }
        reasons = []
        if self.seen.get(cid):
            reasons.append("weak_match")
        elif cid not in self.alone:
            reasons.append("one_of_several")
        if paise >= LARGE_PAISE:
            reasons.append("large")
        usual = self._usual(cid)
        if kind_en == "udhaar" and usual and paise >= UNUSUAL_TIMES * usual:
            reasons.append("unusual")
        store.show(
            self.con,
            self.conversation_id,
            cid,
            kind_en,
            paise,
            self.his_words or None,
            reasons,
            self.his_seq,
            self.now,
            called=self._nickname(cid, called),
        )
        said, about = self._say(cid)
        self.done.append(
            f"Showed a card: {self.refs[cid].display_name} ₹{paise // 100} "
            f"{KIND_HI[kind_en]}"
        )
        return {
            "ok": True,
            "card": f"{said}, {about}, {amount_words(paise)} {KIND_HI[kind_en]}",
            "needs_clear_yes": bool(reasons),
            "next": "The card is waiting for his yes. Read it back in one short "
            "sentence and ask पक्का?",
        }

    def propose_correction(
        self,
        customer_id: str,
        right_amount_rupees: float,
        wrong_amount_rupees: float | None = None,
    ) -> dict[str, Any]:
        cid = self.resolve(customer_id)
        if cid is None or cid not in self.seen:
            return {"ok": False, "problem": "look this customer up with find_customer"}
        right, problem = _paise(right_amount_rupees)
        if problem is not None:
            return {"ok": False, "problem": problem}
        today = self.now.date()
        open_ = [
            e
            for e in reversed(entries.of_customer(self.con, cid))
            if e.status in ("recorded", "confirmed", "disputed")
            and not limitation.expired(
                e.recorded_at.date(),
                e.acknowledged_at.date() if e.acknowledged_at else None,
                today,
            )
        ]
        fixable = [e for e in open_ if e.paid_paise == 0]

        def listed() -> list[dict[str, Any]]:
            return [
                {"amount": amount_words(e.amount_paise), "on": f"{e.recorded_at:%d %b}"}
                for e in open_[:LISTED]
            ]

        if wrong_amount_rupees is not None:
            wrong, problem = _paise(wrong_amount_rupees)
            if problem is not None:
                return {"ok": False, "problem": problem}
            hits = [e for e in fixable if e.amount_paise == wrong]
            if not hits:
                paid = [e for e in open_ if e.amount_paise == wrong]
                return {
                    "ok": False,
                    "problem": "part of that entry is already paid, so it can't be "
                    "corrected; ask whether to write the difference instead"
                    if paid
                    else f"no open entry of {amount_words(wrong)} for this customer; "
                    "tell him which entries there are and ask which one",
                    "open_entries": listed(),
                }
            e = hits[0]
        elif len(fixable) == 1:
            e = fixable[0]
        else:
            return {
                "ok": False,
                "problem": "nothing open to correct for this customer"
                if not fixable
                else "more than one entry is open: ask which amount was wrong",
                "open_entries": listed(),
            }
        if right == e.amount_paise:
            return {"ok": False, "problem": "that is already what the entry says; ask"}
        store.show(
            self.con,
            self.conversation_id,
            cid,
            "correction",
            right,
            self.his_words or None,
            ["correction"],
            self.his_seq,
            self.now,
            corrects=e.id,
        )
        said, about = self._say(cid)
        self.done.append(
            f"Showed a card: correct {self.refs[cid].display_name} "
            f"₹{e.amount_paise // 100} → ₹{right // 100}"
        )
        return {
            "ok": True,
            "card": f"{said}, {about}: {amount_words(e.amount_paise)} की जगह "
            f"{amount_words(right)}",
            "needs_clear_yes": True,
            "next": "The correction is waiting for his yes. Read back the wrong and "
            "the right amount in one short sentence and ask पक्का?",
        }

    def propose_new_customer(
        self,
        name: str,
        description: str | None = None,
        amount_rupees: float | None = None,
    ) -> dict[str, Any]:
        name = (name or "").strip()
        tag = (description or "").strip() or None
        if not name or len(name) > 40:
            return {"ok": False, "problem": "say the new customer's name"}
        if not self.searched:
            return {"ok": False, "problem": "look them up with find_customer first"}
        # Someone already in the book by that name is asked about, never doubled.
        same = [f for f in find(self.people, name, None).found if f.name_strong]
        if same:
            rows = []
            for f in same[:LISTED]:
                said, about = self._say(f.person.ref)
                rows.append({"id": short(f.person.ref), "name": said, "about": about})
                self.seen[f.person.ref] = False
            return {
                "ok": False,
                "problem": "someone in the book already has this name: ask if it's "
                "them before adding anyone",
                "customers": rows,
            }
        paise: int | None = None
        if amount_rupees is not None:
            paise, problem = _paise(amount_rupees)
            if problem is not None:
                return {"ok": False, "problem": problem}
        reasons = ["new_customer"]
        if paise is not None and paise >= LARGE_PAISE:
            reasons.append("large")
        store.show(
            self.con,
            self.conversation_id,
            None,
            "customer" if paise is None else "udhaar",
            paise,
            self.his_words or None,
            reasons,
            self.his_seq,
            self.now,
            new_name=name,
            new_tag=tag,
        )
        what = f"New customer {name}" + (f", {tag}" if tag else "")
        if paise is not None:
            what += f", {amount_words(paise)} उधार"
        self.done.append(
            f"Showed a card: new customer {name}"
            + (f" ₹{paise // 100} उधार" if paise is not None else "")
        )
        return {
            "ok": True,
            "card": what,
            "needs_clear_yes": True,
            "next": "The card is waiting for his yes. Read it back: the name, where "
            "they live"
            + (", and the udhaar" if paise is not None else "")
            + ", and ask पक्का?"
            + (
                ""
                if paise is not None
                else " If he asked for an amount for them earlier, call "
                "propose_new_customer again with amount_rupees first."
            ),
        }

    def tonight(self) -> dict[str, Any]:
        e = tonight_service.work_out(self.con, self.shop_id, self.now)
        t = e.tonight
        sending, stopped = [], []
        for p in t.sending:
            said, about = self._say(p.customer_id)
            r = e.reminders.get(p.customer_id)
            if r is not None and r.status == "stopped":
                stopped.append({"name": said, "about": about})
                continue
            sending.append(
                {
                    "name": said,
                    "about": about,
                    "days_since_last_paid": p.day,
                    "longest_gap_before": p.rhythm.max_gap,
                }
            )
        waiting = []
        for p in t.plans:
            if p.wait is not None:
                said, about = self._say(p.customer_id)
                waiting.append(
                    {
                        "name": said,
                        "about": about,
                        "why": "they promised in chat"
                        if p.wait.said_by == "customer"
                        else "your note",
                        "said": p.wait.body,
                        "quiet_until": p.wait.until.isoformat(),
                    }
                )
        self.done.append(f"Worked out tomorrow: {len(sending)} of {t.owing_count}")
        out: dict[str, Any] = {
            "reminders_tomorrow": sending,
            "owing": t.owing_count,
            "left_alone": t.owing_count - len(sending),
            "next": "Say how many get a reminder and who, each with one short reason "
            "(past the longest gap they've ever had). Everyone else is inside their "
            "own rhythm and gets nothing. Never say amounts. The list is on the "
            "Tomorrow screen, where he can stop any of them.",
        }
        if stopped:
            # He stopped these himself on the Tomorrow screen.
            out["stopped_by_shopkeeper"] = stopped
        if waiting:
            # Past their gap, but held for what was said: say who and why.
            out["held_for_what_was_said"] = waiting
        return out

    def remember(
        self, customer_id: str, note: str, until: str | None = None
    ) -> dict[str, Any]:
        cid = self.resolve(customer_id)
        if cid is None or cid not in self.seen:
            return {"ok": False, "problem": "look this customer up with find_customer"}
        note = (note or "").strip()
        if not note or len(note) > NOTE_CHARS:
            return {"ok": False, "problem": f"the note must be 1 to {NOTE_CHARS} letters"}
        day: date | None = None
        if until:
            try:
                day = date.fromisoformat(str(until).strip())
            except ValueError:
                return {"ok": False, "problem": "until must be a date, YYYY-MM-DD"}
        try:
            keeping.keep(
                self.con, self.shop_id, cid, "note", note, "shop", self.now, until=day
            )
        except (Conflict, NotFound) as e:
            return {"ok": False, "problem": f"{e}; ask him"}
        name = self.refs[cid].display_name
        self.done.append(
            f"Remembered about {name}" + (f", quiet until {day:%d %b}" if day else "")
        )
        return {
            "ok": True,
            "remembered": note,
            "quiet_until": day.isoformat() if day else None,
            "next": "Say in one short sentence that you'll remember it (याद रख लिया), "
            "and until when BAHI stays quiet, if he gave a day. Never tell the "
            "customer.",
        }

    def expected_payments(self, days: int = 7) -> dict[str, Any]:
        days = min(max(_whole(days) or 7, 1), 31)
        today = self.now.date()
        end = today + timedelta(days=days)
        owing = {
            c.id: ln
            for c in book_store.load(self.con, self.shop_id)
            if (ln := book_domain.line(c, today)) is not None and ln.balance_paise > 0
        }
        waiting = memories.waits(self.con, self.shop_id, today)
        promised, due, late = [], [], []
        for cid, p in pattern.of_shop(self.con, self.shop_id, today).items():
            if cid not in owing or cid not in self.refs:
                continue
            said, about = self._say(cid)
            who = {"name": said, "about": about}
            wait = waiting.get(cid)
            if wait is not None and wait.until is not None and wait.until >= today:
                who["note"] = f"{wait.body} (quiet until {wait.until:%d %b})"
            if p.promised and p.promised <= end:
                promised.append({**who, "promised_by": f"{p.promised:%d %b}"})
            elif p.now == "due" or (
                p.now == "early" and p.expect_from and p.expect_from <= end
            ):
                assert p.expect_from and p.expect_by
                due.append(
                    {
                        **who,
                        "usual_window": f"{p.expect_from:%d %b} to {p.expect_by:%d %b}",
                    }
                )
            elif p.now == "late":
                late.append({**who, "days_since_paid": p.rhythm.day})
        self.done.append(f"Worked out who is likely to pay in {days} days")
        return {
            "from": f"{today:%d %b}",
            "to": f"{end:%d %b}",
            "promised_in_chat": promised[:LISTED],
            "due_by_their_rhythm": due[:LISTED],
            "late_by_their_rhythm": late[:LISTED],
            "next": "Say who is likely, in one or two sentences: promises first, then "
            "those due by their rhythm; mention the late ones briefly. Names and "
            "places only, never amounts. It is a guess from the book, and you say so.",
        }

    def recall(self, question: str) -> dict[str, Any]:
        question = (question or "").strip()
        if not question:
            return {"error": "ask a question"}
        found, how = "", "cognee"
        memory = cognee_client.get()
        if memory is not None:
            try:
                found = memory.recall(self.shop_id, question)
            except Exception as e:  # noqa: BLE001 - the book's own list is next
                log.warning("Cognee couldn't recall: %s", e)
                memory = None
        if memory is None:
            # Cognee is off or failed: what this shop remembers, as kept.
            how = "the book's list"
            found = "\n".join(
                f"{m.display_name}: {_remembered(m)['said']}"
                for m in memories.of_shop(self.con, self.shop_id)[:RECALLED_ALL]
            )
        self.done.append(f"Searched memory: {question}")
        return {
            "found": found or "nothing remembered about that",
            "searched": how,
            "next": "Answer from what was found only, in one or two short sentences. "
            "If it doesn't answer him, say you don't remember that.",
        }

    def _called(self, name: str, description: str | None) -> dict[str, Any] | None:
        """Nobody in the book has this name, but he has called someone this before
        and said yes to the card: that person, as a hint to say back, never as
        proof. The card for them waits for his clear yes (a weak match)."""
        nicks = [
            m
            for m in memories.of_shop(self.con, self.shop_id, "nickname")
            if m.customer_id in self.refs
        ]
        if not nicks:
            return None
        by_nick = [Person(m.id, m.body, None, m.body, None) for m in nicks]
        hits = {f.person.ref for f in find(by_nick, name, None).found}
        matched = [m for m in nicks if m.id in hits]
        if description:  # what else he said about them must fit too
            fits = {f.person.ref for f in find(self.people, None, description).found}
            matched = [m for m in matched if m.customer_id in fits]
        if not matched:
            return None
        rows = []
        for m in matched[:LISTED]:
            said, about = self._say(m.customer_id)
            rows.append(
                {
                    "id": short(m.customer_id),
                    "name": said,
                    "about": about,
                    "match": f"you have called them {m.body} before",
                }
            )
            self.seen[m.customer_id] = True  # weak: he must say it's them
        return {
            "looked_for": {"name": name, "description": description},
            "count": len(rows),
            "customers": rows,
            "next": "Nobody in the book is named that, but he has called this person "
            "that before. Say the book's name and place back and ask if that's who "
            "he means.",
        }

    def _nickname(self, cid: str, called: str | None) -> str | None:
        """The name he used, if it is a name the book doesn't already have."""
        called = (called or "").strip()
        if not called or len(called) > NICKNAME_CHARS:
            return None
        c = self.refs[cid]
        own = {x.casefold() for x in (c.display_name, c.name_hi) if x}
        return None if called.casefold() in own else called

    def _usual(self, cid: str) -> int | None:
        past = [e.amount_paise for e in entries.of_customer(self.con, cid)]
        return int(statistics.median(past)) if len(past) >= USUAL_FROM else None

    def confirm_entry(self) -> dict[str, Any]:
        d = store.latest_draft(self.con, self.conversation_id)
        if d is None or d.status != "shown":
            return {"ok": False, "problem": "there is no card waiting; propose one first"}
        if d.shown_seq >= self.his_seq:
            return {
                "ok": False,
                "problem": "he hasn't answered the card yet; read it back and ask पक्का?",
            }
        return save(self.con, self.shop_id, d.id, self.now, self.done)

    def cancel_entry(self) -> dict[str, Any]:
        d = store.latest_draft(self.con, self.conversation_id)
        if d is None or d.status != "shown":
            return {"ok": False, "problem": "there is no card waiting"}
        store.decide(self.con, d.id, "cancelled", self.now)
        self.done.append("Took the card away")
        return {"ok": True, "cancelled": True}


def _remembered(m: Memory) -> dict[str, Any]:
    """A memory as the munshi is shown it."""
    by = {"shop": "you (the shopkeeper)", "customer": "the customer, in chat"}
    if m.kind == "said":
        by = {**by, "customer": "the customer's chat, as the munshi read it"}
    out: dict[str, Any] = {"said": m.body, "by": by[m.said_by], "kind": m.kind}
    if m.kind == "nickname":
        out["said"] = f"you call them {m.body}"
    if m.until is not None:
        out["quiet_until"] = m.until.isoformat()
    return out


def _keep_nickname(
    con: Conn, shop_id: str, customer_id: str, called: str, now: datetime
) -> None:
    """His yes to a card made out to what he calls them: remembered, once."""
    known = {
        m.body.casefold()
        for m in memories.of_customer(con, customer_id)
        if m.kind == "nickname"
    }
    if called.casefold() in known:
        return
    try:
        keeping.keep(con, shop_id, customer_id, "nickname", called, "shop", now)
    except (Conflict, NotFound) as e:
        log.info("nickname not kept: %s", e)


def save(
    con: Conn, shop_id: str, draft_id: str, now: datetime, done: list[str]
) -> dict[str, Any]:
    """The waiting card becomes the entry, once. Used by confirm_entry and by his
    tap on the card, so a spoken yes and a tapped one are the same yes."""
    d = store.claim(con, draft_id)
    if d is None:
        return {"ok": False, "problem": "that card is no longer waiting"}
    added = False
    try:
        if d.customer_id is None:
            assert d.new_name is not None
            c = ledger.add_by_name(con, shop_id, d.new_name, d.new_tag, now, voice.hindi)
            added = True
        else:
            found = customers.get(con, d.customer_id)
            assert found is not None
            c = found
        entry_id: str | None = None
        if d.kind == "correction":
            assert d.amount_paise is not None and d.corrects_entry_id is not None
            wrong = entries.get(con, d.corrects_entry_id)
            e = ledger.correct(
                con,
                shop_id,
                d.corrects_entry_id,
                d.amount_paise,
                now,
                spoken_text=d.spoken_text,
            )
            store.decide(con, d.id, "saved", now, e.id, customer_id=c.id)
            sent = c.joined == "linked"
            done.append(
                f"Corrected {c.display_name}: "
                f"₹{(wrong.amount_paise if wrong else 0) // 100} → "
                f"₹{d.amount_paise // 100}"
            )
            return {
                "saved": True,
                "corrected": True,
                "customer": c.name_hi or c.display_name,
                "was": amount_words(wrong.amount_paise) if wrong else None,
                "now": amount_words(d.amount_paise),
                "sent_to_customer_phone": sent,
                "next": "Say it is corrected, and that the customer confirms the new "
                "amount on their phone."
                if sent
                else "Say it is corrected. This customer is not on BAHI, so nothing "
                "was sent.",
            }
        if d.kind == "udhaar":
            assert d.amount_paise is not None
            scan_id = scans.waiting_for(con, c.id, now)
            e = ledger.record(
                con,
                shop_id,
                d.amount_paise,
                now,
                scan_id=UUID(scan_id) if scan_id else None,
                customer_id=None if scan_id else UUID(c.id),
                spoken_text=d.spoken_text,
            )
            entry_id = e.id
        elif d.kind == "payment":
            assert d.amount_paise is not None
            ledger.pay_cash(con, c.id, d.amount_paise, now)
    except Conflict as e:
        return {"ok": False, "problem": f"the book refused it: {e}"}
    store.decide(con, d.id, "saved", now, entry_id, customer_id=c.id)
    if d.called:
        _keep_nickname(con, shop_id, c.id, d.called, now)
    if added:
        done.append(f"Added {c.display_name} to the book, by name only")
    if d.amount_paise is None:
        return {
            "saved": True,
            "added_to_book": c.name_hi or c.display_name,
            "by_name_only": True,
            "next": "Say they're added by name only; to send them entries, invite "
            "them from Add customer.",
        }
    sent = c.joined == "linked"
    done.append(f"Wrote it: {c.display_name} ₹{d.amount_paise // 100}")
    return {
        "saved": True,
        "added_to_book": (c.name_hi or c.display_name) if added else None,
        "customer": c.name_hi or c.display_name,
        "kind": KIND_HI[d.kind],
        "amount": amount_words(d.amount_paise),
        "sent_to_customer_phone": sent,
        "why_not_sent": None
        if sent
        else "just added by name only, with no phone to send to; invite them from "
        "Add customer to send them entries"
        if added
        else "this customer is not on BAHI, so there is no phone to send to",
    }


def _paise(amount_rupees: Any) -> tuple[int, str | None]:
    """Whole rupees above zero and within what a conversation may take, as paise,
    or the problem to tell the munshi."""
    try:
        rupees = float(amount_rupees)
    except (TypeError, ValueError):
        return 0, "the amount must be a number of rupees"
    paise = round(rupees * 100)
    if rupees <= 0 or paise % 100:
        return 0, "the amount must be whole rupees above zero; ask him"
    if paise > MOST_PAISE:
        return 0, "that is too large to take by voice; ask him to check"
    return paise, None


def _whole(n: Any) -> int:
    try:
        return int(n)
    except (TypeError, ValueError):
        return 0


def edit_card(
    con: Conn,
    shop_id: str,
    draft_id: str,
    now: datetime,
    *,
    amount_rupees: int | None = None,
    new_name: str | None = None,
    new_tag: str | None = None,
) -> tuple[store.Draft | None, str | None]:
    """The shopkeeper fixed the waiting card on screen: the amount, and for
    someone new, their name and where they live. The same checks as a card the
    munshi makes; his own tap is still what writes it. Returns the card, or why
    not."""
    d = store.draft(con, draft_id)
    if d is None or d.status != "shown":
        return None, "that card is no longer waiting"
    kind, paise = d.kind, d.amount_paise
    if amount_rupees is not None:
        paise, problem = _paise(amount_rupees)
        if problem is not None:
            return None, problem
        if kind == "customer":
            kind = "udhaar"  # an amount on an add-only card makes it their first udhaar
        if kind == "payment" and d.customer_id:
            owed = ledger.balance(con, shop_id, d.customer_id, now.date())
            if paise > owed:
                return None, f"they owe only {rupees(owed)}"
    name, tag = d.new_name, d.new_tag
    if d.new_name is not None:
        name = (new_name if new_name is not None else d.new_name).strip()
        if not name or len(name) > 40:
            return None, "a name is needed"
        tag = (new_tag if new_tag is not None else (d.new_tag or "")).strip() or None
    reasons = [r for r in d.reasons if r not in ("large", "unusual")]
    if paise is not None and paise >= LARGE_PAISE:
        reasons.append("large")
    if kind == "udhaar" and d.customer_id and paise is not None:
        past = [e.amount_paise for e in entries.of_customer(con, d.customer_id)]
        if len(past) >= USUAL_FROM and paise >= UNUSUAL_TIMES * statistics.median(past):
            reasons.append("unusual")
    if kind == "correction" and d.corrects_entry_id:
        wrong = entries.get(con, d.corrects_entry_id)
        if wrong is not None and wrong.amount_paise == paise:
            return None, "that is what the entry already says"
    return store.edit(con, d.id, kind, paise, name, tag, reasons), None
