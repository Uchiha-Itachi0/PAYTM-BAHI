"""Applies api/migrations/*.sql in order, once each.

Plain numbered SQL files, tracked in schema_migrations. No ORM and no generated
migrations: the schema is where half of the product's rules live, so it is written
by hand and read by humans.

    uv run python -m data.migrate            # apply what is pending
    uv run python -m data.migrate --reset    # drop everything first
"""

from __future__ import annotations

import sys
from pathlib import Path

from data import db

MIGRATIONS = Path(__file__).resolve().parents[1] / "migrations"

TRACKING = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version    text PRIMARY KEY,
    applied_at timestamptz NOT NULL DEFAULT now()
)
"""


def reset(con: db.Conn) -> None:
    """Drop the public schema and rebuild it empty.

    Blunt on purpose. The seed is deterministic and rebuilds in seconds, so there is
    never anything in this database worth migrating carefully around.
    """
    with con.cursor() as cur:
        cur.execute("DROP SCHEMA public CASCADE")
        cur.execute("CREATE SCHEMA public")
        # Paytm's simulated accounts (011) live beside the book, not in it.
        cur.execute("DROP SCHEMA IF EXISTS paytm CASCADE")
    con.commit()
    print("  dropped and recreated schema public")


def main() -> int:
    print(f"postgres  {db.describe()}")
    try:
        con = db.connect()
    except Exception as exc:  # noqa: BLE001 - the message is the whole point
        print(f"\ncannot connect: {exc}", file=sys.stderr)
        print(
            "\nIs Postgres running, and does the database exist?\n"
            "  brew services start postgresql@17\n"
            "  createdb bahi",
            file=sys.stderr,
        )
        return 1

    with con:
        if "--reset" in sys.argv:
            reset(con)

        with con.cursor() as cur:
            cur.execute(TRACKING)
            con.commit()
            cur.execute("SELECT version FROM schema_migrations")
            done = {row[0] for row in cur.fetchall()}

            pending = sorted(p for p in MIGRATIONS.glob("*.sql") if p.stem not in done)
            if not pending:
                print("  nothing pending")
                return 0

            for path in pending:
                cur.execute(path.read_text(encoding="utf-8"))
                cur.execute(
                    "INSERT INTO schema_migrations (version) VALUES (%s)", (path.stem,)
                )
                con.commit()
                print(f"  applied {path.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
