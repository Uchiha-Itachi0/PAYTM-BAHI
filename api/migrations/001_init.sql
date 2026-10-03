-- BAHI: the udhaar book both sides can see.
--
-- Eight tables. Several of the product's rules are enforced here by what is
-- absent: there is no due-date column, no fee or interest column anywhere, and
-- no amount on a message. tests/test_schema.py asks Postgres itself and fails
-- the build if any of those ever appears.
--
-- Conventions
--   ids      uuid. The seed uses uuid5 so every rebuild is identical; rows made
--            live get gen_random_uuid().
--   money    bigint paise, always > 0. Never a float, never numeric.
--   time     timestamptz. Stored in UTC, shown in IST.
--   states   text + CHECK, not enum. A CHECK list is one line to change in a
--            migration; an enum value can never be dropped.
--   deletes  nothing cascades, and money rows refuse DELETE outright. A mistake
--            is corrected by a new row, the way an accountant posts a contra
--            entry instead of rubbing out a line.
--   derived  balances, expiry, payment gaps and tonight's decisions are
--            computed, never stored. Anything that depends on the date would be
--            wrong by midnight if it were a column.


-- The kirana. Only what anchors the rest.
CREATE TABLE shops (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name        text NOT NULL,
    locality    text NOT NULL,
    created_at  timestamptz NOT NULL DEFAULT now()
);


-- A person *at one shop*. The name belongs to the shop, not the person: one
-- shop says "Sharma", the chemist says "Sharma ji", the dairy says "Room 19".
--
--   person_id  the Paytm account. It points at Paytm's user system, which we do
--              not hold, so there is no foreign key. NULL means the shopkeeper
--              keeps him by name only, exactly like the notebook. We never
--              store a phone number: a number is only ever used to find the
--              account, and then thrown away.
--   linked_at  when he scanned the udhaar QR, or accepted an invite. A person
--              with no linked_at has been invited and has not said yes, and
--              nothing can be recorded against him until he does.
CREATE TABLE customers (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    shop_id       uuid NOT NULL REFERENCES shops,
    person_id     uuid,
    display_name  text NOT NULL CHECK (length(display_name) > 0),
    tag           text,
    added_at      timestamptz NOT NULL DEFAULT now(),
    linked_at     timestamptz,
    UNIQUE (shop_id, person_id),
    CHECK (linked_at IS NULL OR person_id IS NOT NULL),
    CHECK (linked_at IS NULL OR linked_at >= added_at)
);


-- One udhaar: "₹200 on 22 Sep". There is no shop_id: the customer already
-- belongs to a shop, and a second copy could disagree with the first.
--
--   spoken_text        what Sarvam heard, kept beside the number the rule
--                      parsed out of it. The evidence that the model returned
--                      words and plain code produced the amount. NULL when the
--                      amount was typed.
--   status             recorded   the shopkeeper said it; no answer yet
--                      confirmed  the customer tapped "Yes, I owe"
--                      disputed   the customer tapped "That's not right"
--                      corrected  replaced by a newer entry; counts for nothing
--                      settled    paid in full
--   corrects_entry_id  set on a correction, pointing at the entry it replaces.
--                      The correction needs its own confirmation.
--
-- "Expired" is not a status. Nobody does it; time does. It is computed.
CREATE TABLE entries (
    id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id        uuid NOT NULL REFERENCES customers,
    amount_paise       bigint NOT NULL CHECK (amount_paise > 0),
    note               text,
    spoken_text        text,
    status             text NOT NULL DEFAULT 'recorded' CHECK (
                           status IN ('recorded', 'confirmed', 'disputed',
                                      'corrected', 'settled')),
    corrects_entry_id  uuid REFERENCES entries,
    recorded_at        timestamptz NOT NULL DEFAULT now(),
    CHECK (corrects_entry_id IS DISTINCT FROM id)
);
CREATE INDEX entries_by_customer ON entries (customer_id, recorded_at);


-- The customer's "Yes, I owe ₹200". Its own table because it is its own legal
-- record: the written acknowledgment the Limitation Act counts from.
--
--   wording          the exact words on the button he tapped. Proof that he
--                    acknowledged a sum, and did not promise to pay by a date.
--   UNIQUE entry_id  one per entry, ever. Each acknowledgment restarts the
--                    three-year limit, so an app that could ask twice could
--                    keep a debt alive forever. This database cannot.
--
-- No due date. Not unused: absent.
CREATE TABLE acknowledgments (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    entry_id         uuid NOT NULL UNIQUE REFERENCES entries,
    wording          text NOT NULL CHECK (length(wording) > 0),
    acknowledged_at  timestamptz NOT NULL DEFAULT now()
);


-- Money coming back. Every payment names the entry it pays: the payer's own
-- choice, so nobody has to guess which old debt a ₹500 note was meant for. A
-- part-payment is simply one of several rows against the same entry. A cash
-- lump the shopkeeper records is split oldest-first in code, skipping entries
-- that have expired, so a payment can never quietly revive a dead debt.
CREATE TABLE repayments (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    entry_id      uuid NOT NULL REFERENCES entries,
    amount_paise  bigint NOT NULL CHECK (amount_paise > 0),
    method        text NOT NULL CHECK (method IN ('upi', 'cash')),
    paid_at       timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX repayments_by_entry ON repayments (entry_id, paid_at);


-- One conversation per shopkeeper and customer. The table exists for the two
-- read markers: the inbox's unread badge needs to know what each side last saw.
CREATE TABLE threads (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id       uuid NOT NULL UNIQUE REFERENCES customers,
    shop_read_at      timestamptz,
    customer_read_at  timestamptz,
    created_at        timestamptz NOT NULL DEFAULT now()
);


-- One bubble. People type; only BAHI posts entry cards and reminders.
--
-- There is no amount column. A shopkeeper cannot send a demand for money,
-- because a message has nowhere to carry one: the customer's Pay button comes
-- from his own open entries, never from a message.
CREATE TABLE messages (
    id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    thread_id  uuid NOT NULL REFERENCES threads,
    author     text NOT NULL CHECK (author IN ('shop', 'customer', 'bahi')),
    kind       text NOT NULL CHECK (kind IN ('text', 'entry', 'reminder')),
    body       text NOT NULL CHECK (length(body) > 0),
    entry_id   uuid REFERENCES entries,
    sent_at    timestamptz NOT NULL DEFAULT now(),
    CHECK ((author IN ('shop', 'customer')) = (kind = 'text')),
    CHECK (kind <> 'entry' OR entry_id IS NOT NULL)
);
CREATE INDEX messages_by_thread ON messages (thread_id, sent_at);


-- Someone at the counter. Scanning the udhaar QR says "I'm here" and nothing
-- more: it records no debt. Whether a scan is still waiting is computed (no
-- entry, not left, scanned in the last three minutes), so a prank scan simply
-- expires.
--
--   entry_id  set once, when the shopkeeper's amount is attached. The claim is
--             UPDATE ... WHERE entry_id IS NULL RETURNING id, so a scan is used
--             exactly once even if two utterances race for it. UNIQUE, so one
--             entry can come from only one scan.
--   left_at   the customer tapped Cancel.
CREATE TABLE scans (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id  uuid NOT NULL REFERENCES customers,
    scanned_at   timestamptz NOT NULL DEFAULT now(),
    entry_id     uuid UNIQUE REFERENCES entries,
    left_at      timestamptz,
    CHECK (left_at IS NULL OR entry_id IS NULL)
);
CREATE INDEX scans_waiting ON scans (scanned_at)
    WHERE entry_id IS NULL AND left_at IS NULL;


-- ── The database refuses, so no code path has to remember to ────────────────

-- An entry's amount, customer and time never change once written. The status
-- moves; the facts do not. A wrong amount is fixed with a correction entry.
CREATE FUNCTION entries_facts_are_fixed() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.amount_paise <> OLD.amount_paise
       OR NEW.customer_id <> OLD.customer_id
       OR NEW.recorded_at <> OLD.recorded_at
       OR NEW.corrects_entry_id IS DISTINCT FROM OLD.corrects_entry_id THEN
        RAISE EXCEPTION 'an entry''s amount, customer and time never change; '
                        'record a correction instead';
    END IF;
    RETURN NEW;
END $$;

CREATE TRIGGER entries_facts_are_fixed
    BEFORE UPDATE ON entries
    FOR EACH ROW EXECUTE FUNCTION entries_facts_are_fixed();

-- Money rows are never deleted. This covers the entry, the customer's word on
-- it, and the payment against it.
CREATE FUNCTION money_rows_are_kept() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION '% rows are never deleted; record a new row instead',
                    TG_TABLE_NAME;
END $$;

CREATE TRIGGER entries_are_kept BEFORE DELETE ON entries
    FOR EACH ROW EXECUTE FUNCTION money_rows_are_kept();
CREATE TRIGGER acknowledgments_are_kept BEFORE DELETE ON acknowledgments
    FOR EACH ROW EXECUTE FUNCTION money_rows_are_kept();
CREATE TRIGGER repayments_are_kept BEFORE DELETE ON repayments
    FOR EACH ROW EXECUTE FUNCTION money_rows_are_kept();
