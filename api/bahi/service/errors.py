"""The ways a request can be refused, and the status code each one gets."""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from psycopg import errors as pg

from bahi.domain.lifecycle import IllegalMove
from bahi.voice import VoiceOffline
from bahi.voice.sarvam import SarvamError

log = logging.getLogger(__name__)

#: What the shopkeeper reads when Sarvam fails. What Sarvam said goes to the log.
SARVAM_FAILED = "Sarvam couldn't hear that just now. Say it again, or type it."


class NotFound(Exception):
    """404: no such shop, customer, entry or scan."""


class Conflict(Exception):
    """409: the request is well formed but the state of the world says no."""


class Forbidden(Exception):
    """403: this person may not do this to that entry."""


def install(app: FastAPI) -> None:
    def reply(status: int):  # type: ignore[no-untyped-def]
        async def handler(_: Request, exc: Exception) -> JSONResponse:
            return JSONResponse({"detail": str(exc)}, status_code=status)

        return handler

    app.add_exception_handler(NotFound, reply(404))
    app.add_exception_handler(Forbidden, reply(403))
    app.add_exception_handler(Conflict, reply(409))
    app.add_exception_handler(IllegalMove, reply(409))
    # Voice: switched off with nothing on disk (503), or Sarvam failed (502).
    # Either way the screen offers the keypad.
    app.add_exception_handler(VoiceOffline, reply(503))
    app.add_exception_handler(SarvamError, sarvam_failed)
    # The database's own refusals: a second acknowledgment, a changed amount.
    app.add_exception_handler(pg.UniqueViolation, reply(409))
    app.add_exception_handler(pg.RaiseException, reply(409))


async def sarvam_failed(_: Request, exc: Exception) -> JSONResponse:
    log.warning("Sarvam failed: %s", exc)
    return JSONResponse({"detail": SARVAM_FAILED}, status_code=502)
