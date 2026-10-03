"""The demo lines, as short recordings the laptop can play into the voice path.

They exist so the whole path (audio in, transcript, rule, readback) can be shown
with the wifi off. Each is rendered once by macOS's Hindi voice (Lekha) and
committed; `make voice` then has Sarvam transcribe it and commits the transcript.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from bahi.voice.cache import AUDIO

CLIPS_DIR = AUDIO / "clips"


@dataclass(frozen=True, slots=True)
class Clip:
    slug: str
    #: What the recording says, in the script the Hindi voice reads.
    words: str
    #: The same, in roman, for a button on the screen.
    label: str
    #: What it shows.
    shows: str

    @property
    def path(self) -> Path:
        return CLIPS_DIR / f"{self.slug}.wav"


CLIPS = (
    # Not "दो सौ" alone: Sarvam hears the Mac voice's दो सौ as दूसरा ("second").
    Clip(
        "do-sau",
        "दो सौ रुपये",
        "do sau rupaye",
        "One person at the counter: the amount is enough",
    ),
    Clip(
        "iqbal-teen-sau",
        "इक़बाल भाई, तीन सौ",
        "Iqbal bhai, teen sau",
        "A name said: looked for at the counter first, then in the book",
    ),
    Clip(
        "sharma-dhaai-sau",
        "शर्मा को ढाई सौ उधार",
        "Sharma ko dhaai sau udhaar",
        "Not at the counter: the name is found in the book",
    ),
    Clip(
        "saade-teen-sau-de-do",
        "साढ़े तीन सौ दे दो",
        "saade teen sau de do",
        "A fraction word, and 'do' that means 'give'",
    ),
    Clip(
        "anubhav-do-sau-bees",
        "अनुभव को दो सौ बीस रुपये दे दो",
        "Anubhav ko do sau bees",
        "Four Anubhavs in the book: Kaunse Anubhav?",
    ),
    Clip(
        "anubhav-shukla",
        "अनुभव शुक्ला को दो सौ बीस",
        "Anubhav Shukla ko do sau bees",
        "The surname picks one of the four",
    ),
)

BY_SLUG = {c.slug: c for c in CLIPS}
