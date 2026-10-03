-- Someone kept by name only gets a phone: the shopkeeper adds his number later.
--
-- The invite waits on this same row, so his history stays his, and the book keeps
-- working by name meanwhile: the shopkeeper can still write his udhaar at the
-- counter. When he says yes, the row becomes his (person_id, linked_at) and his
-- open entries go to his phone for his own yes. Said no, the invite goes and he
-- stays in the book by name.
--
--   invite_person_id  the Paytm account invited. Never a phone number.
--   invited_at        when
ALTER TABLE customers
    ADD COLUMN invite_person_id uuid,
    ADD COLUMN invited_at timestamptz,
    ADD CONSTRAINT customers_invite_only_by_name CHECK (
        invite_person_id IS NULL OR person_id IS NULL),
    ADD CONSTRAINT customers_invited_when CHECK (
        (invite_person_id IS NULL) = (invited_at IS NULL));
-- One invite per account per shop, as one row per account per shop.
CREATE UNIQUE INDEX customers_one_invite_per_shop
    ON customers (shop_id, invite_person_id) WHERE invite_person_id IS NOT NULL;
