-- Migration: Add password field to users table for web authentication
-- Run this SQL to add password support for web users

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'users' AND column_name = 'password_hash'
    ) THEN
        ALTER TABLE users ADD COLUMN password_hash VARCHAR(255) DEFAULT NULL;
        COMMENT ON COLUMN users.password_hash IS 'Bcrypt hashed password for web users';
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'users' AND column_name = 'email'
    ) THEN
        ALTER TABLE users ADD COLUMN email VARCHAR(255) DEFAULT NULL;
        COMMENT ON COLUMN users.email IS 'Email for web users (optional)';
    END IF;
END $$;

-- Add index for email lookups
CREATE INDEX IF NOT EXISTS idx_email ON users(email);
