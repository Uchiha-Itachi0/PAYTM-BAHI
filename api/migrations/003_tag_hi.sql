-- Each customer's tag in Devanagari too, as the name already is (002).
--
-- The shop describes customers by where they live or work: "Chai tapri",
-- "Medical shop". The shopkeeper says "चाय टपरी वाले", and Sarvam writes it in
-- Devanagari, which our own roman reading does not bring close enough to the
-- tag. Kept as Sarvam's transliterate writes it. NULL where there is no tag, or
-- voice was off when it was written.

ALTER TABLE customers ADD COLUMN tag_hi text CHECK (tag_hi IS NULL OR length(tag_hi) > 0);
