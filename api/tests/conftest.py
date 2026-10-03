from __future__ import annotations

from collections.abc import Iterator

import pytest

from data import db


@pytest.fixture(scope="session")
def con() -> Iterator[db.Conn]:
    """A connection to the seeded database, or a skip.

    Skipping beats failing when someone has cloned the repo and not run `make db`
    yet: a red suite on a fresh clone teaches people to ignore the suite.
    """
    try:
        c = db.connect()
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"no database ({exc}); run `make db`")
    with c:
        with c.cursor() as cur:
            cur.execute("SELECT to_regclass('public.entries') IS NOT NULL")
            row = cur.fetchone()
            if not row or not row[0]:
                pytest.skip("no schema; run `make db`")
            cur.execute("SELECT count(*) FROM entries")
            row = cur.fetchone()
            if not row or row[0] == 0:
                pytest.skip("database is empty; run `make db`")
        c.rollback()
        yield c


@pytest.fixture
def tx(con: db.Conn) -> Iterator[db.Conn]:
    """The seeded database inside a transaction that is always rolled back.

    Tests that try to break a rule write here, so the seed is never changed.
    """
    yield con
    con.rollback()
