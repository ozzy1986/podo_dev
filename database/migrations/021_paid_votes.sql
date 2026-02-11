-- Migration: Paid like/dislike. Add amount and free-vote flags to votes; karma = SUM(value * amount).

-- Add columns to votes
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'votes' AND column_name = 'amount') THEN
        ALTER TABLE votes ADD COLUMN amount INT NOT NULL DEFAULT 1;
        COMMENT ON COLUMN votes.amount IS 'Number of votes in this direction (1 = free, >1 includes paid).';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'votes' AND column_name = 'free_like_used') THEN
        ALTER TABLE votes ADD COLUMN free_like_used BOOLEAN NOT NULL DEFAULT false;
        COMMENT ON COLUMN votes.free_like_used IS 'User has used their one free like on this target.';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'votes' AND column_name = 'free_dislike_used') THEN
        ALTER TABLE votes ADD COLUMN free_dislike_used BOOLEAN NOT NULL DEFAULT false;
        COMMENT ON COLUMN votes.free_dislike_used IS 'User has used their one free dislike on this target.';
    END IF;
END $$;

-- Backfill: existing rows get amount=1 and free_*_used set by current value (idempotent)
UPDATE votes SET amount = 1, free_like_used = (value = 1), free_dislike_used = (value = -1);

-- Ensure defaults for any new rows (idempotent)
ALTER TABLE votes ALTER COLUMN amount SET DEFAULT 1;
ALTER TABLE votes ALTER COLUMN free_like_used SET DEFAULT false;
ALTER TABLE votes ALTER COLUMN free_dislike_used SET DEFAULT false;

-- Karma = SUM(value * amount). Replace comment karma trigger function.
CREATE OR REPLACE FUNCTION update_comment_karma()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        UPDATE comments SET karma_score = COALESCE((
            SELECT SUM(v.value * COALESCE(v.amount, 1)) FROM votes v
            WHERE v.target_type = 'comment' AND v.target_id = OLD.target_id
        ), 0), updated_at = CURRENT_TIMESTAMP
        WHERE id = OLD.target_id;
        RETURN OLD;
    END IF;
    UPDATE comments SET karma_score = COALESCE((
        SELECT SUM(v.value * COALESCE(v.amount, 1)) FROM votes v
        WHERE v.target_type = 'comment' AND v.target_id = NEW.target_id
    ), 0), updated_at = CURRENT_TIMESTAMP
    WHERE id = NEW.target_id;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
