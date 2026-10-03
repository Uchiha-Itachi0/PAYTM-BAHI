-- The munshi can correct an entry: "जाधव का पाँच सौ नहीं, तीन सौ था". It puts the
-- correction on its card; his yes records the right amount as a new entry that
-- points at the wrong one, exactly as Correct the amount in the chat does, and
-- the customer confirms it on his own phone.
--
--   kind correction    amount_paise is the right amount
--   corrects_entry_id  the entry it corrects
--   entry_id           once saved, the new entry
ALTER TABLE drafts
    ADD COLUMN corrects_entry_id uuid REFERENCES entries,
    DROP CONSTRAINT drafts_kind_check,
    ADD CONSTRAINT drafts_kind_check CHECK (
        kind IN ('udhaar', 'payment', 'customer', 'correction')),
    ADD CONSTRAINT drafts_correction_names_its_entry CHECK (
        (kind = 'correction') = (corrects_entry_id IS NOT NULL)),
    DROP CONSTRAINT drafts_check1,
    ADD CONSTRAINT drafts_entry_once_saved CHECK (
        entry_id IS NULL OR (status = 'saved' AND kind IN ('udhaar', 'correction')));
