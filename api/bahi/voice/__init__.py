"""Speech in: a recording becomes words, and the words become a checked draft.

`hear`: the words, from the cache or from Sarvam. `understand`: Sarvam-105B reads
them, and `domain.check` holds its draft to them; offline, our parser reads them
and the same checks run. `hindi`: a new customer's name in Devanagari.

`SARVAM_OFFLINE` is on unless set to 0. Offline, a recording Sarvam has heard
before (the demo clips) is answered from disk, anything else is refused with a
clear message so the shopkeeper types it instead, and our parser does the reading.
Nothing is ever guessed in place of a transcript.

Live recordings are never written to the cache. Only `make voice` writes there.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from bahi.domain.check import Checked, check_draft, check_rules
from bahi.domain.who import Person, shortlist
from bahi.voice import cache, reader, sarvam

Source = Literal["sarvam", "sarvam_cached", "clip_script"]
#: Why our parser read it instead of Sarvam-105B.
Fallback = Literal["offline", "no_answer"]


class VoiceOffline(Exception):
    """No transcript on disk for this recording, and Sarvam is switched off."""


@dataclass(frozen=True, slots=True)
class Transcript:
    text: str
    source: Source
    #: The language Sarvam heard, e.g. "mr-IN"; None from the cache.
    language: str | None = None


#: Unicode blocks of the scripts Sarvam speaks, and the language it reads each
#: as. Devanagari is Hindi unless the speaker was heard in Marathi.
SCRIPTS = (
    (0x0900, 0x097F, "hi-IN"),
    (0x0980, 0x09FF, "bn-IN"),
    (0x0A00, 0x0A7F, "pa-IN"),
    (0x0A80, 0x0AFF, "gu-IN"),
    (0x0B00, 0x0B7F, "od-IN"),
    (0x0B80, 0x0BFF, "ta-IN"),
    (0x0C00, 0x0C7F, "te-IN"),
    (0x0C80, 0x0CFF, "kn-IN"),
    (0x0D00, 0x0D7F, "ml-IN"),
)


def language_of(text: str, heard: str | None = None) -> str:
    """The language to say `text` in: by its script, the one with the most
    letters. Devanagari takes `heard` when that was Marathi; English letters only
    are en-IN. Hindi when there are no letters at all."""
    counts: dict[str, int] = {}
    for ch in text:
        o = ord(ch)
        lang = next((code for lo, hi, code in SCRIPTS if lo <= o <= hi), None)
        if lang is None and ch.isascii() and ch.isalpha():
            lang = "en-IN"
        if lang is not None:
            counts[lang] = counts.get(lang, 0) + 1
    if not counts:
        return "hi-IN"
    best = max(counts, key=lambda k: counts[k])
    if best == "hi-IN" and heard == "mr-IN":
        return "mr-IN"
    return best


log = logging.getLogger(__name__)

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
    text, language = sarvam.heard(audio, content_type, key=key, keyterms=keyterms)
    return Transcript(text, "sarvam", language)


def understand(
    transcript: str, waiting: Sequence[Person], book: Sequence[Person]
) -> tuple[Checked, Fallback | None]:
    """Sarvam-105B's reading, checked; or our parser's, and why."""
    key = api_key()
    if offline() or key is None:
        return check_rules(transcript, waiting, book), "offline"
    shown = shortlist(transcript, waiting, book)
    try:
        draft = reader.read(transcript, waiting, shown, key=key)
    except sarvam.SarvamError as e:
        log.warning("Sarvam-105B gave no usable reading, our parser read it: %s", e)
        return check_rules(transcript, waiting, book), "no_answer"
    return check_draft(transcript, draft, shown, waiting, book), None


def hindi(name: str) -> str | None:
    """The name in Devanagari, or None when voice is off or Sarvam doesn't answer.
    The roman name still matches; this only helps."""
    key = api_key()
    if offline() or key is None or not name.strip():
        return None
    try:
        return sarvam.transliterate(name.strip(), key=key)
    except sarvam.SarvamError as e:
        log.warning("no Devanagari for a new customer's name: %s", e)
        return None
