-- V8b: the book on a hosted Postgres (Supabase), where more than our API can
-- knock: Supabase's Data API answers anyone holding the project's public key.
--
-- Row level security on every table, with no policies: anyone who isn't the
-- tables' owner gets no rows. The API connects as the owner, which row level
-- security doesn't bind (no FORCE), so nothing changes for it, on the laptop or
-- deployed. A table added later is added to this list in its own migration.
DO $$
DECLARE
    t text;
BEGIN
    FOR t IN SELECT tablename FROM pg_tables WHERE schemaname = 'public' LOOP
        EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', t);
    END LOOP;
END $$;

-- The two guards on the money rows run with a fixed search_path, so no one can
-- put a table of the same name in front of ours.
ALTER FUNCTION entries_facts_are_fixed() SET search_path = pg_catalog, public;
ALTER FUNCTION money_rows_are_kept() SET search_path = pg_catalog, public;
