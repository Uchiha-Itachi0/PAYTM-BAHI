"""Health, and what time the product thinks it is."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter
from pydantic import BaseModel

from bahi import clock

router = APIRouter(tags=["system"])


class Health(BaseModel):
    ok: bool
    now: datetime


@router.get("/health")
def health() -> Health:
    return Health(ok=True, now=clock.now())
