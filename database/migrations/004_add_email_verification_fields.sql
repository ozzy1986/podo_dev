-- Migration: Add email verification fields to users table
-- PostgreSQL version - uses DO $$ blocks for idempotent column addition

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'users' AND column_name = 'email_verification_code'
    ) THEN
        ALTER TABLE users ADD COLUMN email_verification_code VARCHAR(10) DEFAULT NULL;
        COMMENT ON COLUMN users.email_verification_code IS 'Temporary email verification code';
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'users' AND column_name = 'email_verification_created_at'
    ) THEN
        ALTER TABLE users ADD COLUMN email_verification_created_at TIMESTAMP DEFAULT NULL;
        COMMENT ON COLUMN users.email_verification_created_at IS 'When email verification code was generated';
    END IF;
END $$;
