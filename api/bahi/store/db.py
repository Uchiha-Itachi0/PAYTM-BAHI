"""One place that knows how to reach Postgres."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import psycopg
from dotenv import load_dotenv

API_DIR = Path(__file__).resolve().parents[2]
load_dotenv(API_DIR / ".env")

Conn = psycopg.Connection[Any]


def url() -> str:
    """DATABASE_URL, or the local Homebrew default.

    On macOS the Homebrew Postgres role is your own username with no password, so
    the default works without anyone writing a .env first. One fewer step between a
    clean clone and a populated database, which matters on the day.

    The default names no user. libpq then uses the account the process really runs
    as, rather than the $USER variable, which a launcher can set to anything.
    """
    return os.environ.get("DATABASE_URL") or "postgresql://localhost:5432/bahi"


def connect(*, autocommit: bool = False) -> Conn:
    return psycopg.connect(url(), autocommit=autocommit)


def describe() -> str:
    """The connection string with any password removed, for printing."""
    u = url()
    if "@" not in u:
        return u
    head, tail = u.split("@", 1)
    scheme, creds = head.split("//", 1)
    return f"{scheme}//{creds.split(':', 1)[0]}@{tail}"
