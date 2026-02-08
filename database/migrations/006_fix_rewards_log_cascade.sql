-- Migration: Fix rewards_log ON DELETE CASCADE issue
--
-- PROBLEM:
--   When a user deletes a domain, the foreign key constraint with ON DELETE CASCADE
--   automatically deletes ALL reward logs for that domain. This causes "Total Earned"
--   to decrease unexpectedly because historical reward data is permanently lost.
--
-- SOLUTION:
--   Change the foreign key constraint from ON DELETE CASCADE to ON DELETE SET NULL.
--   This preserves reward history even when domains are deleted. The domain_id will
--   be set to NULL, but all reward data (amount, status, timestamps) remains intact.
--
-- IMPORTANT:
--   Reward history should NEVER be deleted retroactively. Once a reward is earned,
--   that historical record must be preserved regardless of domain deletion.

-- Step 1: Drop the existing foreign key constraint
DO $$
DECLARE
    constraint_name_var TEXT;
BEGIN
    SELECT tc.constraint_name INTO constraint_name_var
    FROM information_schema.table_constraints tc
    JOIN information_schema.key_column_usage kcu
        ON tc.constraint_name = kcu.constraint_name
        AND tc.table_schema = kcu.table_schema
    JOIN information_schema.constraint_column_usage ccu
        ON ccu.constraint_name = tc.constraint_name
        AND ccu.table_schema = tc.table_schema
    WHERE tc.constraint_type = 'FOREIGN KEY'
      AND tc.table_schema = 'public'
      AND tc.table_name = 'rewards_log'
      AND kcu.column_name = 'domain_id'
      AND ccu.table_name = 'domains'
    LIMIT 1;

    IF constraint_name_var IS NOT NULL THEN
        EXECUTE 'ALTER TABLE rewards_log DROP CONSTRAINT ' || constraint_name_var;
    END IF;
END $$;

-- Step 2: Make domain_id nullable (required for SET NULL)
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'rewards_log'
          AND column_name = 'domain_id'
          AND is_nullable = 'NO'
    ) THEN
        ALTER TABLE rewards_log ALTER COLUMN domain_id DROP NOT NULL;
    END IF;

    COMMENT ON COLUMN rewards_log.domain_id IS 'Foreign key to domains table (NULL if domain was deleted)';
END $$;

-- Step 3: Add new foreign key with ON DELETE SET NULL
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
            ON tc.constraint_name = kcu.constraint_name
            AND tc.table_schema = kcu.table_schema
        JOIN information_schema.constraint_column_usage ccu
            ON ccu.constraint_name = tc.constraint_name
            AND ccu.table_schema = tc.table_schema
        WHERE tc.constraint_type = 'FOREIGN KEY'
          AND tc.table_schema = 'public'
          AND tc.table_name = 'rewards_log'
          AND kcu.column_name = 'domain_id'
          AND ccu.table_name = 'domains'
    ) THEN
        ALTER TABLE rewards_log
            ADD CONSTRAINT rewards_log_domain_id_fkey
            FOREIGN KEY (domain_id) REFERENCES domains(id) ON DELETE SET NULL;
    END IF;
END $$;
