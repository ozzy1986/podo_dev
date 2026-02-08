-- Migration: Add promotion subscriptions feature
--
-- PROBLEM:
--   Need to support recurring promotion subscriptions where users can
--   automatically renew their domain promotions on a weekly/monthly basis.
--
-- SOLUTION:
--   Create promotion_subscriptions table to manage recurring promotions
--   with auto-renewal functionality.

-- Step 1: Create promotion_subscriptions table
CREATE TABLE IF NOT EXISTS promotion_subscriptions (
    id SERIAL PRIMARY KEY,
    domain_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    subscription_type VARCHAR(32) NOT NULL,
    price_per_period DECIMAL(18,8) NOT NULL,
    auto_renew BOOLEAN DEFAULT TRUE,
    next_renewal_at TIMESTAMP NOT NULL,
    status VARCHAR(32) DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    cancelled_at TIMESTAMP DEFAULT NULL,
    last_renewal_at TIMESTAMP DEFAULT NULL,

    FOREIGN KEY (domain_id) REFERENCES domains(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

COMMENT ON TABLE promotion_subscriptions IS 'Recurring promotion subscriptions for domains';
COMMENT ON COLUMN promotion_subscriptions.subscription_type IS 'Subscription type: weekly, monthly, quarterly';
COMMENT ON COLUMN promotion_subscriptions.price_per_period IS 'Price per renewal period in DOMAIN tokens';
COMMENT ON COLUMN promotion_subscriptions.auto_renew IS 'Whether subscription should auto-renew';
COMMENT ON COLUMN promotion_subscriptions.next_renewal_at IS 'When the next renewal is due';
COMMENT ON COLUMN promotion_subscriptions.status IS 'Status: active, cancelled, expired, suspended';
COMMENT ON COLUMN promotion_subscriptions.cancelled_at IS 'When subscription was cancelled';
COMMENT ON COLUMN promotion_subscriptions.last_renewal_at IS 'When last renewal occurred';

CREATE INDEX IF NOT EXISTS idx_promotion_subscriptions_domain_id ON promotion_subscriptions(domain_id);
CREATE INDEX IF NOT EXISTS idx_promotion_subscriptions_user_id ON promotion_subscriptions(user_id);
CREATE INDEX IF NOT EXISTS idx_promotion_subscriptions_next_renewal ON promotion_subscriptions(next_renewal_at);
CREATE INDEX IF NOT EXISTS idx_promotion_subscriptions_status ON promotion_subscriptions(status);
CREATE INDEX IF NOT EXISTS idx_promotion_subscriptions_subscription_type ON promotion_subscriptions(subscription_type);

-- Trigger for updated_at on promotion_subscriptions
-- (Assumes update_updated_at_column function already exists from schema.sql)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_trigger WHERE tgname = 'trg_promotion_subscriptions_updated_at'
    ) THEN
        CREATE TRIGGER trg_promotion_subscriptions_updated_at
            BEFORE UPDATE ON promotion_subscriptions
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at_column();
    END IF;
END $$;

-- Step 2: Add subscription_id reference to domain_promotions if not exists
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'domain_promotions' AND column_name = 'subscription_id'
    ) THEN
        ALTER TABLE domain_promotions ADD COLUMN subscription_id INTEGER DEFAULT NULL;
        COMMENT ON COLUMN domain_promotions.subscription_id IS 'Reference to subscription if this is a subscription-based promotion';
    END IF;
END $$;

-- Step 3: Add index on subscription_id in domain_promotions
CREATE INDEX IF NOT EXISTS idx_subscription_id ON domain_promotions(subscription_id);
