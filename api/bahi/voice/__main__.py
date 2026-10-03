"""`make voice` and `make voice-list`.

    make voice        render any missing demo clip with macOS's Hindi voice, then
                      have Sarvam transcribe every clip (needs SARVAM_API_KEY; runs
                      whatever SARVAM_OFFLINE says, since calling Sarvam is the point)
    make voice-list   what the offline cache holds, and where each transcript came from

Without a key, `make voice` still renders the clips, and records the line each was
made from as its transcript, marked "script" rather than "sarvam".
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from dotenv import load_dotenv

from bahi.voice import api_key, cache, sarvam
from bahi.voice.clips import CLIPS, CLIPS_DIR, Clip

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

VOICE = "Lekha"  # macOS's hi_IN voice


def render(clip: Clip) -> None:
    """Speak the line with macOS `say`, as 16 kHz mono WAV: Sarvam's best rate."""
    if shutil.which("say") is None or shutil.which("afconvert") is None:
        sys.exit("rendering a clip needs macOS `say` and `afconvert`")
    CLIPS_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        aiff = Path(tmp) / "clip.aiff"
        subprocess.run(["say", "-v", VOICE, "-o", str(aiff), clip.words], check=True)
        subprocess.run(
            [
                "afconvert",
                "-f",
                "WAVE",
                "-d",
                "LEI16@16000",
                "-c",
                "1",
                str(aiff),
                str(clip.path),
            ],
            check=True,
        )


def generate() -> None:
    key = api_key()
    for clip in CLIPS:
        if not clip.path.exists():
            render(clip)
            print(f"rendered   {clip.path.name}")
        audio = clip.path.read_bytes()
        if key:
            # No keyterms: the committed transcript is what Sarvam hears unaided.
            text = sarvam.transcribe(audio, "audio/wav", key=key)
            cache.put(audio, cache.Cached(text, "sarvam", sarvam.model(), clip.slug))
            print(f"sarvam     {clip.slug:24} {text}")
        elif cache.get(audio) is None:
            cache.put(audio, cache.Cached(clip.words, "script", None, clip.slug))
            note = "(no key: the line, not a transcript)"
            print(f"script     {clip.slug:24} {clip.words}   {note}")
        else:
            print(f"cached     {clip.slug}")


def listing() -> None:
    entries = cache.all_cached()
    if not entries:
        print("the cache is empty. run `make voice`")
    for digest, c in entries:
        model, clip = c.model or "-", c.clip or "-"
        print(f"{c.source:7} {model:10} {clip:24} {c.transcript}   {digest[:12]}")


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    if command == "generate":
        generate()
    elif command == "list":
        listing()
    else:
        sys.exit("usage: python -m bahi.voice generate | list")
