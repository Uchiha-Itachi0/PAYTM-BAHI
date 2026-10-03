"""What happened at a shop since a moment: for the Soundbox and the screen.

Read from the rows themselves (a scan, an acknowledgment, a dispute, a UPI
payment, a customer's message), so there is no second record of events to keep
in step with the first.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from psycopg.rows import class_row

from bahi.store.db import Conn

#: At most this many at once; a screen that was away hears only the latest.
MOST = 20


@dataclass(frozen=True, slots=True)
class Event:
    kind: str
    at: datetime
    customer_id: str
    display_name: str
    amount_paise: int | None


SINCE = """
SELECT * FROM (
    SELECT 'scanned' AS kind, s.scanned_at AS at, c.id::text AS customer_id,
           c.display_name, NULL::bigint AS amount_paise
    FROM scans s JOIN customers c ON c.id = s.customer_id
    WHERE c.shop_id = %(shop)s AND s.scanned_at > %(after)s AND s.scanned_at <= %(now)s
  UNION ALL
    SELECT 'confirmed', a.acknowledged_at, c.id::text, c.display_name, e.amount_paise
    FROM acknowledgments a
    JOIN entries e ON e.id = a.entry_id
    JOIN customers c ON c.id = e.customer_id
    WHERE c.shop_id = %(shop)s
      AND a.acknowledged_at > %(after)s AND a.acknowledged_at <= %(now)s
  UNION ALL
    SELECT 'disputed', e.disputed_at, c.id::text, c.display_name, e.amount_paise
    FROM entries e JOIN customers c ON c.id = e.customer_id
    WHERE c.shop_id = %(shop)s
      AND e.disputed_at > %(after)s AND e.disputed_at <= %(now)s
  UNION ALL
    SELECT 'paid', r.paid_at, c.id::text, c.display_name, sum(r.amount_paise)::bigint
    FROM repayments r
    JOIN entries e ON e.id = r.entry_id
    JOIN customers c ON c.id = e.customer_id
    WHERE c.shop_id = %(shop)s AND r.method = 'upi'
      AND r.paid_at > %(after)s AND r.paid_at <= %(now)s
    GROUP BY r.paid_at, c.id, c.display_name
  UNION ALL
    SELECT 'message', m.sent_at, c.id::text, c.display_name, NULL
    FROM messages m
    JOIN threads t ON t.id = m.thread_id
    JOIN customers c ON c.id = t.customer_id
    WHERE c.shop_id = %(shop)s AND m.author = 'customer'
      AND m.sent_at > %(after)s AND m.sent_at <= %(now)s
) happened
ORDER BY at DESC
LIMIT %(most)s
"""


def since(con: Conn, shop_id: str, after: datetime, now: datetime) -> list[Event]:
    """Everything after `after` up to `now`, oldest first."""
    with con.cursor(row_factory=class_row(Event)) as cur:
        rows = cur.execute(
            SINCE, {"shop": shop_id, "after": after, "now": now, "most": MOST}
        ).fetchall()
    return list(reversed(rows))
