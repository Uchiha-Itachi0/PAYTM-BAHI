"""Speech in: a recording becomes words, from the cache or from Sarvam.

`SARVAM_OFFLINE` is on unless set to 0, which is how the demo runs: a recording
Sarvam has heard before (the demo clips) is answered from disk, and anything else
is refused with a clear message, so the shopkeeper types it instead. Nothing is
ever guessed in place of a transcript.

Live recordings are never written to the cache. Only `make voice` writes there.
"""

from __future__ import annotations

import os
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from bahi.voice import cache, sarvam

Source = Literal["sarvam", "sarvam_cached", "clip_script"]


class VoiceOffline(Exception):
    """No transcript on disk for this recording, and Sarvam is switched off."""


@dataclass(frozen=True, slots=True)
class Transcript:
    text: str
    source: Source


_OFF = frozenset({"0", "false", "no", "off"})


def offline() -> bool:
    return os.environ.get("SARVAM_OFFLINE", "1").strip().lower() not in _OFF


def api_key() -> str | None:
    return os.environ.get("SARVAM_API_KEY") or None


def hear(audio: bytes, content_type: str, keyterms: Sequence[str] = ()) -> Transcript:
    cached = cache.get(audio)
    if cached is not None:
        return Transcript(
            cached.transcript,
            "sarvam_cached" if cached.source == "sarvam" else "clip_script",
        )
    key = api_key()
    if offline() or key is None:
        raise VoiceOffline(
            "Voice is offline, so only the demo clips can be heard. "
            "Type the amount instead."
        )
    text = sarvam.transcribe(audio, content_type, key=key, keyterms=keyterms)
    return Transcript(text, "sarvam")
