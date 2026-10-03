-- V9: an entry written by mistake can be taken back, the customer says why an
-- entry is wrong, the munshi can change how the shop describes someone and send
-- them a message, and each customer has a (simulated) Paytm account.


-- An entry written for the wrong person, or for nothing he took, is removed by
-- the shop. It is kept, marked removed, and claims nothing; both sides see it
-- was taken back. Like a correction, never for an entry anything was paid
-- against: the payment names it.
ALTER TABLE entries
    DROP CONSTRAINT entries_status_check,
    ADD CONSTRAINT entries_status_check CHECK (
        status IN ('recorded', 'confirmed', 'disputed', 'corrected', 'settled',
                   'removed')),
    ADD COLUMN removed_at timestamptz,
    ADD CONSTRAINT entries_removed_when CHECK (
        (removed_at IS NOT NULL) = (status = 'removed')),
    DROP CONSTRAINT entries_disputed_when,
    ADD CONSTRAINT entries_disputed_when CHECK (
        disputed_at IS NULL OR status IN ('disputed', 'corrected', 'removed')),
    -- What he said is wrong with it: not his at all, or the amount.
    ADD COLUMN disputed_as text CHECK (disputed_as IN ('not_mine', 'wrong_amount')),
    ADD CONSTRAINT entries_disputed_as_when CHECK (
        disputed_as IS NULL OR disputed_at IS NOT NULL);


-- The munshi's cards, beyond money:
--   removal   take back an entry written by mistake (names the entry)
--   details   the shop's name for someone, or how it describes them
--   message   words to send to the customer, in the shop's name
ALTER TABLE drafts
    DROP CONSTRAINT drafts_kind_check,
    ADD CONSTRAINT drafts_kind_check CHECK (
        kind IN ('udhaar', 'payment', 'customer', 'correction', 'removal',
                 'details', 'message')),
    DROP CONSTRAINT drafts_amount_unless_customer,
    ADD CONSTRAINT drafts_amount_unless_customer CHECK (
        (amount_paise IS NULL) = (kind IN ('customer', 'details', 'message'))),
    DROP CONSTRAINT drafts_correction_names_its_entry,
    ADD CONSTRAINT drafts_correction_names_its_entry CHECK (
        (kind IN ('correction', 'removal')) = (corrects_entry_id IS NOT NULL)),
    DROP CONSTRAINT drafts_new_owes_nothing_back,
    ADD CONSTRAINT drafts_new_owes_nothing_back CHECK (
        new_name IS NULL OR kind IN ('udhaar', 'customer', 'details')),
    ADD CONSTRAINT drafts_details_change_something CHECK (
        kind <> 'details'
        OR (customer_id IS NOT NULL AND (new_name IS NOT NULL OR new_tag IS NOT NULL))),
    ADD COLUMN message text CHECK (length(message) BETWEEN 1 AND 500),
    ADD CONSTRAINT drafts_message_is_a_message CHECK (
        (message IS NOT NULL) = (kind = 'message')
        AND (kind <> 'message' OR customer_id IS NOT NULL));


-- Paytm's own record of each person, simulated, in a schema of its own: BAHI's
-- tables (public) still hold no phone number (test_chat checks). In Paytm this
-- is the signed-in account: the name on it, its UPI ID and its mobile number,
-- none of which the person or the shop can change here. The shop sees the name
-- and the UPI ID, never the number; the person sees all three.
CREATE SCHEMA paytm;
CREATE TABLE paytm.accounts (
    person_id   uuid PRIMARY KEY,
    name        text NOT NULL CHECK (length(name) BETWEEN 1 AND 60),
    phone       text NOT NULL UNIQUE CHECK (phone ~ '^[6-9][0-9]{9}$'),
    upi         text NOT NULL UNIQUE CHECK (upi ~ '^[a-z0-9.]+@[a-z]+$'),
    created_at  timestamptz NOT NULL DEFAULT now()
);
-- As in 010: only the API, which owns the tables, reads them.
ALTER TABLE paytm.accounts ENABLE ROW LEVEL SECURITY;


-- Tomorrow's reminder, in the shopkeeper's own words when he rewrites it.
ALTER TABLE reminders
    DROP CONSTRAINT reminders_written_check,
    ADD CONSTRAINT reminders_written_check CHECK (
        written IN ('munshi', 'words', 'shop'));
