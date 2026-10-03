from __future__ import annotations

from collections.abc import Iterator

import psycopg
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

    The transaction is opened explicitly. psycopg's `con.transaction()` makes a
    savepoint only when a transaction is already in progress; on an idle
    connection it starts a real one and commits it. Opening one here means every
    `transaction()` inside a test is a savepoint, and everything is rolled back.
    """
    con.rollback()
    con.execute("SELECT 1")
    assert con.info.transaction_status == psycopg.pq.TransactionStatus.INTRANS
    yield con
    con.rollback()


@pytest.fixture(autouse=True)
def voice_offline(monkeypatch: pytest.MonkeyPatch) -> None:
    """No test calls Sarvam. api/.env may hold a key and SARVAM_OFFLINE=0 for the
    app; the suite runs voice as the demo does with the wifi off, and a test of the
    online path fakes Sarvam itself."""
    monkeypatch.setenv("SARVAM_OFFLINE", "1")
    monkeypatch.delenv("SARVAM_API_KEY", raising=False)
    # Nor Cognee, nor memory's background worker: a test runs a round itself.
    monkeypatch.setenv("MEMORY_WORKER", "off")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
