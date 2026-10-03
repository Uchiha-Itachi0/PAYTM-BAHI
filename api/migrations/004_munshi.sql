-- M1: the munshi. A conversation with the shopkeeper, every turn of it kept,
-- and the entry it proposes held as a draft until he says yes.
--
-- The munshi (Sarvam's model with tools) never writes to entries or repayments.
-- It proposes a draft; the shopkeeper's yes turns the draft into the entry
-- through the same ledger code a typed entry uses. So everything the rest of
-- the schema promises still holds, whatever the model says.

-- One sitting at the counter: from "Add udhaar" until the entry is saved or he
-- leaves. Later channels (typed chat, WhatsApp) open conversations too.
CREATE TABLE conversations (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    shop_id     uuid NOT NULL REFERENCES shops,
    started_at  timestamptz NOT NULL DEFAULT now()
);


-- Every message, in the order the model saw it: his words, the munshi's
-- replies, each tool call and each tool result. The whole conversation can be
-- replayed and audited from here, and it is what the model is shown next turn.
--
--   message   the message exactly as sent to or received from the model
--   heard     for his turns: what the mic heard, or null if he typed
--   ms        for the munshi's turns: how long the model took, in milliseconds
CREATE TABLE turns (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id  uuid NOT NULL REFERENCES conversations,
    seq              integer NOT NULL CHECK (seq >= 0),
    role             text NOT NULL CHECK (role IN ('system', 'user', 'assistant', 'tool')),
    message          jsonb NOT NULL,
    heard            text,
    ms               integer CHECK (ms >= 0),
    created_at       timestamptz NOT NULL DEFAULT now(),
    UNIQUE (conversation_id, seq)
);


-- What the munshi proposed, shown on the card and waiting for his yes.
--
--   kind        udhaar  goods on credit: becomes an entry
--               payment money back: split across his open entries, oldest first
--   status      shown     on the card, waiting
--               saved     he said yes; entry_id (udhaar) is set
--               replaced  a newer draft in the same conversation took its place
--               cancelled he said no
--   shown_seq   the turn the card appeared in. His yes counts only from a later
--               turn, so the munshi cannot show a card and approve it at once.
--   reasons     why this card needs an explicit yes, or empty for the quick
--               three-second one: weak_match, large, unusual.
CREATE TABLE drafts (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id  uuid NOT NULL REFERENCES conversations,
    customer_id      uuid NOT NULL REFERENCES customers,
    kind             text NOT NULL CHECK (kind IN ('udhaar', 'payment')),
    amount_paise     bigint NOT NULL CHECK (amount_paise > 0),
    spoken_text      text,
    reasons          text[] NOT NULL DEFAULT '{}',
    status           text NOT NULL DEFAULT 'shown' CHECK (
                         status IN ('shown', 'saved', 'replaced', 'cancelled')),
    shown_seq        integer NOT NULL,
    entry_id         uuid REFERENCES entries,
    created_at       timestamptz NOT NULL DEFAULT now(),
    decided_at       timestamptz,
    CHECK ((status IN ('saved', 'cancelled')) = (decided_at IS NOT NULL)),
    CHECK (entry_id IS NULL OR (status = 'saved' AND kind = 'udhaar'))
);
CREATE INDEX drafts_by_conversation ON drafts (conversation_id, created_at);
-- At most one card waits in a conversation at a time.
CREATE UNIQUE INDEX one_shown_draft ON drafts (conversation_id) WHERE status = 'shown';
