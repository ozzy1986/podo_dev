-- Migration for Widget Preferences v1.0
-- Adds widget_preferences column to store user's dashboard widget configuration

-- Add widget_preferences column to users table (JSON format)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'users' AND column_name = 'widget_preferences'
    ) THEN
        ALTER TABLE users ADD COLUMN widget_preferences TEXT DEFAULT NULL;
        COMMENT ON COLUMN users.widget_preferences IS 'JSON array of enabled widget IDs';
    END IF;
END $$;
