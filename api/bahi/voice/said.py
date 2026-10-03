"""What the counter says back, in Sarvam's voice, kept on disk.

The Soundbox says only two kinds of thing: an amount ("दो सौ बीस रुपये") and
one of its questions, never a name. The munshi says its own sentences, which can
name a customer when the shopkeeper has asked it to (`munshi.brain`); those are
spoken here too, on first use, and kept in `audio/raw/said`.

Each phrase is spoken once by Sarvam's bulbul:v3 and kept, keyed by the voice
and the words. `make voice` speaks the demo's phrases into `audio/said`, which
is committed, so they play with the wifi off. Anything else is spoken on first
use and kept in `audio/raw/said`, which git ignores.

A munshi sentence can be long (a list of names he asked to hear), and bulbul
takes longer the longer it is: 2.2 s for 61 characters, 6.7 s for 212. So it is
cut where a speaker pauses anyway, the pieces are said at once and joined, and
it takes about as long as its longest piece. It is started the moment the reply
exists (`warm`), not when the screen asks for it.
"""

from __future__ import annotations

import contextlib
import hashlib
import io
import re
import threading
import wave
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path

from bahi.domain.speak import say
from bahi.voice import VoiceOffline, api_key, offline, sarvam
from bahi.voice.cache import AUDIO

SAID = AUDIO / "said"
LIVE = AUDIO / "raw" / "said"

#: What the counter asks, then listens for the answer.
ASKS = {
    "who": "किसके लिए?",
    "how_much": "कितने रुपये?",
    "kind": "उधार या जमा?",
    "again": "फिर से बोलिए।",
}


def amount_words(paise: int) -> str:
    """20000 -> "दो सौ रुपये". ValueError beyond what is said aloud."""
    return f"{say(paise).devanagari} रुपये"


def received(paid_paise: int, left_paise: int) -> str:
    """What the Soundbox says when money arrives: the sum, and what is still open
    after it. Amounts only, never a name. ValueError beyond what is said aloud."""
    got = f"{amount_words(paid_paise)} मिले"
    if left_paise == 0:
        return f"{got}, हिसाब पूरा।"
    return f"{got}, {amount_words(left_paise)} बाकी।"


def _name(text: str, voice: str) -> str:
    raw = f"{sarvam.TTS_MODEL}|{voice}|{text}".encode()
    return hashlib.sha256(raw).hexdigest()[:24] + ".wav"


def cached(text: str, voice: str | None = None) -> Path | None:
    name = _name(text, voice or sarvam.speaker())
    return next((d / name for d in (SAID, LIVE) if (d / name).exists()), None)


def speech(text: str, *, keep_in: Path | None = None) -> Path:
    """The phrase as a WAV on disk: from the cache, or spoken by Sarvam now.
    VoiceOffline when it isn't on disk and Sarvam is switched off."""
    voice = sarvam.speaker()
    found = cached(text, voice)
    if found is not None:
        return found
    key = api_key()
    if offline() or key is None:
        raise VoiceOffline("Voice is offline and this phrase was never spoken")
    audio = sarvam.speak(text, key=key, voice=voice)
    folder = keep_in or LIVE
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / _name(text, voice)
    path.write_bytes(audio)
    return path


# ── the munshi's sentences ───────────────────────────────────────────────────

#: A piece of a long sentence: about two seconds of speech.
PIECE_CHARS = 80
#: Where a sentence can be cut without changing how it sounds: after a full stop
#: (। . ? !) or a semicolon, and inside a long list, after a comma.
_ENDS = re.compile(r"(?<=[।.?!;])\s+")
_COMMAS = re.compile(r"(?<=,)\s+")

_SENTENCES = ThreadPoolExecutor(max_workers=4, thread_name_prefix="said")
_PIECES = ThreadPoolExecutor(max_workers=8, thread_name_prefix="said-piece")
_LOCK = threading.Lock()
#: Sentences being said right now, by file name: the screen's request for one
#: that `warm` started waits for it instead of asking Sarvam again.
_BUSY: dict[str, Future[Path]] = {}


def pieces(text: str, most: int = PIECE_CHARS) -> list[str]:
    """The sentence in pieces of up to `most` characters, cut only where the
    speaker would pause anyway. A part with nowhere to cut stays whole."""
    parts: list[str] = []
    for p in _ENDS.split(text.strip()):
        parts.extend(_COMMAS.split(p) if len(p) > most else [p])
    out: list[str] = []
    for p in (x.strip() for x in parts):
        if not p:
            continue
        if out and len(out[-1]) + 1 + len(p) <= most:
            out[-1] = f"{out[-1]} {p}"
        else:
            out.append(p)
    return out


def joined(wavs: list[bytes]) -> bytes:
    """One WAV from several, in order. Each of Sarvam's already ends in a short
    silence, the pause between two sentences."""
    if len(wavs) == 1:
        return wavs[0]
    frames: list[bytes] = []
    shape: tuple[int, int, int] | None = None
    try:
        for one in wavs:
            with wave.open(io.BytesIO(one)) as r:
                this = (r.getnchannels(), r.getsampwidth(), r.getframerate())
                if shape is not None and this != shape:
                    raise sarvam.SarvamError("Sarvam's pieces don't match")
                shape = this
                frames.append(r.readframes(r.getnframes()))
    except wave.Error as e:
        raise sarvam.SarvamError(f"Sarvam's audio was not a WAV: {e}") from e
    assert shape is not None
    out = io.BytesIO()
    with wave.open(out, "wb") as w:
        w.setnchannels(shape[0])
        w.setsampwidth(shape[1])
        w.setframerate(shape[2])
        w.writeframes(b"".join(frames))
    return out.getvalue()


def _say_and_keep(text: str, voice: str, key: str) -> Path:
    asked = [
        _PIECES.submit(
            sarvam.speak,
            p,
            key=key,
            voice=voice,
            timeout=sarvam.SENTENCE_TTS_TIMEOUT_S,
        )
        for p in pieces(text)
    ]
    audio = joined([f.result() for f in asked])
    LIVE.mkdir(parents=True, exist_ok=True)
    path = LIVE / _name(text, voice)
    path.write_bytes(audio)
    return path


def _started(text: str) -> Future[Path]:
    voice = sarvam.speaker()
    found = cached(text, voice)
    if found is not None:
        ready: Future[Path] = Future()
        ready.set_result(found)
        return ready
    key = api_key()
    if offline() or key is None:
        raise VoiceOffline("Voice is offline and this sentence was never spoken")
    name = _name(text, voice)
    with _LOCK:
        busy = _BUSY.get(name)
        if busy is None:
            busy = _SENTENCES.submit(_say_and_keep, text, voice, key)
            _BUSY[name] = busy

            def over(f: Future[Path], name: str = name) -> None:
                with _LOCK:
                    if _BUSY.get(name) is f:
                        del _BUSY[name]

            busy.add_done_callback(over)
    return busy


def sentence(text: str) -> Path:
    """One of the munshi's sentences as a WAV on disk, said now, or already being
    said since `warm`. SarvamError if Sarvam couldn't; VoiceOffline when voice is
    switched off and it was never said."""
    return _started(text).result()


def warm(text: str) -> None:
    """Start saying the munshi's reply now: the screen will ask for it a moment
    later, and by then it is ready or nearly."""
    with contextlib.suppress(VoiceOffline):
        _started(text)
