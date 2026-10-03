"""The BAHI API.

Sync handlers on purpose. Two phones and a laptop poll every two seconds; the
thread pool FastAPI runs sync handlers on is far bigger than that, and async would
buy throughput we cannot use at the cost of a class of missing-await bugs.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from bahi.memory import worker
from bahi.service import errors
from bahi.service.routes import (
    chat,
    customer,
    munshi,
    people,
    shop,
    system,
    tonight,
    voice,
)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    worker.start()  # memory's background work (M3), when voice is online
    yield


app = FastAPI(
    title="BAHI",
    version="0.1.0",
    description="The udhaar book both sides can see. All data is synthetic.",
    lifespan=lifespan,
)
errors.install(app)
app.include_router(system.router)
app.include_router(shop.router)
app.include_router(customer.router)
app.include_router(voice.router)
app.include_router(munshi.router)
app.include_router(chat.router)
app.include_router(people.router)
app.include_router(tonight.router)
