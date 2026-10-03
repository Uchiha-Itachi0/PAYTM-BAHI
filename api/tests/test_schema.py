"""The rules the database enforces, checked against the database itself.

Each of these would otherwise be a convention someone could forget. Here, if a
migration ever adds a late-fee column or lets a shopkeeper post a demand, the
build fails.
"""

from __future__ import annotations

from typing import Any

import psycopg
import pytest
from psycopg import errors

from data import db

#: Words no column name may contain. Rule 1 (no due date) and rule 2 (never a
#: rupee above the price).
FORBIDDEN = {
    "fee",
    "fees",
    "interest",
    "charge",
    "charges",
    "penalty",
    "due",
    "overdue",
    "late",
}


def columns(con: db.Conn) -> list[tuple[str, str, str]]:
    with con.cursor() as cur:
        cur.execute(
            """
            SELECT table_name, column_name, data_type
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name <> 'schema_migrations'
            """
        )
        return list(cur.fetchall())


def one(con: db.Conn, sql: str, *args: Any) -> Any:
    with con.cursor() as cur:
        cur.execute(sql, args)
        row = cur.fetchone()
        assert row is not None, sql
        return row[0]


def refused(con: db.Conn, error: type[Exception], sql: str, *args: Any) -> None:
    """The statement fails with `error`, inside a savepoint so the test goes on."""
    with pytest.raises(error), con.transaction(), con.cursor() as cur:
        cur.execute(sql, args)


# ── what is absent ───────────────────────────────────────────────────────────


def test_no_column_can_hold_a_fee_interest_or_due_date(con: db.Conn) -> None:
    bad = [
        f"{table}.{column}"
        for table, column, _ in columns(con)
        if FORBIDDEN & set(column.split("_"))
    ]
    assert bad == []


def test_a_message_has_nowhere_to_carry_an_amount(con: db.Conn) -> None:
    on_messages = [c for t, c, _ in columns(con) if t == "messages"]
    assert not [c for c in on_messages if "amount" in c or c.endswith("_paise")]


def test_money_is_bigint_paise_and_nothing_is_a_float(con: db.Conn) -> None:
    cols = columns(con)
    assert all(kind == "bigint" for _, c, kind in cols if c.endswith("_paise"))
    assert [
        c for _, c, kind in cols if kind in ("numeric", "real", "double precision")
    ] == []


# ── what is refused ──────────────────────────────────────────────────────────


def test_an_entry_can_be_acknowledged_only_once(tx: db.Conn) -> None:
    entry = one(tx, "SELECT entry_id FROM acknowledgments LIMIT 1")
    refused(
        tx,
        errors.UniqueViolation,
        "INSERT INTO acknowledgments (entry_id, wording) VALUES (%s, 'Yes, I owe it')",
        entry,
    )


def test_people_can_only_type(tx: db.Conn) -> None:
    thread = one(tx, "SELECT id FROM threads LIMIT 1")
    entry = one(tx, "SELECT id FROM entries LIMIT 1")
    post = (
        "INSERT INTO messages (thread_id, author, kind, body, entry_id) "
        "VALUES (%s, %s, %s, %s, %s)"
    )

    # The shopkeeper cannot post a reminder or an entry card, only words.
    refused(tx, errors.CheckViolation, post, thread, "shop", "reminder", "Pay up", None)
    refused(tx, errors.CheckViolation, post, thread, "shop", "entry", "₹500", entry)
    refused(tx, errors.CheckViolation, post, thread, "customer", "entry", "₹1", entry)
    # And BAHI never speaks as a person.
    refused(tx, errors.CheckViolation, post, thread, "bahi", "text", "Hello", None)


def test_an_amount_must_be_more_than_zero(tx: db.Conn) -> None:
    customer = one(tx, "SELECT id FROM customers LIMIT 1")
    entry = one(tx, "SELECT id FROM entries LIMIT 1")
    refused(
        tx,
        errors.CheckViolation,
        "INSERT INTO entries (customer_id, amount_paise) VALUES (%s, 0)",
        customer,
    )
    refused(
        tx,
        errors.CheckViolation,
        "INSERT INTO repayments (entry_id, amount_paise, method) "
        "VALUES (%s, -100, 'upi')",
        entry,
    )


def test_a_status_outside_the_list_is_refused(tx: db.Conn) -> None:
    customer = one(tx, "SELECT id FROM customers LIMIT 1")
    refused(
        tx,
        errors.CheckViolation,
        "INSERT INTO entries (customer_id, amount_paise, status) "
        "VALUES (%s, 100, 'overdue')",
        customer,
    )


def test_an_entrys_amount_never_changes_but_its_status_can(tx: db.Conn) -> None:
    entry = one(tx, "SELECT id FROM entries WHERE status = 'confirmed' LIMIT 1")
    refused(
        tx,
        errors.RaiseException,
        "UPDATE entries SET amount_paise = amount_paise + 100 WHERE id = %s",
        entry,
    )
    with tx.cursor() as cur:
        cur.execute("UPDATE entries SET status = 'settled' WHERE id = %s", (entry,))
        assert cur.rowcount == 1


@pytest.mark.parametrize("table", ["entries", "acknowledgments", "repayments"])
def test_money_rows_are_never_deleted(tx: db.Conn, table: str) -> None:
    row = one(tx, f"SELECT id FROM {table} LIMIT 1")  # noqa: S608 - fixed names
    refused(tx, errors.RaiseException, f"DELETE FROM {table} WHERE id = %s", row)  # noqa: S608


def test_nobody_is_linked_without_an_account(tx: db.Conn) -> None:
    shop = one(tx, "SELECT id FROM shops LIMIT 1")
    refused(
        tx,
        errors.CheckViolation,
        "INSERT INTO customers (shop_id, display_name, linked_at) "
        "VALUES (%s, 'X', now())",
        shop,
    )


def test_a_scan_is_claimed_exactly_once(tx: db.Conn) -> None:
    customer = one(tx, "SELECT id FROM customers WHERE linked_at IS NOT NULL LIMIT 1")
    scan = one(tx, "INSERT INTO scans (customer_id) VALUES (%s) RETURNING id", customer)
    first = one(
        tx,
        "INSERT INTO entries (customer_id, amount_paise) VALUES (%s, 20000) RETURNING id",
        customer,
    )
    second = one(
        tx,
        "INSERT INTO entries (customer_id, amount_paise) VALUES (%s, 30000) RETURNING id",
        customer,
    )

    claim = """
        UPDATE scans SET entry_id = %s
        WHERE id = %s AND entry_id IS NULL AND left_at IS NULL
          AND scanned_at > now() - interval '3 minutes'
        RETURNING id
    """
    with tx.cursor() as cur:
        cur.execute(claim, (first, scan))
        assert cur.fetchone() is not None
        cur.execute(claim, (second, scan))
        assert cur.fetchone() is None


def test_the_connection_is_real(con: db.Conn) -> None:
    """Guards the guards: if this runs, the tests above ran against Postgres."""
    assert isinstance(con, psycopg.Connection)
