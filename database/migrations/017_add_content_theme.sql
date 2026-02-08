-- Migration: Add content_theme to domains for description/parking content display
--
-- PURPOSE:
--   Store the theme (light/dark) the author had when they last edited description
--   or parking content. The public domain page shows this content in that theme
--   regardless of the viewer's site theme.
--
-- content_theme: 'light' | 'dark', default 'light'. NULL treated as 'light' in app.

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'domains'
          AND column_name = 'content_theme'
    ) THEN
        ALTER TABLE domains
        ADD COLUMN content_theme VARCHAR(10) DEFAULT 'light';
        
        COMMENT ON COLUMN domains.content_theme IS 'Theme (light/dark) when author last edited description or parking content. Display block uses this so author intent is preserved.';
    END IF;
END $$;
