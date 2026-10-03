"""The munshi at the counter: talk or type, tap the card, hear the reply.

Every call is one turn of a conversation. The munshi may look people up and put a
card on the screen; nothing is written until his yes, spoken or tapped, and then
through the same ledger code as a typed entry. The munshi needs Sarvam: with voice
offline these calls answer 503, and the screen's keypad still records by hand.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from bahi import clock, voice
from bahi.munshi import brain
from bahi.service import ledger
from bahi.service.deps import Con
from bahi.service.models import CardEditIn, CardOut, MunshiIn, MunshiOut
from bahi.service.routes.voice import _read
from bahi.store import customers, entries
from bahi.store import munshi as store
from bahi.store.db import Conn
from bahi.voice import said, sarvam

router = APIRouter(tags=["munshi"])

OFFLINE = "The munshi needs the internet, and voice is offline. Enter it by hand below."


def chat() -> brain.Chat:
    """Sarvam's model, or 503 when voice is off. Tests replace this."""
    key = voice.api_key()
    if voice.offline() or key is None:
        raise HTTPException(503, OFFLINE)

    def ask(
        messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> dict[str, Any]:
        return sarvam.munshi(messages, tools, key=key)

    return ask


def _conversation(
    con: Conn, shop_id: str, conversation_id: UUID | str | None
) -> str | None:
    if conversation_id is None or conversation_id == "":
        return None
    cid = str(conversation_id)
    if store.shop_of(con, cid) != shop_id:
        raise HTTPException(404, f"no conversation {cid} at this shop")
    return cid


def _was(con: Conn, entry_id: str | None) -> int | None:
    e = entries.get(con, entry_id) if entry_id else None
    return e.amount_paise if e else None


def _out(
    con: Conn, shop_id: str, o: brain.Outcome, heard: str | None, source: str
) -> MunshiOut:
    card = None
    d = o.draft
    if d is not None:
        c = customers.get(con, d.customer_id) if d.customer_id else None
        name = c.display_name if c else d.new_name
        assert name is not None
        card = CardOut(
            draft_id=UUID(d.id),
            customer_id=UUID(c.id) if c else None,
            display_name=name,
            tag=c.tag if c else d.new_tag,
            amount_paise=d.amount_paise,
            kind=d.kind,  # type: ignore[arg-type]
            new=d.new_name is not None,
            corrects_amount_paise=_was(con, d.corrects_entry_id),
            status=d.status,  # type: ignore[arg-type]
            reasons=d.reasons,  # type: ignore[arg-type]
            spoken_text=d.spoken_text,
            entry_id=UUID(d.entry_id) if d.entry_id else None,
            on_bahi=c is not None and c.joined == "linked",
        )
    say = (
        f"/shops/{shop_id}/munshi/{o.conversation_id}/say/{o.reply_turn_id}.wav"
        if o.reply and o.reply_turn_id
        else None
    )
    if say and o.reply:
        said.warm(o.reply)  # ready, or nearly, when the screen asks for it
    return MunshiOut(
        conversation_id=UUID(o.conversation_id),
        heard=heard,
        source=source,  # type: ignore[arg-type]
        reply=o.reply,
        say_url=say,
        done=o.done,
        card=card,
        finished=o.finished,
    )


@router.post("/shops/{shop_id}/munshi")
def talk_text(shop_id: str, body: MunshiIn, con: Con) -> MunshiOut:
    """He typed to the munshi."""
    ledger.shop(con, shop_id)
    ask = chat()
    cid = _conversation(con, shop_id, body.conversation_id)
    text = body.text.strip()
    o = brain.talk(con, shop_id, cid, text, clock.now(), ask)
    return _out(con, shop_id, o, text, "typed")


@router.post("/shops/{shop_id}/munshi/voice")
def talk_voice(
    shop_id: str, audio: UploadFile, con: Con, conversation_id: str = Form("")
) -> MunshiOut:
    """He spoke to the munshi. The book's names are Saaras's hints."""
    data = _read(audio)
    ledger.shop(con, shop_id)
    ask = chat()
    cid = _conversation(con, shop_id, conversation_id or None)
    at_counter, book, _ = ledger.counter_and_book(con, shop_id, clock.now())
    names = [p.name for p in at_counter + book]
    t = voice.hear(data, audio.content_type or "", keyterms=names)
    o = brain.talk(con, shop_id, cid, t.text, clock.now(), ask, heard=t.text)
    return _out(con, shop_id, o, t.text, t.source)


def _tap(
    con: Conn, shop_id: str, conversation_id: UUID, draft_id: UUID, yes: bool
) -> MunshiOut:
    ledger.shop(con, shop_id)
    ask = chat()
    cid = _conversation(con, shop_id, conversation_id)
    assert cid is not None
    d = store.draft(con, str(draft_id))
    if d is None or d.conversation_id != cid:
        raise HTTPException(404, f"no card {draft_id} in this conversation")
    o = brain.tap(con, shop_id, cid, str(draft_id), yes, clock.now(), ask)
    return _out(con, shop_id, o, None, "tap")


@router.post("/shops/{shop_id}/munshi/{conversation_id}/cards/{draft_id}/yes")
def card_yes(shop_id: str, conversation_id: UUID, draft_id: UUID, con: Con) -> MunshiOut:
    """He tapped हाँ, or the three-second countdown ran out. Saving twice is saving
    once."""
    return _tap(con, shop_id, conversation_id, draft_id, True)


@router.post("/shops/{shop_id}/munshi/{conversation_id}/cards/{draft_id}/no")
def card_no(shop_id: str, conversation_id: UUID, draft_id: UUID, con: Con) -> MunshiOut:
    """He tapped नहीं: the card goes, nothing is written."""
    return _tap(con, shop_id, conversation_id, draft_id, False)


@router.post("/shops/{shop_id}/munshi/{conversation_id}/cards/{draft_id}/edit")
def card_edit(
    shop_id: str, conversation_id: UUID, draft_id: UUID, body: CardEditIn, con: Con
) -> MunshiOut:
    """He fixed the waiting card on screen: the amount, or someone new's name and
    where they live. No model is asked, so this works with voice down too."""
    ledger.shop(con, shop_id)
    cid = _conversation(con, shop_id, conversation_id)
    assert cid is not None
    d = store.draft(con, str(draft_id))
    if d is None or d.conversation_id != cid:
        raise HTTPException(404, f"no card {draft_id} in this conversation")
    o = brain.edit(
        con,
        shop_id,
        cid,
        str(draft_id),
        clock.now(),
        amount_rupees=body.amount_rupees,
        new_name=body.new_name,
        new_tag=body.new_tag,
    )
    return _out(con, shop_id, o, None, "tap")


@router.get(
    "/shops/{shop_id}/munshi/{conversation_id}/say/{turn_id}.wav",
    response_class=FileResponse,
)
def say_reply(
    shop_id: str, conversation_id: UUID, turn_id: UUID, con: Con
) -> FileResponse:
    """The munshi's reply in Sarvam's voice (Bulbul, shreya). 503 when voice is
    offline; the screen then shows the reply without saying it."""
    cid = _conversation(con, shop_id, conversation_id)
    t = store.turn(con, str(turn_id))
    if (
        t is None
        or t.conversation_id != cid
        or t.role != "assistant"
        or not t.message.get("content")
    ):
        raise HTTPException(404, "no reply to say")
    text = brain.spoken(str(t.message["content"]))
    try:
        return FileResponse(said.sentence(text), media_type="audio/wav")
    except sarvam.SarvamError as e:
        raise HTTPException(503, "Sarvam didn't say it this time") from e
