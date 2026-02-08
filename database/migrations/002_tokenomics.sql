-- Migration for Tokenomics v2.0 and User-Controlled Payouts

-- 1. Update USERS table (conditionally add columns)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'users' AND column_name = 'accumulated_balance'
    ) THEN
        ALTER TABLE users ADD COLUMN accumulated_balance DECIMAL(20, 8) DEFAULT 0;
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'users' AND column_name = 'accumulated_units'
    ) THEN
        ALTER TABLE users ADD COLUMN accumulated_units BIGINT DEFAULT 0;
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'users' AND column_name = 'payout_mode'
    ) THEN
        ALTER TABLE users ADD COLUMN payout_mode VARCHAR(10) DEFAULT 'manual';
        -- payout_mode values: 'manual', 'auto'
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'users' AND column_name = 'payout_threshold'
    ) THEN
        ALTER TABLE users ADD COLUMN payout_threshold DECIMAL(20, 2) DEFAULT NULL;
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'users' AND column_name = 'last_payout_at'
    ) THEN
        ALTER TABLE users ADD COLUMN last_payout_at TIMESTAMP DEFAULT NULL;
    END IF;
END $$;

-- 2. Update DOMAINS table (conditionally add columns)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'domains' AND column_name = 'sld_length'
    ) THEN
        ALTER TABLE domains ADD COLUMN sld_length SMALLINT DEFAULT NULL;
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'domains' AND column_name = 'creation_date'
    ) THEN
        ALTER TABLE domains ADD COLUMN creation_date TIMESTAMP DEFAULT NULL;
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'domains' AND column_name = 'age_r'
    ) THEN
        ALTER TABLE domains ADD COLUMN age_r DOUBLE PRECISION DEFAULT 1.0;
    END IF;
END $$;

-- Add index if it doesn't exist
CREATE INDEX IF NOT EXISTS idx_mining ON domains(is_mining);

-- 3. New POOL_STATE table (Aggregates)
CREATE TABLE IF NOT EXISTS pool_state (
    length_bucket SMALLINT PRIMARY KEY,  -- 1..63
    domain_count INTEGER DEFAULT 0,
    r_sum DOUBLE PRECISION DEFAULT 0.0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Initialize pool buckets (only if table is empty)
INSERT INTO pool_state (length_bucket)
SELECT n FROM generate_series(1, 63) AS n
ON CONFLICT DO NOTHING;

-- 4. New PAYOUT_REQUESTS table
CREATE TABLE IF NOT EXISTS payout_requests (
    id BIGSERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    wallet VARCHAR(50) NOT NULL,
    amount DECIMAL(20, 8) NOT NULL,
    amount_units BIGINT NOT NULL,
    status VARCHAR(20) DEFAULT 'pending',
    -- status values: 'pending', 'processing', 'completed', 'failed'
    triggered_by VARCHAR(20) NOT NULL,
    -- triggered_by values: 'manual', 'auto_threshold'
    tx_id VARCHAR(64) DEFAULT NULL,
    error_message TEXT DEFAULT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    processed_at TIMESTAMP DEFAULT NULL,

    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS idx_payout_requests_status ON payout_requests(status);
CREATE INDEX IF NOT EXISTS idx_payout_requests_user ON payout_requests(user_id);

-- 5. New SYSTEM_STATE table (Global vars)
CREATE TABLE IF NOT EXISTS system_state (
    key_name VARCHAR(50) PRIMARY KEY,
    value_int BIGINT DEFAULT NULL,
    value_float DOUBLE PRECISION DEFAULT NULL,
    value_str TEXT DEFAULT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO system_state (key_name, value_int) VALUES ('current_hour', 0) ON CONFLICT DO NOTHING;
INSERT INTO system_state (key_name, value_int) VALUES ('last_processed_hour', -1) ON CONFLICT DO NOTHING;
