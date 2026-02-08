-- Migration: Add is_clickable field to domains table
--
-- PURPOSE:
--   Allow users to make their domains clickable in ratings tables.
--   Clickable domains become links in ratings, but earn 5% less rewards.
--
-- SOLUTION:
--   Add is_clickable BOOLEAN column to domains table (default FALSE).
--   When is_clickable = TRUE, domain rewards are reduced by 5% (multiplied by 0.95).

-- Step 1: Add is_clickable column to domains table
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'domains' AND column_name = 'is_clickable'
    ) THEN
        ALTER TABLE domains ADD COLUMN is_clickable BOOLEAN DEFAULT FALSE;
        COMMENT ON COLUMN domains.is_clickable IS 'If TRUE, domain is shown as clickable link in ratings but earns 5% less rewards.';
    END IF;
END $$;
