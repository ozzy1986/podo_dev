-- Migration: Add total_earnings and weight cached fields to domains table
--
-- PROBLEM:
--   Calculating "Rating" (total earnings) on-the-fly from rewards_log becomes slow as data grows.
--   With thousands of reward logs per domain, this creates performance bottlenecks in the rating page.
--   Weight is also calculated on-the-fly using formulas, which could be cached for consistency.
--
-- SOLUTION:
--   Add total_earnings and weight columns to domains table and maintain them incrementally.
--   Each time a reward is created, add it to total_earnings.
--   Weight is updated when age_r changes (via hourly processor or domain updates).
--   This makes displaying Rating page instant (single field lookup).

-- Step 1: Add total_earnings column to domains table
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'domains' AND column_name = 'total_earnings'
    ) THEN
        ALTER TABLE domains ADD COLUMN total_earnings DECIMAL(20, 8) DEFAULT 0;
        COMMENT ON COLUMN domains.total_earnings IS 'Cached total of all earned rewards (confirmed + accumulated) for this domain. Updated incrementally when rewards are created.';
    END IF;
END $$;

-- Step 2: Add weight column to domains table
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'domains' AND column_name = 'weight'
    ) THEN
        ALTER TABLE domains ADD COLUMN weight DECIMAL(18, 8) DEFAULT NULL;
        COMMENT ON COLUMN domains.weight IS 'Cached domain weight (W_len * (1 + B_FACTOR * (1 - age_r))). Updated when sld_length or age_r changes.';
    END IF;
END $$;

-- Step 3: Add index on total_earnings for faster sorting
CREATE INDEX IF NOT EXISTS idx_total_earnings ON domains(total_earnings);

-- Step 4: Add index on weight for faster sorting
CREATE INDEX IF NOT EXISTS idx_weight ON domains(weight);

-- Step 5: Backfill total_earnings for existing domains from rewards_log
-- This calculates total_earnings from historical data for all existing domains
UPDATE domains d
SET total_earnings = COALESCE((
    SELECT SUM(r.amount)
    FROM rewards_log r
    WHERE r.domain_id = d.id
      AND r.status IN ('confirmed', 'accumulated')
), 0)
WHERE d.is_mining = TRUE
  AND (d.total_earnings IS NULL OR d.total_earnings = 0);

-- Step 6: Backfill weight for existing domains
-- Weight = W_len[L] * (1 + B_FACTOR * (1 - age_r))
-- W_len(L) = max(1, W_BASE * PHI^(-(L-1)))
-- W_BASE = 610 * ALPHA = 3660
-- PHI = (1 + sqrt(5)) / 2 ≈ 1.6180339887
-- B_FACTOR = 0.30
UPDATE domains d
SET weight = GREATEST(1.0, 3660.0 * POWER(1.6180339887, -(GREATEST(1, COALESCE(d.sld_length, 63)) - 1)))
             * (1.0 + 0.30 * (1.0 - COALESCE(d.age_r, 1.0)))
WHERE d.is_mining = TRUE
  AND d.sld_length IS NOT NULL
  AND d.age_r IS NOT NULL
  AND (d.weight IS NULL OR d.weight = 0);
