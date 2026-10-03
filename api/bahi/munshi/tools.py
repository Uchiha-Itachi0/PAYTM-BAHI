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
import statistics
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID

from bahi import voice
from bahi.domain import book as book_domain
from bahi.domain import limitation
from bahi.domain.find import Found, find
from bahi.domain.money import rupees
from bahi.domain.who import Person
from bahi.service import ledger
from bahi.service import tonight as tonight_service
from bahi.service.errors import Conflict
from bahi.store import book as book_store
from bahi.store import customers, entries, scans
from bahi.store import munshi as store
from bahi.store.customers import CustomerRef
from bahi.store.db import Conn
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

        out["customers"] = [row(f) for f in found[:LISTED]]
        if len(found) == 1:
            self.alone.add(found[0].person.ref)
        for f in found[:LISTED]:
            weak = not f.strong
            self.seen[f.person.ref] = self.seen.get(f.person.ref, True) and weak
        if len(found) > LISTED:
            out["more"] = len(found) - LISTED
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
                "Nobody fits. Say so plainly and ask who he means. If he says they "
                "are new, offer to add them with propose_new_customer."
            )
        elif len(found) > LISTED:
            out["next"] = (
                f"He asked for the names: read these {LISTED}, each with its place "
                f"only, never what they owe. Say there are {len(found) - LISTED} more "
                "and ask which one, or for a name or place to narrow it."
            )
        elif len(found) >= 3:
            out["next"] = (
                "He asked for the names: read each with its place only, never what "
                "they owe, then ask which one."
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
        return {
            "name": said,
            "about": about,
            "owes": amount_words(owed) if owed else "कुछ बाकी नहीं",
            "days_since_last_paid": day,
        }

    def propose_entry(
        self, customer_id: str, kind: str, amount_rupees: float
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
        return out

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
