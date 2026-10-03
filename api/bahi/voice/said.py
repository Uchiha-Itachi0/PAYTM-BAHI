"""What the counter says back, in Sarvam's voice, kept on disk.

The Soundbox says only two kinds of thing: an amount ("दो सौ बीस रुपये") and
one of three questions. Never a name: the customer's name is shown, not spoken
aloud. So this module takes an amount in paise or a question's name, and nothing
else.

Each phrase is spoken once by Sarvam's bulbul:v3 and kept, keyed by the voice
and the words. `make voice` speaks the demo's phrases into `audio/said`, which
is committed, so they play with the wifi off. Anything else is spoken on first
use and kept in `audio/raw/said`, which git ignores.
"""

from __future__ import annotations

import hashlib
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
    "again": "फिर से बोलिए।",
}


def amount_words(paise: int) -> str:
    """20000 -> "दो सौ रुपये". ValueError beyond what is said aloud."""
    return f"{say(paise).devanagari} रुपये"


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
