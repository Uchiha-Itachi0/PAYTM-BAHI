-- V2b: every customer's name in Devanagari too.
--
-- Sarvam's transcript can come back in either script, and a name like Gaikwad
-- does not survive a round trip through our own roman reading of गायकवाड़. So the
-- name is kept as Sarvam's speech-to-text writes it, from Sarvam's transliterate:
-- once, when the customer joins. NULL when voice was offline at the time; the
-- roman name still matches.

ALTER TABLE customers ADD COLUMN name_hi text CHECK (name_hi IS NULL OR length(name_hi) > 0);
