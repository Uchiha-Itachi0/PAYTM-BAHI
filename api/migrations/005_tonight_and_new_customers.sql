-- V4 and V6: the reminders Tonight drafted, and a new customer on the munshi's card.


-- Tonight's reminders. Who gets one is not stored: it is worked out from the
-- book every time it is asked (domain/tonight.py), so it is never a day stale.
-- What is stored is what can't be worked out again: the words the munshi wrote,
-- the shopkeeper's Stop, and the message it became once sent.
--
--   for_day   the day it goes out. One per customer per day.
--   send_at   the hour he usually pays, worked out when it was drafted
--   written   munshi: Sarvam's model wrote it. words: our own sentence, because
--             voice was off or the model's words did not pass our checks
--   status    planned  goes out at send_at
--             stopped  the shopkeeper said no
--             sent     posted in the thread; message_id is set
CREATE TABLE reminders (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id  uuid NOT NULL REFERENCES customers,
    for_day      date NOT NULL,
    send_at      timestamptz NOT NULL,
    body         text NOT NULL CHECK (length(body) > 0),
    written      text NOT NULL CHECK (written IN ('munshi', 'words')),
    status       text NOT NULL DEFAULT 'planned' CHECK (
                     status IN ('planned', 'stopped', 'sent')),
    message_id   uuid UNIQUE REFERENCES messages,
    created_at   timestamptz NOT NULL DEFAULT now(),
    UNIQUE (customer_id, for_day),
    CHECK ((status = 'sent') = (message_id IS NOT NULL))
);


-- The munshi can put someone who isn't in the book yet on its card: "रमेश को पाँच
-- सौ" → "Ramesh isn't in your book. Add him, and ₹500 udhaar?" His yes adds him,
-- by name only, then writes the entry. With no amount, the card only adds him.
--
--   new_name, new_tag  who to add. customer_id is set once he is added.
--   kind customer      only adds him; there is no amount
ALTER TABLE drafts
    ALTER COLUMN customer_id DROP NOT NULL,
    ALTER COLUMN amount_paise DROP NOT NULL,
    ADD COLUMN new_name text CHECK (new_name IS NULL OR length(new_name) > 0),
    ADD COLUMN new_tag text CHECK (new_tag IS NULL OR length(new_tag) > 0),
    DROP CONSTRAINT drafts_kind_check,
    ADD CONSTRAINT drafts_kind_check CHECK (kind IN ('udhaar', 'payment', 'customer')),
    ADD CONSTRAINT drafts_amount_unless_customer CHECK (
        (amount_paise IS NULL) = (kind = 'customer')),
    ADD CONSTRAINT drafts_someone CHECK (customer_id IS NOT NULL OR new_name IS NOT NULL),
    ADD CONSTRAINT drafts_new_owes_nothing_back CHECK (
        new_name IS NULL OR kind IN ('udhaar', 'customer'));


-- V5: when the customer said an entry is wrong. The inbox shows it and the
-- Soundbox asks its question tone. A status says what; this says when.
ALTER TABLE entries
    ADD COLUMN disputed_at timestamptz,
    ADD CONSTRAINT entries_disputed_when CHECK (
        disputed_at IS NULL OR status IN ('disputed', 'corrected'));
