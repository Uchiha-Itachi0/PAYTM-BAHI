"""Voice at the counter: what was said, and what the rules made of it.

Every endpoint only reads. They return the amount, the person (or a question), and
the words to say back; the screen then records the entry with POST /entries, after
the shopkeeper has had three seconds to cancel. Typing and speaking end in the same
call, so a spoken entry and a typed one are the same entry.

When the screen asks "किसके लिए?", his answer goes to /answer: only who, among
the people it offered (or the whole book), and the amount stays the one it heard.
When it asks "कितने रुपये?" or "उधार या जमा?", his answer comes back to /heard or
/voice with `before`, what he said first, and the two are read as one sentence.
"""

from __future__ import annotations

from fastapi import APIRouter, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from bahi import clock, voice
from bahi.service import ledger, views
from bahi.service.deps import Con
from bahi.service.models import AnswerIn, AnswerOut, ClipOut, HeardIn, HeardOut
from bahi.voice import said
from bahi.voice.clips import BY_SLUG, CLIPS

router = APIRouter(tags=["voice"])

#: About a minute of compressed speech. An entry is a few seconds.
MAX_AUDIO_BYTES = 2_000_000


@router.post("/shops/{shop_id}/heard")
def heard_text(shop_id: str, body: HeardIn, con: Con) -> HeardOut:
    """Words typed or tapped: the same rules as speech, without the recogniser."""
    text = _after(body.before, body.text)
    hearing = ledger.hear(con, shop_id, text, clock.now())
    return views.heard_out(hearing, text, "typed")


@router.post("/shops/{shop_id}/voice")
def heard_voice(
    shop_id: str, audio: UploadFile, con: Con, before: str = Form("", max_length=400)
) -> HeardOut:
    """A recording from the shop's mic. 503 when voice is offline and it isn't a
    recording we have heard before; the screen then asks him to type it.
    `before`: what he said before, when this answers "कितने रुपये?"."""
    data = _read(audio)
    ledger.shop(con, shop_id)
    at_counter, book, _ = ledger.counter_and_book(con, shop_id, clock.now())
    names = [p.name for p in at_counter + book]  # listen out for these
    t = voice.hear(data, audio.content_type or "", keyterms=names)
    text = _after(before, t.text)
    hearing = ledger.hear(con, shop_id, text, clock.now())
    return views.heard_out(hearing, text, t.source)


@router.post("/shops/{shop_id}/answer")
def answer_text(shop_id: str, body: AnswerIn, con: Con) -> AnswerOut:
    """His answer to "किसके लिए?", typed: who, among `among` (empty: the book)."""
    among = [str(i) for i in body.among]
    a = ledger.answer(con, shop_id, body.text, among, clock.now())
    return views.answer_out(a, body.text, "typed")


@router.post("/shops/{shop_id}/answer/voice")
def answer_voice(
    shop_id: str, audio: UploadFile, con: Con, among: str = Form("")
) -> AnswerOut:
    """His answer to "किसके लिए?", spoken. `among`: the customer ids offered,
    comma separated; empty for anyone in the book."""
    data = _read(audio)
    ids = [i.strip() for i in among.split(",") if i.strip()]
    ledger.shop(con, shop_id)
    at_counter, book, _ = ledger.counter_and_book(con, shop_id, clock.now())
    offered = [p for p in book if p.ref in ids] if ids else at_counter + book
    t = voice.hear(data, audio.content_type or "", keyterms=[p.name for p in offered])
    a = ledger.answer(con, shop_id, t.text, ids, clock.now())
    return views.answer_out(a, t.text, t.source)


def _after(before: str | None, text: str) -> str:
    """ "Sharma ko" and "do sau": one sentence, read and checked as one."""
    return f"{before.strip()} {text}" if before and before.strip() else text


def _read(audio: UploadFile) -> bytes:
    data = audio.file.read(MAX_AUDIO_BYTES + 1)
    if len(data) > MAX_AUDIO_BYTES:
        raise HTTPException(413, "that recording is too long; an entry is a few words")
    return data


@router.get("/voice/clips")
def list_clips() -> list[ClipOut]:
    """The demo recordings on disk, for playing into /voice with the wifi off."""
    return [
        ClipOut(slug=c.slug, label=c.label, shows=c.shows)
        for c in CLIPS
        if c.path.exists()
    ]


@router.get("/voice/clips/{slug}.wav", response_class=FileResponse)
def get_clip(slug: str) -> FileResponse:
    clip = BY_SLUG.get(slug)
    if clip is None or not clip.path.exists():
        raise HTTPException(404, f"no clip {slug}")
    return FileResponse(clip.path, media_type="audio/wav")


@router.get("/voice/say/{paise}.wav", response_class=FileResponse)
def say_amount(paise: int) -> FileResponse:
    """The amount said back in Sarvam's voice. An amount only: this route cannot
    say a name. 503 when voice is offline and it was never spoken; the screen then
    uses the browser's own voice."""
    try:
        words = said.amount_words(paise)
    except ValueError as e:
        raise HTTPException(404, f"{paise} paise is not said aloud") from e
    return FileResponse(said.speech(words), media_type="audio/wav")


@router.get("/voice/received/{paid}/{left}.wav", response_class=FileResponse)
def say_received(paid: int, left: int) -> FileResponse:
    """The Soundbox when money arrives: "सौ रुपये मिले, सौ रुपये बाकी।" Amounts
    only: this route cannot say a name. 503 when voice is offline and it was never
    spoken; the Soundbox then plays its tone."""
    try:
        words = said.received(paid, left)
    except ValueError as e:
        raise HTTPException(404, "that is not said aloud") from e
    return FileResponse(said.speech(words), media_type="audio/wav")


@router.get("/voice/ask/{question}.wav", response_class=FileResponse)
def say_ask(question: str) -> FileResponse:
    """ "किसके लिए?" (who), "कितने रुपये?" (how_much), "उधार या जमा?" (kind) or
    "फिर से बोलिए।" (again), in Sarvam's voice."""
    words = said.ASKS.get(question)
    if words is None:
        raise HTTPException(404, f"no question {question}")
    return FileResponse(said.speech(words), media_type="audio/wav")
