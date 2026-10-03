"""Voice at the counter: what was said, and what the rules made of it.

Both endpoints only read. They return the amount, the person (or a question), and
the words to say back; the screen then records the entry with POST /entries, after
the shopkeeper has had three seconds to cancel. Typing and speaking end in the same
call, so a spoken entry and a typed one are the same entry.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, UploadFile
from fastapi.responses import FileResponse

from bahi import clock, voice
from bahi.service import ledger, views
from bahi.service.deps import Con
from bahi.service.models import ClipOut, HeardIn, HeardOut
from bahi.voice import said
from bahi.voice.clips import BY_SLUG, CLIPS

router = APIRouter(tags=["voice"])

#: About a minute of compressed speech. An entry is a few seconds.
MAX_AUDIO_BYTES = 2_000_000


@router.post("/shops/{shop_id}/heard")
def heard_text(shop_id: str, body: HeardIn, con: Con) -> HeardOut:
    """Words typed or tapped: the same rules as speech, without the recogniser."""
    hearing = ledger.hear(con, shop_id, body.text, clock.now())
    return views.heard_out(hearing, body.text, "typed")


@router.post("/shops/{shop_id}/voice")
def heard_voice(shop_id: str, audio: UploadFile, con: Con) -> HeardOut:
    """A recording from the shop's mic. 503 when voice is offline and it isn't a
    recording we have heard before; the screen then asks him to type it."""
    data = audio.file.read(MAX_AUDIO_BYTES + 1)
    if len(data) > MAX_AUDIO_BYTES:
        raise HTTPException(413, "that recording is too long; an entry is a few words")
    ledger.shop(con, shop_id)
    at_counter, book, _ = ledger.counter_and_book(con, shop_id, clock.now())
    names = [p.name for p in at_counter + book]  # listen out for these
    t = voice.hear(data, audio.content_type or "", keyterms=names)
    hearing = ledger.hear(con, shop_id, t.text, clock.now())
    return views.heard_out(hearing, t.text, t.source)


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


@router.get("/voice/ask.wav", response_class=FileResponse)
def say_ask() -> FileResponse:
    """ "किसके लिए?", in Sarvam's voice."""
    return FileResponse(said.speech(said.ASK), media_type="audio/wav")
