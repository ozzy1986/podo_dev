-- Migration: Add parking_mode and parking_content fields for super parking
--
-- PURPOSE:
--   Support "super parking" (non-redirect) - site opens under user's domain
--   with custom content. Cost: 50% mining power.
--
-- parking_mode: 'redirect' = default (A-record redirects to d.onl)
--               'non_redirect' = super parking (page served on user's domain)
-- parking_content: HTML content for super parking landing page (max 5000 chars in app)
--
-- Extensible for future parking modes.

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'domains'
          AND column_name = 'parking_mode'
    ) THEN
        ALTER TABLE domains
        ADD COLUMN parking_mode VARCHAR(20) DEFAULT 'redirect';
        
        COMMENT ON COLUMN domains.parking_mode IS 'Parking mode: redirect (default, A-record redirects to d.onl), non_redirect (super parking, page on user domain). Extensible for future modes.';
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'domains'
          AND column_name = 'parking_content'
    ) THEN
        ALTER TABLE domains
        ADD COLUMN parking_content TEXT DEFAULT NULL;
        
        COMMENT ON COLUMN domains.parking_content IS 'HTML content for super parking landing page. Used when parking_mode=non_redirect. Max 5000 chars in app layer.';
    END IF;
END $$;
