"""How Cognee is set up for BAHI: everything on this machine, Sarvam to think.

- Storage: its own database on the local Postgres (MEMORY_DATABASE_URL, the
  `bahi_memory` role, which can't read the book). Graph, vectors and Cognee's
  own records all live there; each shop's memory in its own schema.
- Thinking: Sarvam's sarvam-105b, with thinking off. With it on, Sarvam spent
  its whole 2,048-token reply on reasoning and wrote no answer (trial, 1 Oct).
- Vectors, to search by meaning: OpenAI's text-embedding-3-small. Sarvam has no
  embeddings API.
- Nothing goes to Cognee itself: its telemetry is off, it keeps no log files,
  and it reads no .env but its own empty one (cognee.env).

Every setting is passed here, before Cognee is first imported.
"""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path
from urllib.parse import urlparse, urlunparse

from bahi import voice

API_DIR = Path(__file__).resolve().parents[2]
HOME = API_DIR / ".cognee"
SARVAM_V1 = "https://api.sarvam.ai/v1"
THINKER = "openai/sarvam-105b"
EMBEDDER = "openai/text-embedding-3-small"
EMBEDDING_SIZE = 1536


def url() -> str | None:
    """MEMORY_DATABASE_URL; MEMORY_DATABASE names another database on the same
    server (the test stack's bahi_memory_check), so its password stays in .env."""
    base = os.environ.get("MEMORY_DATABASE_URL") or None
    other = os.environ.get("MEMORY_DATABASE", "").strip()
    if base is None or not other:
        return base
    return urlunparse(urlparse(base)._replace(path=f"/{other}"))


def installed() -> bool:
    """Whether Cognee is installed at all: the laptop's default; the deployed
    server leaves it out. Looked for, never imported."""
    return importlib.util.find_spec("cognee") is not None


def enabled() -> bool:
    """Cognee is on when COGNEE isn't off, it is installed, it has its database
    and both keys, and voice is online. On the laptop it is on; the deployed
    server sets COGNEE=off and doesn't install it.

    Off, Cognee is never loaded and nothing is sent to it. BAHI still keeps what
    was said, Tonight still waits on it, and a question across customers reads
    the book's own list instead."""
    if os.environ.get("COGNEE", "on").lower() in ("off", "0", "false"):
        return False
    if not installed():
        return False
    return bool(
        url()
        and voice.api_key()
        and os.environ.get("OPENAI_API_KEY")
        and not voice.offline()
    )


def cognee_env(database_url: str) -> dict[str, str]:
    """Cognee's settings, as environment variables. Holds keys: never printed."""
    db = urlparse(database_url)
    where = {
        "HOST": db.hostname or "localhost",
        "PORT": str(db.port or 5432),
        "USERNAME": db.username or "",
        "PASSWORD": db.password or "",
        "NAME": db.path.lstrip("/"),
    }
    env = {
        "COGNEE_ENV_FILE": str(Path(__file__).with_name("cognee.env")),
        "TELEMETRY_DISABLED": "1",
        "COGNEE_LOG_FILE": "false",
        "LOG_LEVEL": os.environ.get("MEMORY_LOG_LEVEL", "WARNING"),
        "CACHING": "false",
        "DATA_ROOT_DIRECTORY": str(HOME / "data"),
        "SYSTEM_ROOT_DIRECTORY": str(HOME / "system"),
        "DB_PROVIDER": "postgres",
        "VECTOR_DB_PROVIDER": "pgvector",
        "GRAPH_DATABASE_PROVIDER": "postgres",
        # One schema per shop's dataset, in the one database.
        "VECTOR_DATASET_DATABASE_HANDLER": "pgvector_shared",
        "GRAPH_DATASET_DATABASE_HANDLER": "postgres_graph_shared",
        "LLM_PROVIDER": "custom",
        "LLM_MODEL": THINKER,
        "LLM_ENDPOINT": SARVAM_V1,
        "LLM_API_KEY": voice.api_key() or "",
        "LLM_ARGS": '{"extra_body": {"reasoning_effort": null}}',
        "EMBEDDING_PROVIDER": "openai",
        "EMBEDDING_MODEL": EMBEDDER,
        "EMBEDDING_DIMENSIONS": str(EMBEDDING_SIZE),
        "EMBEDDING_API_KEY": os.environ.get("OPENAI_API_KEY", ""),
    }
    for k, v in where.items():
        env[f"DB_{k}"] = v
        env[f"VECTOR_DB_{k}"] = v
        env[f"GRAPH_DATABASE_{k}"] = v
    return env
