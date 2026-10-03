"""Sarvam speech-to-text, over HTTP. The only code that talks to Sarvam.

It returns the words and nothing else. The amount and the person are found by the
rules in `bahi.domain`, from the transcript: the model never sees the book and
never produces the number that is recorded.

`saaras:v4` takes `keyterms`: words to listen out for. We pass the names of the
people at the counter (then the book), so "Iqbal" is heard as Iqbal. That biases
what it hears; it does not decide who the entry is for.

API: https://docs.sarvam.ai/api-reference-docs/speech-to-text/transcribe
"""

from __future__ import annotations

import json
import os
from collections.abc import Sequence

import httpx

URL = "https://api.sarvam.ai/speech-to-text"
LANGUAGE = "hi-IN"
MAX_KEYTERMS, MAX_KEYTERM_LEN = 50, 64
TIMEOUT_S = 15.0


class SarvamError(Exception):
    """Sarvam could not be reached, or refused the request."""


def model() -> str:
    return os.environ.get("SARVAM_STT_MODEL", "saaras:v4")


def transcribe(
    audio: bytes,
    content_type: str,
    *,
    key: str,
    keyterms: Sequence[str] = (),
) -> str:
    m = model()
    form: dict[str, str] = {"model": m, "language_code": LANGUAGE}
    if m == "saaras:v4":
        terms = [t[:MAX_KEYTERM_LEN] for t in dict.fromkeys(keyterms) if t]
        if terms:
            form["keyterms"] = json.dumps(terms[:MAX_KEYTERMS], ensure_ascii=False)
    else:
        form["mode"] = "transcribe"  # native script; the parser reads either
    try:
        r = httpx.post(
            URL,
            headers={"api-subscription-key": key},
            data=form,
            files={"file": ("speech", audio, content_type or "application/octet-stream")},
            timeout=TIMEOUT_S,
        )
    except httpx.HTTPError as e:
        raise SarvamError(f"could not reach Sarvam: {e}") from e
    if r.status_code != 200:
        raise SarvamError(f"Sarvam said {r.status_code}: {r.text[:200]}")
    transcript = r.json().get("transcript")
    if not isinstance(transcript, str):
        raise SarvamError("Sarvam sent no transcript")
    return transcript
