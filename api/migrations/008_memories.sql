-- M3: what BAHI remembers that the numbers can't show.
--
-- The book has the arithmetic. This keeps what people said: the shopkeeper's
-- note ("इक़बाल की सैलरी 10 को आती है, तब तक मत भेजना"), a customer's promise in
-- chat ("5 तारीख को दे दूँगा"), and a nickname the shopkeeper uses for someone.
-- A memory never writes an entry or changes an amount. With `until`, it can
-- only hold Tonight's reminder for him, never send one.
--
-- This table is the record: what the screen lists, what Tonight reads, what
-- Forget removes. Cognee keeps a copy to search by meaning (bahi.memory), in its
-- own database on this machine; `stored_at` and `cognee_id` say it has it.
--
--   kind      note      the shopkeeper told the munshi, or typed it
--             promise   the customer said, in chat, when he will pay
--             nickname  what the shopkeeper calls him, from a confirmed entry
--   said_by   shop or customer
--   until     the last day BAHI stays quiet for it: no reminder goes out on or
--             before this day. A promise always has one.
--   message_id  the chat message a promise was read from
CREATE TABLE memories (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    shop_id        uuid NOT NULL REFERENCES shops,
    customer_id    uuid NOT NULL REFERENCES customers,
    kind           text NOT NULL CHECK (kind IN ('note', 'promise', 'nickname')),
    body           text NOT NULL CHECK (length(body) BETWEEN 1 AND 300),
    said_by        text NOT NULL CHECK (said_by IN ('shop', 'customer')),
    until          date,
    message_id     uuid REFERENCES messages,
    remembered_at  timestamptz NOT NULL,
    forgotten_at   timestamptz,
    stored_at      timestamptz,
    cognee_id      uuid,
    CHECK (kind <> 'promise' OR (until IS NOT NULL AND said_by = 'customer')),
    CHECK (kind <> 'nickname' OR (said_by = 'shop' AND until IS NULL)),
    CHECK (stored_at IS NOT NULL OR cognee_id IS NULL)
);
CREATE INDEX memories_of_customer ON memories (customer_id) WHERE forgotten_at IS NULL;
CREATE INDEX memories_to_store ON memories (remembered_at)
    WHERE stored_at IS NULL AND forgotten_at IS NULL;
-- One promise per chat message.
CREATE UNIQUE INDEX memories_one_per_message ON memories (message_id)
    WHERE message_id IS NOT NULL;


-- A customer's words are read once for a promise. Everything already said is
-- marked read, so turning memory on doesn't reread the past.
ALTER TABLE messages ADD COLUMN read_for_memory_at timestamptz;
UPDATE messages SET read_for_memory_at = sent_at;
CREATE INDEX messages_to_read_for_memory ON messages (sent_at)
    WHERE read_for_memory_at IS NULL AND author = 'customer';


-- The name the shopkeeper used on a card, when it isn't the book's: "पप्पू" for
-- Raju. His yes to the card makes it a nickname memory; until then it is only
-- what he said.
ALTER TABLE drafts ADD COLUMN called text CHECK (length(called) BETWEEN 1 AND 40);
