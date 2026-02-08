-- Migration: Allow NULL telegram_id for web users
-- This enables web users to register without Telegram ID
-- Run this BEFORE using the email verification system

-- Step 1: Remove the NOT NULL constraint on telegram_id and set default to NULL
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'users'
          AND column_name = 'telegram_id'
          AND is_nullable = 'NO'
    ) THEN
        ALTER TABLE users ALTER COLUMN telegram_id DROP NOT NULL;
        ALTER TABLE users ALTER COLUMN telegram_id SET DEFAULT NULL;
        COMMENT ON COLUMN users.telegram_id IS 'Telegram user ID (NULL for web users)';
    END IF;
END $$;

-- Step 2: Drop old unique index/constraint on telegram_id and recreate
-- PostgreSQL allows multiple NULLs in a UNIQUE constraint by default,
-- so a standard UNIQUE constraint works correctly for our use case.
DO $$
BEGIN
    -- Drop the original unique constraint from schema.sql if it exists
    IF EXISTS (
        SELECT 1 FROM pg_indexes
        WHERE schemaname = 'public'
          AND tablename = 'users'
          AND indexname = 'users_telegram_id_key'
    ) THEN
        ALTER TABLE users DROP CONSTRAINT IF EXISTS users_telegram_id_key;
    END IF;

    -- Drop any legacy index named 'telegram_id'
    DROP INDEX IF EXISTS telegram_id;
END $$;

-- Add unique constraint for telegram_id (PostgreSQL allows multiple NULLs by default)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'unique_telegram_id'
          AND conrelid = 'users'::regclass
    ) THEN
        ALTER TABLE users ADD CONSTRAINT unique_telegram_id UNIQUE (telegram_id);
    END IF;
END $$;

-- Add a unique constraint on email for web users
-- This ensures email uniqueness for web authentication
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'unique_email_web'
          AND conrelid = 'users'::regclass
    ) THEN
        ALTER TABLE users ADD CONSTRAINT unique_email_web UNIQUE (email);
    END IF;
END $$;

-- Update the table comment to reflect web user support
COMMENT ON TABLE users IS 'Users registered in the system (Telegram and Web)';
