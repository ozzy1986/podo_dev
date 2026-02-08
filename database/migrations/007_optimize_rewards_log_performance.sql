-- Migration: Optimize rewards_log query performance for Total Earned calculation
--
-- PROBLEM:
--   Calculating "Total Earned" requires querying rewards_log with complex JOINs and OR conditions.
--   As the system grows, this becomes slow, especially with 1000+ concurrent users.
--
-- SOLUTION:
--   Add composite indexes to optimize the most common query patterns:
--   1. (wallet, created_at) - for NULL domain_id case (deleted domains)
--   2. (domain_id, created_at) - for active domains case
--   3. (wallet, status, created_at) - for filtering by status
--
--   These indexes will dramatically speed up ORDER BY created_at DESC with WHERE filters.

-- Index 1: Optimize queries for rewards with NULL domain_id (deleted domains)
-- This helps: WHERE r.domain_id IS NULL AND r.wallet = ? ORDER BY r.created_at DESC
CREATE INDEX IF NOT EXISTS idx_wallet_created_at ON rewards_log (wallet, created_at DESC);

-- Index 2: Optimize queries for rewards with domain_id (active domains)
-- This helps: JOIN domains WHERE d.user_id = ? ORDER BY r.created_at DESC
CREATE INDEX IF NOT EXISTS idx_domain_created_at ON rewards_log (domain_id, created_at DESC);

-- Index 3: Optimize queries filtering by status (for total_earned calculation)
-- This helps: WHERE status IN ('confirmed', 'accumulated') ORDER BY created_at DESC
CREATE INDEX IF NOT EXISTS idx_wallet_status_created_at ON rewards_log (wallet, status, created_at DESC);

-- Index 4: Optimize domain lookup by user_id (for JOIN performance)
-- This helps: JOIN domains d ON r.domain_id = d.id WHERE d.user_id = ?
CREATE INDEX IF NOT EXISTS idx_user_id_id ON domains (user_id, id);
