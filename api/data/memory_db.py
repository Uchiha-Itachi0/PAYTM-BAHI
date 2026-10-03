"""Memory's databases on this machine's Postgres: `make memory-db`. Run it once.

- a role of its own, `bahi_memory`, with a random password: Cognee needs one to
  connect, and with its own role it can't read the book;
- `bahi_memory` (the app's) and `bahi_memory_check` (the tests' and the live
  check's), owned by that role, with pgvector;
- MEMORY_DATABASE_URL appended to api/.env, if it isn't there yet.

Needs pgvector installed into Postgres first: `brew install pgvector`. Run again,
it changes nothing it has already done; it never prints the password.
"""

from __future__ import annotations

import re
import secrets
import sys

import psycopg
from psycopg import sql

from bahi.store.db import API_DIR, url

ROLE = "bahi_memory"
DATABASES = ("bahi_memory", "bahi_memory_check")
ENV = API_DIR / ".env"


def main() -> int:
    env = ENV.read_text(encoding="utf-8") if ENV.exists() else ""
    have_url = re.search(r"^MEMORY_DATABASE_URL=", env, re.M) is not None
    admin = re.sub(r"/[^/?]*(\?|$)", r"/postgres\1", url(), count=1)
    with psycopg.connect(admin, autocommit=True) as con:
        if not con.execute(
            "SELECT 1 FROM pg_available_extensions WHERE name = 'vector'"
        ).fetchone():
            sys.exit("pgvector isn't installed in this Postgres: brew install pgvector")
        exists = con.execute(
            "SELECT 1 FROM pg_roles WHERE rolname = %s", (ROLE,)
        ).fetchone()
        password = None
        if not exists or not have_url:
            password = secrets.token_urlsafe(24)
            verb = "ALTER" if exists else "CREATE"
            con.execute(
                sql.SQL(verb + " ROLE {} LOGIN PASSWORD {}").format(
                    sql.Identifier(ROLE), sql.Literal(password)
                )
            )
            print(f"  {verb.lower()}d role {ROLE}")
        for name in DATABASES:
            if not con.execute(
                "SELECT 1 FROM pg_database WHERE datname = %s", (name,)
            ).fetchone():
                con.execute(
                    sql.SQL("CREATE DATABASE {} OWNER {}").format(
                        sql.Identifier(name), sql.Identifier(ROLE)
                    )
                )
                print(f"  created {name}")
    for name in DATABASES:
        db_url = re.sub(r"/[^/?]*(\?|$)", rf"/{name}\1", url(), count=1)
        with psycopg.connect(db_url, autocommit=True) as con:
            con.execute("CREATE EXTENSION IF NOT EXISTS vector")
    if password is not None:
        line = f"MEMORY_DATABASE_URL=postgresql://{ROLE}:{password}@localhost:5432/bahi_memory\n"
        with ENV.open("a", encoding="utf-8") as f:
            f.write(
                "\n# Cognee memory (M3): its own role and database on this "
                "machine's Postgres.\n" + line
            )
        print("  wrote MEMORY_DATABASE_URL to api/.env")
    print("  memory databases ready")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
