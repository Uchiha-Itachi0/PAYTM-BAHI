-- The customer can ask, too. Scanning the udhaar QR, she may say how much she
-- is taking and what for: "₹200, atta and oil". Nothing is written: the ask
-- waits on the scan until the shopkeeper answers.
--
--   asked_paise  what she asked for; whole rupees, at most ₹1,00,000
--   asked_note   what for, in her words (optional)
--   asked_at     when she asked
--   answer       yes      he wrote exactly that: her ask is her yes, so the
--                         entry is agreed by both at once
--                no       he said no; nothing written, the scan is over
--                changed  he wrote a different amount: an ordinary entry,
--                         which she confirms on her phone like any other
--   answered_at  when he answered
--
-- An ask keeps the scan open for ten minutes, not three: she is waiting on his
-- answer, not just standing at the counter.
ALTER TABLE scans
    ADD COLUMN asked_paise bigint
        CHECK (asked_paise IS NULL OR asked_paise BETWEEN 100 AND 1_00_000_00),
    ADD COLUMN asked_note text
        CHECK (asked_note IS NULL OR length(asked_note) BETWEEN 1 AND 80),
    ADD COLUMN asked_at timestamptz,
    ADD COLUMN answer text CHECK (answer IN ('yes', 'no', 'changed')),
    ADD COLUMN answered_at timestamptz,
    ADD CONSTRAINT scans_asked_together CHECK ((asked_paise IS NULL) = (asked_at IS NULL)),
    ADD CONSTRAINT scans_note_with_an_ask CHECK (asked_note IS NULL OR asked_paise IS NOT NULL),
    ADD CONSTRAINT scans_answer_to_an_ask CHECK (answer IS NULL OR asked_at IS NOT NULL),
    ADD CONSTRAINT scans_answered_together CHECK ((answer IS NULL) = (answered_at IS NULL)),
    -- Said no: nothing was written.
    ADD CONSTRAINT scans_no_writes_nothing CHECK (answer IS DISTINCT FROM 'no' OR entry_id IS NULL);
