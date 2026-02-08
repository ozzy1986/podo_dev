-- Migration: Add description field to domains table
-- 
-- PURPOSE:
--   Allow domain owners to add/edit descriptions for their domains.
--   Descriptions will be displayed on public domain pages.
--
-- SOLUTION:
--   Add description TEXT column to domains table (default NULL).
--   Max length: 500 characters (enforced in application layer).

-- Step 1: Add description column to domains table (PostgreSQL)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_schema = 'public' 
          AND table_name = 'domains' 
          AND column_name = 'description'
    ) THEN
        ALTER TABLE domains 
        ADD COLUMN description TEXT DEFAULT NULL;
        
        COMMENT ON COLUMN domains.description IS 'User-provided description for the domain. Max 500 characters. Displayed on public domain pages.';
    END IF;
END $$;
