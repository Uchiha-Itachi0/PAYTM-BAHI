"""Reads the seed back and prints what it contains.

The proof that `make db` did what it says, in a form someone can read aloud: how
many rows, what the book adds up to, and each person's own rhythm next to where
he is today. Every figure below comes from Postgres through the domain code, not
from the generator's intentions.

    uv run python -m data.check
"""

from __future__ import annotations

from collections import Counter

from bahi.domain.book import book
from bahi.domain.money import rupees
from bahi.domain.rhythm import rhythm
from bahi.store import book as store
from data import db
from data.personas import CAST
from data.world import HOME, SHOPS, TODAY, uid

TABLES = (
    "shops",
    "customers",
    "entries",
    "acknowledgments",
    "repayments",
    "threads",
    "messages",
    "scans",
)


def main() -> int:
    with db.connect() as con:
        with con.cursor() as cur:
            print("rows")
            for table in TABLES:
                cur.execute(f"SELECT count(*) FROM {table}")  # noqa: S608 - fixed names
                row = cur.fetchone()
                print(f"  {table:<16} {row[0] if row else 0:>6,}")

        customers = store.load(con, str(uid("shop", HOME)))

    b = book(customers, TODAY)
    print(f"\n{SHOPS[HOME][0]}, as of {TODAY:%d %b %Y}")
    print(
        f"  in the book    {b.customer_count}  (+{b.invited_count} invited, not accepted)"
    )
    print(f"  owe something  {b.owing_count}")
    print(f"  outstanding    {rupees(b.outstanding_paise)}")
    chips = Counter(ln.chip for ln in b.lines)
    print("  chips          " + "  ".join(f"{k} {v}" for k, v in sorted(chips.items())))

    by_name = {c.display_name: c for c in customers}
    lines = {ln.display_name: ln for ln in b.lines}
    print("\nthe cast            usual   max    n   day   owes        chip")
    for p in CAST:
        c = by_name.get(p.name)
        if c is None or p.joined == "invited":
            continue
        r = rhythm(c.paid_on, TODAY)
        ln = lines.get(p.name)
        day = _n(ln.day if ln else r.day)
        owes = rupees(ln.balance_paise) if ln else "-"
        print(
            f"  {p.name:<16} {_n(r.median_gap):>6} {_n(r.max_gap):>5} {r.n:>4} "
            f"{day:>5}   {owes:<10}  {ln.chip if ln else 'square'}"
        )

    usual = Counter(
        r.median_gap
        for c in customers
        if (r := rhythm(c.paid_on, TODAY)).median_gap is not None
    )
    print("\neveryone's usual gap, in days")
    for gap, n in sorted(usual.items()):
        print(f"  {gap:>3}  {'#' * n}")
    return 0


def _n(v: int | None) -> str:
    return "-" if v is None else str(v)


if __name__ == "__main__":
    raise SystemExit(main())
