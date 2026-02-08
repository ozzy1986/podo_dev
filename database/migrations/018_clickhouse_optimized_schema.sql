-- ClickHouse optimized schema for rewards_log
-- Run this on ClickHouse server: clickhouse-client < 018_clickhouse_optimized_schema.sql
--
-- Key optimizations:
--   1. PARTITION BY month for efficient time-range queries and easy data management
--   2. ORDER BY (wallet, created_at) matches primary query patterns (filter by wallet)
--   3. LowCardinality(String) for status (very few distinct values = huge compression)
--   4. TTL 730 days (2 years) for automatic data retention
--   5. ZSTD(3) codec for good compression/speed balance
--   6. Removed MAX(id) anti-pattern; id is now just a data column, not a sequence

-- Create database if not exists
CREATE DATABASE IF NOT EXISTS domain_mining;

-- Drop the old table and recreate (only for fresh installs; for existing data, use ALTER)
-- WARNING: If migrating existing data, skip CREATE TABLE and use ALTER TABLE instead.

CREATE TABLE IF NOT EXISTS domain_mining.rewards_log
(
    id           UInt64                          CODEC(Delta, ZSTD(3)),
    domain_id    Nullable(Int32)                 CODEC(ZSTD(3)),
    amount       Decimal(18, 8)                  CODEC(ZSTD(3)),
    amount_units Int64                           CODEC(Delta, ZSTD(3)),
    wallet       String                          CODEC(ZSTD(3)),
    txid         Nullable(String)                CODEC(ZSTD(3)),
    status       LowCardinality(String)          CODEC(ZSTD(3)),
    error_message Nullable(String)               CODEC(ZSTD(3)),
    created_at   DateTime                        CODEC(Delta, ZSTD(3)),
    confirmed_at Nullable(DateTime)              CODEC(Delta, ZSTD(3))
)
ENGINE = MergeTree()
PARTITION BY toYYYYMM(created_at)
ORDER BY (wallet, created_at)
TTL created_at + INTERVAL 730 DAY
SETTINGS
    index_granularity = 8192,
    min_bytes_for_wide_part = 10485760,
    merge_with_ttl_timeout = 86400;

-- Secondary index for domain_id lookups (used in per-domain earnings queries)
ALTER TABLE domain_mining.rewards_log
    ADD INDEX IF NOT EXISTS idx_domain_id domain_id TYPE minmax GRANULARITY 4;

-- Secondary index for status filtering
ALTER TABLE domain_mining.rewards_log
    ADD INDEX IF NOT EXISTS idx_status status TYPE set(10) GRANULARITY 4;

-- Materialized view: daily aggregated stats per wallet (pre-computed for dashboard)
CREATE TABLE IF NOT EXISTS domain_mining.rewards_daily_stats
(
    wallet       String,
    day          Date,
    total_amount Decimal(18, 8),
    tx_count     UInt64,
    domain_count UInt32
)
ENGINE = SummingMergeTree()
PARTITION BY toYYYYMM(day)
ORDER BY (wallet, day)
TTL day + INTERVAL 730 DAY;

CREATE MATERIALIZED VIEW IF NOT EXISTS domain_mining.rewards_daily_stats_mv
TO domain_mining.rewards_daily_stats
AS
SELECT
    wallet,
    toDate(created_at) AS day,
    sum(amount)        AS total_amount,
    count()            AS tx_count,
    uniq(domain_id)    AS domain_count
FROM domain_mining.rewards_log
WHERE status IN ('confirmed', 'accumulated')
GROUP BY wallet, day;

-- Materialized view: per-domain total earnings (pre-computed for ratings)
CREATE TABLE IF NOT EXISTS domain_mining.rewards_domain_totals
(
    domain_id    Int32,
    total_amount Decimal(18, 8),
    tx_count     UInt64
)
ENGINE = SummingMergeTree()
ORDER BY (domain_id);

CREATE MATERIALIZED VIEW IF NOT EXISTS domain_mining.rewards_domain_totals_mv
TO domain_mining.rewards_domain_totals
AS
SELECT
    domain_id,
    sum(amount)  AS total_amount,
    count()      AS tx_count
FROM domain_mining.rewards_log
WHERE domain_id IS NOT NULL AND status IN ('confirmed', 'accumulated')
GROUP BY domain_id;
