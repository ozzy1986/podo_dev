-- Migration: Add flexible subscription frequencies
--
-- PROBLEM:
--   Need to support multiple subscription frequencies (5min to 1week)
--   Need to track failed renewals due to insufficient balance
--
-- SOLUTION:
--   Add last_failed_renewal column
--   Update subscription_type to support new frequency options
--   Cron will run every 5 minutes and check which subscriptions are due

-- Step 1: Add last_failed_renewal column if not exists
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'promotion_subscriptions' AND column_name = 'last_failed_renewal'
    ) THEN
        ALTER TABLE promotion_subscriptions ADD COLUMN last_failed_renewal TIMESTAMP DEFAULT NULL;
        COMMENT ON COLUMN promotion_subscriptions.last_failed_renewal IS 'When last renewal failed due to insufficient balance';
    END IF;
END $$;

-- Step 2: Add index on last_failed_renewal for dashboard queries
CREATE INDEX IF NOT EXISTS idx_last_failed_renewal ON promotion_subscriptions(last_failed_renewal);

-- Note: subscription_type column already exists and can store the new frequency values:
-- Supported frequencies:
--   '5min', '10min', '15min', '1hour', '2hours', '3hours', '5hours', '7hours', '10hours',
--   '24hours', '48hours', '72hours', '1week'
--
-- The existing VARCHAR(32) column is sufficient for these values.
-- No schema change needed, just application logic update.
