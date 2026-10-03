"""Per-request plumbing: one connection, one transaction, one ETag."""

from __future__ import annotations

import hashlib
from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Request, Response
from pydantic import BaseModel

from bahi.store import db


def connection() -> Iterator[db.Conn]:
    """One connection and one transaction per request.

    Commits after the handler returns and before the response is sent
    (`scope="function"`), so a phone that polls straight after a write always
    sees it. Any exception rolls the whole request back.
    """
    con = db.connect()
    try:
        yield con
        con.commit()
    except BaseException:
        con.rollback()
        raise
    finally:
        con.close()


Con = Annotated[db.Conn, Depends(connection, scope="function")]


def etagged(request: Request, body: BaseModel) -> Response:
    """The body, or 304 Not Modified if the client already has it.

    Both screens poll every two seconds. Most of those polls find nothing new,
    and this answers them with an empty 304 instead of the whole book.
    """
    raw = body.model_dump_json().encode()
    tag = '"' + hashlib.sha1(raw).hexdigest()[:20] + '"'
    if request.headers.get("if-none-match") == tag:
        return Response(status_code=304, headers={"ETag": tag})
    return Response(raw, media_type="application/json", headers={"ETag": tag})
