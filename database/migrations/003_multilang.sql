-- Migration for Multilanguage Support v1.0

-- Add language column to users table
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'users' AND column_name = 'language'
    ) THEN
        ALTER TABLE users ADD COLUMN language VARCHAR(5) DEFAULT 'en';
        COMMENT ON COLUMN users.language IS 'User language preference (en, ru, ar)';
    END IF;
END $$;
