-- d.onl System Database Schema
-- PostgreSQL compatible

-- Drop tables if they exist (for clean reinstall)
DROP TABLE IF EXISTS rewards_log;
DROP TABLE IF EXISTS domains;
DROP TABLE IF EXISTS users;

-- ============================================================================
-- TRIGGER FUNCTION for updated_at columns
-- ============================================================================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- USERS TABLE
-- Stores Telegram user information and their Waves wallet addresses
-- ============================================================================
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    telegram_id BIGINT NOT NULL UNIQUE,
    username VARCHAR(255) DEFAULT NULL,
    wallet VARCHAR(64) DEFAULT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE users IS 'Telegram users registered in the system';
COMMENT ON COLUMN users.telegram_id IS 'Telegram user ID';
COMMENT ON COLUMN users.username IS 'Telegram username';
COMMENT ON COLUMN users.wallet IS 'Waves wallet address (3P...)';

CREATE INDEX idx_telegram_id ON users(telegram_id);
CREATE INDEX idx_users_wallet ON users(wallet);

CREATE TRIGGER trg_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- DOMAINS TABLE
-- Stores domain ownership information and mining status
-- ============================================================================
CREATE TABLE domains (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    domain VARCHAR(255) NOT NULL UNIQUE,
    nonce VARCHAR(64) NOT NULL,
    verified BOOLEAN DEFAULT FALSE,
    verification_time TIMESTAMP DEFAULT NULL,
    last_check TIMESTAMP DEFAULT NULL,
    last_reward TIMESTAMP DEFAULT NULL,
    failed_checks INTEGER DEFAULT 0,
    is_mining BOOLEAN DEFAULT FALSE,
    domain_expires_at DATE DEFAULT NULL,
    whois_last_check DATE DEFAULT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

COMMENT ON TABLE domains IS 'Domains registered for mining';
COMMENT ON COLUMN domains.user_id IS 'Foreign key to users table';
COMMENT ON COLUMN domains.domain IS 'Domain name (example.com)';
COMMENT ON COLUMN domains.nonce IS 'Unique nonce for TXT verification';
COMMENT ON COLUMN domains.verified IS 'Whether domain has been verified';
COMMENT ON COLUMN domains.verification_time IS 'When domain was first verified';
COMMENT ON COLUMN domains.last_check IS 'Last time oracle checked this domain';
COMMENT ON COLUMN domains.last_reward IS 'Last time reward was distributed';
COMMENT ON COLUMN domains.failed_checks IS 'Consecutive failed verification checks';
COMMENT ON COLUMN domains.is_mining IS 'Whether domain is currently mining';
COMMENT ON COLUMN domains.domain_expires_at IS 'Domain expiry date from WHOIS';
COMMENT ON COLUMN domains.whois_last_check IS 'Last time WHOIS was checked';

CREATE INDEX idx_user_id ON domains(user_id);
CREATE INDEX idx_domain ON domains(domain);
CREATE INDEX idx_is_mining ON domains(is_mining);
CREATE INDEX idx_verified ON domains(verified);
CREATE INDEX idx_last_check ON domains(last_check);
CREATE INDEX idx_user_domain ON domains(user_id, domain);

CREATE TRIGGER trg_domains_updated_at
    BEFORE UPDATE ON domains
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- REWARDS LOG TABLE
-- Stores history of all reward transactions
-- ============================================================================
CREATE TABLE rewards_log (
    id SERIAL PRIMARY KEY,
    domain_id INTEGER NOT NULL,
    amount DECIMAL(18,8) NOT NULL,
    amount_units BIGINT NOT NULL,
    wallet VARCHAR(64) NOT NULL,
    txid VARCHAR(128) DEFAULT NULL,
    status VARCHAR(32) DEFAULT 'pending',
    error_message TEXT DEFAULT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    confirmed_at TIMESTAMP DEFAULT NULL,

    FOREIGN KEY (domain_id) REFERENCES domains(id) ON DELETE CASCADE
);

COMMENT ON TABLE rewards_log IS 'History of all reward transactions';
COMMENT ON COLUMN rewards_log.domain_id IS 'Foreign key to domains table';
COMMENT ON COLUMN rewards_log.amount IS 'Reward amount in tokens (with decimals)';
COMMENT ON COLUMN rewards_log.amount_units IS 'Reward amount in smallest units';
COMMENT ON COLUMN rewards_log.wallet IS 'Recipient wallet address';
COMMENT ON COLUMN rewards_log.txid IS 'Waves transaction ID';
COMMENT ON COLUMN rewards_log.status IS 'Transaction status: pending, confirmed, failed';
COMMENT ON COLUMN rewards_log.error_message IS 'Error message if transaction failed';
COMMENT ON COLUMN rewards_log.created_at IS 'When reward was initiated';
COMMENT ON COLUMN rewards_log.confirmed_at IS 'When transaction was confirmed';

CREATE INDEX idx_domain_id ON rewards_log(domain_id);
CREATE INDEX idx_status ON rewards_log(status);
CREATE INDEX idx_txid ON rewards_log(txid);
CREATE INDEX idx_created_at ON rewards_log(created_at);
CREATE INDEX idx_rewards_wallet ON rewards_log(wallet);

-- ============================================================================
-- INITIAL DATA / STATS VIEW (Optional)
-- ============================================================================

-- Create a view for easy stats querying
CREATE OR REPLACE VIEW domain_stats AS
SELECT
    COUNT(DISTINCT d.id) as total_domains,
    COUNT(DISTINCT CASE WHEN d.is_mining = TRUE THEN d.id END) as active_domains,
    COUNT(DISTINCT CASE WHEN d.verified = TRUE THEN d.id END) as verified_domains,
    COUNT(DISTINCT d.user_id) as total_users,
    COALESCE(SUM(r.amount), 0) as total_rewards_distributed,
    COUNT(DISTINCT CASE WHEN r.status = 'confirmed' THEN r.id END) as successful_transactions,
    COUNT(DISTINCT CASE WHEN r.status = 'failed' THEN r.id END) as failed_transactions
FROM domains d
LEFT JOIN rewards_log r ON d.id = r.domain_id;

-- ============================================================================
-- USEFUL QUERIES FOR DEBUGGING
-- ============================================================================

-- Get all mining domains
-- SELECT d.*, u.wallet, u.telegram_id
-- FROM domains d
-- JOIN users u ON d.user_id = u.id
-- WHERE d.is_mining = TRUE;

-- Get recent rewards
-- SELECT r.*, d.domain, u.wallet
-- FROM rewards_log r
-- JOIN domains d ON r.domain_id = d.id
-- JOIN users u ON d.user_id = u.id
-- ORDER BY r.created_at DESC
-- LIMIT 10;

-- Get domains needing check
-- SELECT d.*, u.wallet
-- FROM domains d
-- JOIN users u ON d.user_id = u.id
-- WHERE d.is_mining = TRUE
-- AND (d.last_check IS NULL OR d.last_check < NOW() - INTERVAL '12 hours');
