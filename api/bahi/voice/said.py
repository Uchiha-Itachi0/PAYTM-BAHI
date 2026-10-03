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
takes longer the longer it is: 1.3 s for a short one, 3.2 to 6.7 s for five
names. It is always one request, never pieces joined: each request is voiced
afresh, and on 30 Sep two halves of one sentence came back at 188 and 216 Hz,
two voices to the ear. So it is started the moment the reply exists (`warm`),
not when the screen asks for it.
"""

from __future__ import annotations

import contextlib
import hashlib
import threading
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
    """What the Soundbox says when money arrives: what was owed, how much of it
    came, and what is still open. Amounts only, never a name: the counter is
    public. ValueError beyond what is said aloud.

    "दो सौ रुपये का उधार था, उसमें से सौ रुपये मिले, सौ रुपये बाकी।"
    """
    owed = amount_words(paid_paise + left_paise)
    if left_paise == 0:
        return f"{owed} का उधार था, पूरे {amount_words(paid_paise)} मिले, हिसाब पूरा।"
    return (
        f"{owed} का उधार था, उसमें से {amount_words(paid_paise)} मिले, "
        f"{amount_words(left_paise)} बाकी।"
    )


def asked(paise: int) -> str:
    """What the Soundbox says when someone at the counter asks for udhaar: the
    amount, never who or what for. The shopkeeper reads those on his screen.
    ValueError beyond what is said aloud."""
    return f"{amount_words(paise)} का उधार माँगा है।"


def _name(text: str, voice: str, language: str = sarvam.LANGUAGE) -> str:
    # Hindi, the first language, keeps the names its files were made under.
    lang = "" if language == sarvam.LANGUAGE else f"|{language}"
    raw = f"{sarvam.TTS_MODEL}|{voice}|{text}{lang}".encode()
    return hashlib.sha256(raw).hexdigest()[:24] + ".wav"


def cached(
    text: str, voice: str | None = None, language: str = sarvam.LANGUAGE
) -> Path | None:
    name = _name(text, voice or sarvam.speaker(), language)
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

_SENTENCES = ThreadPoolExecutor(max_workers=4, thread_name_prefix="said")
_LOCK = threading.Lock()
#: Sentences being said right now, by file name: the screen's request for one
#: that `warm` started waits for it instead of asking Sarvam again.
_BUSY: dict[str, Future[Path]] = {}


def _say_and_keep(text: str, voice: str, key: str, language: str) -> Path:
    audio = sarvam.speak(
        text,
        key=key,
        voice=voice,
        timeout=sarvam.SENTENCE_TTS_TIMEOUT_S,
        language=language,
    )
    LIVE.mkdir(parents=True, exist_ok=True)
    path = LIVE / _name(text, voice, language)
    path.write_bytes(audio)
    return path


def _started(text: str, language: str) -> Future[Path]:
    voice = sarvam.speaker()
    found = cached(text, voice, language)
    if found is not None:
        ready: Future[Path] = Future()
        ready.set_result(found)
        return ready
    key = api_key()
    if offline() or key is None:
        raise VoiceOffline("Voice is offline and this sentence was never spoken")
    name = _name(text, voice, language)
    with _LOCK:
        busy = _BUSY.get(name)
        if busy is None:
            busy = _SENTENCES.submit(_say_and_keep, text, voice, key, language)
            _BUSY[name] = busy

            def over(f: Future[Path], name: str = name) -> None:
                with _LOCK:
                    if _BUSY.get(name) is f:
                        del _BUSY[name]

            busy.add_done_callback(over)
    return busy


def sentence(text: str, language: str = sarvam.LANGUAGE) -> Path:
    """One of the munshi's sentences as a WAV on disk, said now, or already being
    said since `warm`. SarvamError if Sarvam couldn't; VoiceOffline when voice is
    switched off and it was never said."""
    return _started(text, language).result()


def warm(text: str, language: str = sarvam.LANGUAGE) -> None:
    """Start saying the munshi's reply now: the screen will ask for it a moment
    later, and by then it is ready or nearly."""
    with contextlib.suppress(VoiceOffline):
        _started(text, language)
