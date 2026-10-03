"""What Sarvam heard, kept on disk and committed, keyed by the audio's hash.

The venue wifi is assumed to fail. The demo clips are transcribed once, with a key,
by `make voice`, and the transcripts are committed; on the day the same audio
finds its transcript here without a network call.

Each file says where its words came from. "sarvam" is a real transcription.
"script" is the line the clip was rendered from, written down before anyone ran
Sarvam on it: honest about being a stand-in, and replaced by `make voice`.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

AUDIO = Path(__file__).resolve().parent.parent / "audio"
HEARD = AUDIO / "heard"

Source = Literal["sarvam", "script"]


@dataclass(frozen=True, slots=True)
class Cached:
    transcript: str
    source: Source
    model: str | None
    clip: str | None


def digest(audio: bytes) -> str:
    return hashlib.sha256(audio).hexdigest()


def get(audio: bytes) -> Cached | None:
    path = HEARD / f"{digest(audio)}.json"
    if not path.exists():
        return None
    return Cached(**json.loads(path.read_text(encoding="utf-8")))


def put(audio: bytes, cached: Cached) -> Path:
    HEARD.mkdir(parents=True, exist_ok=True)
    path = HEARD / f"{digest(audio)}.json"
    body = json.dumps(asdict(cached), ensure_ascii=False, indent=2) + "\n"
    path.write_text(body, encoding="utf-8")
    return path


def all_cached() -> list[tuple[str, Cached]]:
    if not HEARD.exists():
        return []
    return [
        (p.stem, Cached(**json.loads(p.read_text(encoding="utf-8"))))
        for p in sorted(HEARD.glob("*.json"))
    ]
