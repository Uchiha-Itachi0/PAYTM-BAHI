-- M3: what a customer says in chat that is worth remembering, and how each
-- customer pays, as Cognee keeps it.


-- Sarvam reads each customer message for a promise, and now also for anything
-- else worth the shopkeeper remembering: a complaint (prices, weights, an entry
-- he says is wrong), a hardship, a request. That is a `said` memory: one line,
-- in his language, from one message. A message can give a promise and a said.
ALTER TABLE memories
    DROP CONSTRAINT memories_kind_check,
    ADD CONSTRAINT memories_kind_check CHECK (
        kind IN ('note', 'promise', 'nickname', 'said')),
    ADD CONSTRAINT memories_said_from_his_chat CHECK (
        kind <> 'said' OR (said_by = 'customer' AND message_id IS NOT NULL));
DROP INDEX memories_one_per_message;
CREATE UNIQUE INDEX memories_one_kind_per_message ON memories (message_id, kind)
    WHERE message_id IS NOT NULL;


-- How he pays, as one sentence (service/pattern.py): the figures are the book's,
-- worked out by code. Cognee keeps it so a question by meaning ("who pays late?")
-- finds it. Rewritten when his book changes; the copy Cognee had before is taken
-- out once the new one is in.
--
--   body             the sentence
--   stored_at        Cognee has this body; cognee_id is its item
--   stale_cognee_id  Cognee's item for an earlier body, still to take out
CREATE TABLE profiles (
    customer_id      uuid PRIMARY KEY REFERENCES customers,
    shop_id          uuid NOT NULL REFERENCES shops,
    body             text NOT NULL CHECK (length(body) > 0),
    written_at       timestamptz NOT NULL,
    stored_at        timestamptz,
    cognee_id        uuid,
    stale_cognee_id  uuid,
    CHECK (stored_at IS NOT NULL OR cognee_id IS NULL)
);
CREATE INDEX profiles_to_store ON profiles (written_at) WHERE stored_at IS NULL;
