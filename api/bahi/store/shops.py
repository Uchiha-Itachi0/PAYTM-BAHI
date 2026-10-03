"""Shops: the one table nothing else in the product ever changes."""

from __future__ import annotations

from dataclasses import dataclass

from psycopg.rows import class_row

from bahi.store.db import Conn


@dataclass(frozen=True, slots=True)
class Shop:
    id: str
    name: str
    locality: str


SELECT = "SELECT id::text AS id, name, locality FROM shops"


def get(con: Conn, shop_id: str) -> Shop | None:
    with con.cursor(row_factory=class_row(Shop)) as cur:
        return cur.execute(SELECT + " WHERE id = %s", (shop_id,)).fetchone()


def all_shops(con: Conn) -> list[Shop]:
    with con.cursor(row_factory=class_row(Shop)) as cur:
        return cur.execute(SELECT + " ORDER BY created_at, name").fetchall()
