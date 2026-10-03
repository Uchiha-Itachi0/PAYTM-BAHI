"""Sarvam, over HTTP. The only code that talks to Sarvam.

- `transcribe`: speech to words (saaras:v4). It takes `keyterms`, words to listen
  out for: we pass the names of the people at the counter, then the book, so
  "Iqbal" is heard as Iqbal. That biases what it hears; it does not decide who.
- `chat_json`: Sarvam-105B, answering in a JSON schema. `bahi.voice.reader` asks
  it to read the words; `bahi.domain.check` then checks everything it says.
- `transliterate`: a customer's name in Devanagari, once, when he joins, so a
  transcript in either script can be matched to him.
- `speak`: the amount said back, in Sarvam's own voice (bulbul:v3), instead of
  the browser's robotic one.

APIs: https://docs.sarvam.ai/api-reference-docs/speech-to-text/transcribe
      https://docs.sarvam.ai/api-reference-docs/chat/chat-completions
      https://docs.sarvam.ai/api-reference-docs/text/transliterate
      https://docs.sarvam.ai/api-reference-docs/text-to-speech/convert
"""

from __future__ import annotations

import base64
import json
import os
import time
from collections.abc import Callable, Sequence
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from typing import Any

import httpx

URL = "https://api.sarvam.ai/speech-to-text"
CHAT_URL = "https://api.sarvam.ai/v1/chat/completions"
TRANSLITERATE_URL = "https://api.sarvam.ai/transliterate"
TTS_URL = "https://api.sarvam.ai/text-to-speech"
LANGUAGE = "hi-IN"
MAX_KEYTERMS, MAX_KEYTERM_LEN = 50, 64
TIMEOUT_S = 15.0
#: Sarvam-105B took at most 3.8 s on 1,338 readings, and 1.4 s as a rule; one
#: reading on 25 Sep took over 6. Past this, our parser reads, and the screen
#: asks the shopkeeper to tap Send rather than sending by itself.
CHAT_TIMEOUT_S = 8.0
#: On 30 Sep, two readings in eight took 25 s and the rest 1 s. A reading that
#: hasn't answered by now is asked for again, and the first answer wins.
HEDGE_AFTER_S = 2.5
TRANSLITERATE_TIMEOUT_S = 3.0
#: An amount takes bulbul:v3 0.4 to 0.6 s; the countdown is 3 s.
TTS_TIMEOUT_S = 3.0
TTS_MODEL = "bulbul:v3"
#: Picked by ear from twelve bulbul:v3 voices on 30 Sep: the clearest readback.
VOICE = "shreya"
TTS_SAMPLE_RATE = 24000


class SarvamError(Exception):
    """Sarvam could not be reached, or refused the request."""


def media_type(content_type: str) -> str:
    """ "audio/webm;codecs=opus" -> "audio/webm". Chrome's recorder adds the codec,
    and Sarvam refuses any type with a parameter on it, though it takes the audio."""
    return content_type.split(";", 1)[0].strip().lower() or "application/octet-stream"


_POOL = ThreadPoolExecutor(max_workers=8, thread_name_prefix="sarvam")


def hedged[T](
    call: Callable[[], T],
    *,
    timeout: float,
    after: float = HEDGE_AFTER_S,
    again: Callable[[], T] | None = None,
) -> T:
    """The call's answer, asked a second time if the first is slow.

    Sarvam answers in about a second, or now and then in twenty-five. Waiting out
    the slow one would leave the shopkeeper standing there; asking again after
    `after` seconds and taking whichever answers first costs one extra request,
    only when it's needed ("hedged requests", The Tail at Scale, 2013). A refusal
    that comes back quickly is not asked again. `again`, if given, is what is
    asked the second time: the munshi asks a second model rather than the same one.
    """
    deadline = time.monotonic() + timeout
    first = _POOL.submit(call)
    done, _ = wait([first], timeout=min(after, timeout))
    if done:
        return first.result()
    pending: set[Future[T]] = {first, _POOL.submit(again or call)}
    failure: SarvamError | None = None
    while pending:
        left = max(0.0, deadline - time.monotonic())
        done, pending = wait(pending, timeout=left, return_when=FIRST_COMPLETED)
        if not done:
            break
        for f in done:
            try:
                return f.result()
            except SarvamError as e:
                failure = e
    raise failure or SarvamError(f"could not reach Sarvam: no answer in {timeout:.0f} s")


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
            files={"file": ("speech", audio, media_type(content_type))},
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


def _post_json(url: str, body: dict[str, Any], *, key: str, timeout: float) -> Any:
    try:
        r = httpx.post(
            url, headers={"api-subscription-key": key}, json=body, timeout=timeout
        )
    except httpx.HTTPError as e:
        raise SarvamError(f"could not reach Sarvam: {e}") from e
    if r.status_code != 200:
        raise SarvamError(f"Sarvam said {r.status_code}: {r.text[:200]}")
    return r.json()


def chat_json(
    system: str, user: str, schema: dict[str, Any], *, key: str, name: str
) -> dict[str, Any]:
    """Sarvam-105B's answer, parsed. Raises SarvamError if it is not JSON."""
    body = {
        "model": os.environ.get("SARVAM_CHAT_MODEL", "sarvam-105b"),
        "temperature": 0,
        "reasoning_effort": None,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": name, "schema": schema, "strict": True},
        },
    }
    reply = hedged(
        lambda: _post_json(CHAT_URL, body, key=key, timeout=CHAT_TIMEOUT_S),
        timeout=CHAT_TIMEOUT_S,
    )
    try:
        answer = json.loads(reply["choices"][0]["message"]["content"])
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as e:
        raise SarvamError(f"Sarvam-105B's reply was not the JSON asked for: {e}") from e
    if not isinstance(answer, dict):
        raise SarvamError("Sarvam-105B's reply was not a JSON object")
    return answer


#: The munshi's model: Sarvam's own model for voice agents. In our test of 12
#: shop conversations it was right 24 of 24 times, replying in about half a
#: second; thinking modes were ten times slower and made mistakes.
MUNSHI_MODEL = "sarvam-105b-conversations"
#: Asked too when the munshi's model is slow, with thinking off.
MUNSHI_SECOND = "sarvam-105b"
#: Room for a reply of a sentence or two, or a tool call.
MUNSHI_MAX_TOKENS = 400


def munshi(
    messages: list[dict[str, Any]], tools: list[dict[str, Any]], *, key: str
) -> dict[str, Any]:
    """The munshi's next message: a reply, or tool calls. If its model hasn't
    answered in HEDGE_AFTER_S, sarvam-105b is asked the same, and the first answer
    is used."""

    def ask(model_name: str) -> dict[str, Any]:
        body: dict[str, Any] = {
            "model": model_name,
            "temperature": 0.2,
            "reasoning_effort": None,
            "max_tokens": MUNSHI_MAX_TOKENS,
            "messages": messages,
        }
        if tools:
            body["tools"] = tools
        reply = _post_json(CHAT_URL, body, key=key, timeout=CHAT_TIMEOUT_S)
        try:
            message = reply["choices"][0]["message"]
        except (KeyError, IndexError, TypeError) as e:
            raise SarvamError(f"Sarvam sent no message: {e}") from e
        if not isinstance(message, dict):
            raise SarvamError("Sarvam's message was not an object")
        return message

    model_name = os.environ.get("SARVAM_MUNSHI_MODEL", MUNSHI_MODEL)
    return hedged(
        lambda: ask(model_name),
        timeout=CHAT_TIMEOUT_S,
        again=lambda: ask(MUNSHI_SECOND),
    )


def transliterate(text: str, *, key: str) -> str:
    """ "Gaikwad" -> गायकवाड़, the way Sarvam's speech-to-text writes it."""
    body = {
        "input": text,
        "source_language_code": "en-IN",
        "target_language_code": LANGUAGE,
    }
    reply = _post_json(TRANSLITERATE_URL, body, key=key, timeout=TRANSLITERATE_TIMEOUT_S)
    out = reply.get("transliterated_text") if isinstance(reply, dict) else None
    if not isinstance(out, str) or not out:
        raise SarvamError("Sarvam sent no transliteration")
    return out


def speaker() -> str:
    """Which of bulbul:v3's voices says it back. `SARVAM_TTS_SPEAKER` in api/.env."""
    return os.environ.get("SARVAM_TTS_SPEAKER", VOICE).strip().lower() or VOICE


def speak(text: str, *, key: str, voice: str) -> bytes:
    """The words, spoken by Sarvam's bulbul:v3, as a WAV file."""
    body = {
        "text": text,
        "language_code": LANGUAGE,
        "speaker": voice,
        "model": TTS_MODEL,
        "speech_sample_rate": TTS_SAMPLE_RATE,
        "output_audio_codec": "wav",
    }
    reply = _post_json(TTS_URL, body, key=key, timeout=TTS_TIMEOUT_S)
    audios = reply.get("audios") if isinstance(reply, dict) else None
    if not isinstance(audios, list) or not audios or not isinstance(audios[0], str):
        raise SarvamError("Sarvam sent no audio")
    try:
        return base64.b64decode(audios[0], validate=True)
    except ValueError as e:
        raise SarvamError("Sarvam's audio was not base64") from e
