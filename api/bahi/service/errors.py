"""The four ways a request can be refused, and the status code each one gets."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from psycopg import errors as pg

from bahi.domain.lifecycle import IllegalMove


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
    # The database's own refusals: a second acknowledgment, a changed amount.
    app.add_exception_handler(pg.UniqueViolation, reply(409))
    app.add_exception_handler(pg.RaiseException, reply(409))
