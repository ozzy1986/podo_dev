-- Migration: Add total_earned cached field to users table
--
-- PROBLEM:
--   Calculating "Total Earned" on-the-fly from rewards_log becomes slow as data grows.
--   With thousands of reward logs per user, this creates performance bottlenecks.
--
-- SOLUTION:
--   Add total_earned column to users table and maintain it incrementally.
--   Each time a reward is created, add it to total_earned.
--   This makes displaying Total Earned instant (single field lookup).

-- Step 1: Add total_earned column to users table
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'users' AND column_name = 'total_earned'
    ) THEN
        ALTER TABLE users ADD COLUMN total_earned DECIMAL(20, 8) DEFAULT 0;
        COMMENT ON COLUMN users.total_earned IS 'Cached total of all earned rewards (confirmed + accumulated). Updated incrementally when rewards are created.';
    END IF;
END $$;

-- Step 2: Backfill total_earned for existing users from rewards_log
-- This calculates total_earned from historical data for all existing users
UPDATE users u
SET total_earned = COALESCE((
    SELECT SUM(r.amount)
    FROM rewards_log r
    LEFT JOIN domains d ON r.domain_id = d.id
    WHERE (d.user_id = u.id OR (r.domain_id IS NULL AND r.wallet = u.wallet))
      AND r.status IN ('confirmed', 'accumulated')
), 0)
WHERE EXISTS (
    SELECT 1 FROM rewards_log r
    LEFT JOIN domains d ON r.domain_id = d.id
    WHERE (d.user_id = u.id OR (r.domain_id IS NULL AND r.wallet = u.wallet))
      AND r.status IN ('confirmed', 'accumulated')
) OR u.total_earned IS NULL;
