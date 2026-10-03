"""Writes the two contract files the frontend builds against.

contract/shop.json     the shopkeeper's book, exactly what GET /shops/{id}/book
                       returns for the seeded shop: the same code builds both
contract/openapi.json  the API's spec, from which the frontend's TypeScript types
                       are generated (`npm run types` in web/)

Both are generated, never edited by hand. `make db` writes them.

    uv run python -m data.contract
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from bahi.domain.book import book
from bahi.service import app, views
from bahi.store import book as book_store
from bahi.store import shops
from data import db
from data.world import HOME, TODAY, uid

CONTRACT = Path(__file__).resolve().parents[2] / "contract"
SHOP = CONTRACT / "shop.json"
OPENAPI = CONTRACT / "openapi.json"


def build(con: db.Conn) -> dict[str, Any]:
    shop_id = str(uid("shop", HOME))
    s = shops.get(con, shop_id)
    assert s is not None, "the seeded shop is missing: run `make db`"
    b = book(book_store.load(con, shop_id), TODAY)
    return views.book_out(s, b).model_dump(mode="json")


def dump(data: Any) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


def write(con: db.Conn) -> Path:
    CONTRACT.mkdir(exist_ok=True)
    SHOP.write_text(dump(build(con)), encoding="utf-8")
    OPENAPI.write_text(dump(app.openapi()), encoding="utf-8")
    return SHOP


def main() -> int:
    with db.connect() as con:
        print(f"  wrote {write(con)} and {OPENAPI.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
