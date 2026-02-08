-- Migration: Add domain promotions feature
--
-- PROBLEM:
--   Need to allow users to promote their domains to the top of the ratings page
--   by paying 1 DOMAIN token from their accumulated balance.
--
-- SOLUTION:
--   1. Create domain_promotions table to track all promotion transactions
--   2. Add promoted_at column to domains table for fast sorting
--   3. Promoted domains appear first in ratings, ordered by promotion datetime (latest first)

-- Step 1: Create domain_promotions table
CREATE TABLE IF NOT EXISTS domain_promotions (
    id SERIAL PRIMARY KEY,
    domain_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    amount DECIMAL(18,8) NOT NULL DEFAULT 1.0,
    amount_units BIGINT NOT NULL,
    promoted_at TIMESTAMP NOT NULL,
    expires_at TIMESTAMP DEFAULT NULL,
    subscription_id INTEGER DEFAULT NULL,
    status VARCHAR(32) DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (domain_id) REFERENCES domains(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

COMMENT ON TABLE domain_promotions IS 'History of domain promotion transactions';
COMMENT ON COLUMN domain_promotions.domain_id IS 'Foreign key to domains table';
COMMENT ON COLUMN domain_promotions.user_id IS 'Foreign key to users table';
COMMENT ON COLUMN domain_promotions.amount IS 'Amount paid for promotion in DOMAIN tokens';
COMMENT ON COLUMN domain_promotions.amount_units IS 'Amount in smallest units (with decimals)';
COMMENT ON COLUMN domain_promotions.promoted_at IS 'When the promotion was activated';
COMMENT ON COLUMN domain_promotions.expires_at IS 'When promotion expires (NULL for one-time promotions)';
COMMENT ON COLUMN domain_promotions.subscription_id IS 'Reference to subscription if this is a subscription-based promotion';
COMMENT ON COLUMN domain_promotions.status IS 'Status: active, expired, cancelled';

CREATE INDEX IF NOT EXISTS idx_domain_promotions_domain_id ON domain_promotions(domain_id);
CREATE INDEX IF NOT EXISTS idx_domain_promotions_user_id ON domain_promotions(user_id);
CREATE INDEX IF NOT EXISTS idx_domain_promotions_promoted_at ON domain_promotions(promoted_at);
CREATE INDEX IF NOT EXISTS idx_domain_promotions_status ON domain_promotions(status);
CREATE INDEX IF NOT EXISTS idx_domain_promotions_expires_at ON domain_promotions(expires_at);

-- Step 2: Add promoted_at column to domains table (if not exists)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'domains' AND column_name = 'promoted_at'
    ) THEN
        ALTER TABLE domains ADD COLUMN promoted_at TIMESTAMP DEFAULT NULL;
        COMMENT ON COLUMN domains.promoted_at IS 'When domain was last promoted (NULL if never promoted)';
    END IF;
END $$;

-- Step 3: Add index on promoted_at for fast sorting (if not exists)
CREATE INDEX IF NOT EXISTS idx_promoted_at ON domains(promoted_at);

-- Step 4: Add is_clickable column if it doesn't exist (for consistency)
-- This ensures promoted domains can be clickable
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'domains' AND column_name = 'is_clickable'
    ) THEN
        ALTER TABLE domains ADD COLUMN is_clickable BOOLEAN DEFAULT FALSE;
        COMMENT ON COLUMN domains.is_clickable IS 'Whether domain should be clickable in ratings';
    END IF;
END $$;
