-- Migration: Add A-record verification field to domains table
-- 
-- PURPOSE:
--   Track whether domain's A-record points to our server IP.
--   If domain is clickable AND A-record points to our IP → +5% bonus.
--   If domain is clickable AND A-record does NOT point to our IP → -5% penalty.
--
-- SOLUTION:
--   Add a_record_points_to_us BOOLEAN column to domains table (default NULL).
--   NULL = not checked yet, TRUE = points to our IP, FALSE = does not point to our IP.

-- Step 1: Add a_record_points_to_us column to domains table (PostgreSQL)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_schema = 'public' 
          AND table_name = 'domains' 
          AND column_name = 'a_record_points_to_us'
    ) THEN
        ALTER TABLE domains 
        ADD COLUMN a_record_points_to_us BOOLEAN DEFAULT NULL;
        
        COMMENT ON COLUMN domains.a_record_points_to_us IS 'If TRUE, domain''s A-record points to our server IP (verified). NULL = not checked yet, FALSE = does not point to our IP.';
    END IF;
END $$;
