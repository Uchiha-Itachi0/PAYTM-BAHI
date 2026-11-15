-- The family circle: people who can pay each other's udhaar at any shop.
--
-- A circle sits above shops, between people (Paytm accounts), never between a
-- person and a shop. The shopkeeper's book does not change shape: an entry still
-- belongs to the one customer who said "Yes, I owe", and a payment still names
-- the entry it pays. Nothing here lets one member owe another: there is no
-- balance between members, no pooled money, and no amount on any row below. The
-- money goes from the payer to the shop by UPI, against the debtor's own entry.
--
-- What is deliberately absent (docs/family-circle.md):
--   * an accept step for members. The creator adds people by phone number and
--     they are in. Consent at joining is the first thing to revisit.
--   * a default sharing choice in the database. Nobody's setting is stored until
--     they pick one; until then the code's DEFAULT_ON_UDHAAR decides, so the
--     default is one constant to flip.
--   * any column the shop reads. No shop query joins these tables.


-- A circle: a name its members see ("Sharma family"), and who made it.
CREATE TABLE circles (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name        text NOT NULL CHECK (length(name) BETWEEN 1 AND 40),
    created_by  uuid NOT NULL,
    created_at  timestamptz NOT NULL DEFAULT now()
);


-- Who is in it. A person who leaves keeps their row, with left_at; coming back
-- is a new row. One active membership per person per circle; a person can be in
-- several circles.
--
--   person_id  the Paytm account, as customers.person_id: no foreign key (Paytm
--              holds the users) and no phone number.
--   added_by   who put them in: the creator, or themselves.
CREATE TABLE circle_members (
    id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    circle_id  uuid NOT NULL REFERENCES circles,
    person_id  uuid NOT NULL,
    added_by   uuid NOT NULL,
    joined_at  timestamptz NOT NULL DEFAULT now(),
    left_at    timestamptz,
    CHECK (left_at IS NULL OR left_at >= joined_at)
);
CREATE UNIQUE INDEX circle_members_once
    ON circle_members (circle_id, person_id) WHERE left_at IS NULL;
CREATE INDEX circle_members_by_person ON circle_members (person_id) WHERE left_at IS NULL;


-- What a person wants done when they take udhaar, once they have chosen.
--   circle  it goes to their circle's list (to the one they pick, if several)
--   self    it stays with them; they can still add it to a circle themselves
-- No row means they have not chosen, and the code's default applies.
CREATE TABLE circle_settings (
    person_id  uuid PRIMARY KEY,
    on_udhaar  text NOT NULL CHECK (on_udhaar IN ('circle', 'self')),
    set_at     timestamptz NOT NULL DEFAULT now()
);


-- An entry in a circle's list: any member can pay it. The entry stays the
-- debtor's; this row only says who may pay it. No amount: what is left comes
-- from the entry and its payments, so it cannot drift.
--
--   withdrawn_at   taken off the list: by the debtor (taken_back), or because
--                  the debtor left the circle (left). From then on nobody else
--                  can pay it; it is theirs alone, as it always was.
CREATE TABLE circle_shares (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    circle_id      uuid NOT NULL REFERENCES circles,
    entry_id       uuid NOT NULL REFERENCES entries,
    shared_by      uuid NOT NULL,
    shared_at      timestamptz NOT NULL DEFAULT now(),
    withdrawn_at   timestamptz,
    withdrawn_why  text CHECK (withdrawn_why IN ('taken_back', 'left')),
    CHECK ((withdrawn_at IS NULL) = (withdrawn_why IS NULL))
);
-- An entry is in at most one circle's list at a time.
CREATE UNIQUE INDEX circle_shares_once ON circle_shares (entry_id) WHERE withdrawn_at IS NULL;
CREATE INDEX circle_shares_by_circle ON circle_shares (circle_id) WHERE withdrawn_at IS NULL;

-- Only an agreed entry can go to a circle: never one waiting for the debtor's
-- yes, one they say is wrong, or one taken back.
CREATE FUNCTION circle_shares_agreed_only() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog, public AS $$
BEGIN
    IF (SELECT status FROM entries WHERE id = NEW.entry_id) <> 'confirmed' THEN
        RAISE EXCEPTION 'only an entry its customer said yes to can go to a circle';
    END IF;
    RETURN NEW;
END $$;

CREATE TRIGGER circle_shares_agreed_only
    BEFORE INSERT ON circle_shares
    FOR EACH ROW EXECUTE FUNCTION circle_shares_agreed_only();


-- BAHI's notes to one person about their circles: the in-app notification. Not
-- a message in a shop thread, because the shop reads those and the shop never
-- sees the circle.
--
--   kind   added   someone put you in a circle
--          shared  your new udhaar went to your circle's list
--          choose  your new udhaar can go to one of your circles: pick one
--          kept    your new udhaar stayed with you (your setting)
--          help    a member's udhaar is on your circle's list
--          paid    a member paid part or all of your udhaar
--   done_at  read and acted on, or put aside.
CREATE TABLE circle_notices (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    person_id   uuid NOT NULL,
    kind        text NOT NULL CHECK (kind IN ('added', 'shared', 'choose', 'kept', 'help', 'paid')),
    circle_id   uuid REFERENCES circles,
    entry_id    uuid REFERENCES entries,
    body        text NOT NULL CHECK (length(body) > 0),
    created_at  timestamptz NOT NULL DEFAULT now(),
    done_at     timestamptz,
    CHECK (kind IN ('added', 'choose', 'kept') OR circle_id IS NOT NULL),
    CHECK (kind = 'added' OR entry_id IS NOT NULL)
);
CREATE INDEX circle_notices_open ON circle_notices (person_id, created_at) WHERE done_at IS NULL;


-- Who paid, when it was not the customer: a member of a circle the entry was on.
-- NULL means the customer paid it, or it was cash at the counter. The payment
-- still names the debtor's entry; there is no row anywhere where the debtor owes
-- the payer.
ALTER TABLE repayments
    ADD COLUMN paid_by uuid,
    ADD CONSTRAINT repayments_paid_by_upi CHECK (paid_by IS NULL OR method = 'upi');


-- As in 010: only the API, which owns the tables, reads them.
ALTER TABLE circles ENABLE ROW LEVEL SECURITY;
ALTER TABLE circle_members ENABLE ROW LEVEL SECURITY;
ALTER TABLE circle_settings ENABLE ROW LEVEL SECURITY;
ALTER TABLE circle_shares ENABLE ROW LEVEL SECURITY;
ALTER TABLE circle_notices ENABLE ROW LEVEL SECURITY;
