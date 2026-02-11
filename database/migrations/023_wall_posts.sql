-- Migration: Wall posts with HTML body, karma, and voting support.

-- Create wall_posts table
CREATE TABLE IF NOT EXISTS wall_posts (
    id SERIAL PRIMARY KEY,
    author_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    entity_type VARCHAR(32) NOT NULL,
    entity_id INTEGER,
    entity_key VARCHAR(255),
    raw_body TEXT NOT NULL,
    body_html TEXT NOT NULL,
    content_theme VARCHAR(16) NOT NULL DEFAULT 'light',
    karma_score INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_wall_posts_entity CHECK (
        (entity_type = 'domain' AND entity_id IS NOT NULL AND entity_key IS NULL) OR
        (entity_type = 'wallet' AND entity_id IS NULL AND entity_key IS NOT NULL)
    ),
    CONSTRAINT chk_wall_posts_theme CHECK (content_theme IN ('light', 'dark'))
);

COMMENT ON TABLE wall_posts IS 'User wall posts attached to wallet or domain pages.';
COMMENT ON COLUMN wall_posts.entity_type IS 'domain | wallet';
COMMENT ON COLUMN wall_posts.entity_id IS 'domain_id when entity_type = domain';
COMMENT ON COLUMN wall_posts.entity_key IS 'wallet address when entity_type = wallet';
COMMENT ON COLUMN wall_posts.raw_body IS 'Original user input (trimmed) before sanitization.';
COMMENT ON COLUMN wall_posts.body_html IS 'Sanitized HTML body rendered in UI.';
COMMENT ON COLUMN wall_posts.content_theme IS 'Author selected theme: light | dark.';

CREATE INDEX IF NOT EXISTS idx_wall_posts_entity ON wall_posts(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_wall_posts_entity_key ON wall_posts(entity_type, entity_key);
CREATE INDEX IF NOT EXISTS idx_wall_posts_author ON wall_posts(author_id);
CREATE INDEX IF NOT EXISTS idx_wall_posts_created ON wall_posts(created_at DESC);

CREATE TRIGGER trg_wall_posts_updated_at
    BEFORE UPDATE ON wall_posts
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Allow comments to target wall posts
ALTER TABLE comments DROP CONSTRAINT IF EXISTS chk_entity_target;
ALTER TABLE comments ADD CONSTRAINT chk_entity_target CHECK (
    (entity_type = 'domain' AND entity_id IS NOT NULL AND entity_key IS NULL) OR
    (entity_type = 'wallet' AND entity_id IS NULL AND entity_key IS NOT NULL) OR
    (entity_type = 'registrar' AND entity_id IS NOT NULL AND entity_key IS NULL) OR
    (entity_type = 'hoster' AND entity_id IS NOT NULL AND entity_key IS NULL) OR
    (entity_type = 'zone' AND entity_id IS NULL AND entity_key IS NOT NULL) OR
    (entity_type = 'wall_post' AND entity_id IS NOT NULL AND entity_key IS NULL)
);

-- Allow votes to target wall posts
ALTER TABLE votes DROP CONSTRAINT IF EXISTS chk_vote_target;
ALTER TABLE votes ADD CONSTRAINT chk_vote_target CHECK (
    (target_type = 'comment' AND target_id IS NOT NULL AND target_key IS NULL) OR
    (target_type = 'domain' AND target_id IS NOT NULL AND target_key IS NULL) OR
    (target_type = 'registrar' AND target_id IS NOT NULL AND target_key IS NULL) OR
    (target_type = 'hoster' AND target_id IS NOT NULL AND target_key IS NULL) OR
    (target_type = 'zone' AND target_id IS NULL AND target_key IS NOT NULL) OR
    (target_type = 'wallet' AND target_id IS NULL AND target_key IS NOT NULL) OR
    (target_type = 'wall_post' AND target_id IS NOT NULL AND target_key IS NULL)
);

-- Keep wall post karma in sync with votes
CREATE OR REPLACE FUNCTION update_wall_post_karma()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        UPDATE wall_posts
        SET karma_score = COALESCE((
            SELECT SUM(v.value * COALESCE(v.amount, 1))
            FROM votes v
            WHERE v.target_type = 'wall_post' AND v.target_id = OLD.target_id
        ), 0),
            updated_at = CURRENT_TIMESTAMP
        WHERE id = OLD.target_id;
        RETURN OLD;
    END IF;

    UPDATE wall_posts
    SET karma_score = COALESCE((
        SELECT SUM(v.value * COALESCE(v.amount, 1))
        FROM votes v
        WHERE v.target_type = 'wall_post' AND v.target_id = NEW.target_id
    ), 0),
        updated_at = CURRENT_TIMESTAMP
    WHERE id = NEW.target_id;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_votes_wall_post_karma_ins ON votes;
DROP TRIGGER IF EXISTS trg_votes_wall_post_karma_upd ON votes;
DROP TRIGGER IF EXISTS trg_votes_wall_post_karma_del ON votes;
CREATE TRIGGER trg_votes_wall_post_karma_ins AFTER INSERT ON votes
    FOR EACH ROW WHEN (NEW.target_type = 'wall_post')
    EXECUTE FUNCTION update_wall_post_karma();
CREATE TRIGGER trg_votes_wall_post_karma_upd AFTER UPDATE ON votes
    FOR EACH ROW WHEN (NEW.target_type = 'wall_post')
    EXECUTE FUNCTION update_wall_post_karma();
CREATE TRIGGER trg_votes_wall_post_karma_del AFTER DELETE ON votes
    FOR EACH ROW WHEN (OLD.target_type = 'wall_post')
    EXECUTE FUNCTION update_wall_post_karma();

-- Update user comment karma when votes reference comments or wall posts
CREATE OR REPLACE FUNCTION update_user_comment_karma_on_vote()
RETURNS TRIGGER AS $$
DECLARE
    aid INT;
    delta INT;
    tgt_type TEXT;
    tgt_id INT;
BEGIN
    IF TG_OP = 'DELETE' THEN
        tgt_type := OLD.target_type;
        tgt_id := OLD.target_id;
        delta := -(OLD.value * COALESCE(OLD.amount, 1));
    ELSIF TG_OP = 'UPDATE' THEN
        tgt_type := NEW.target_type;
        tgt_id := NEW.target_id;
        delta := (NEW.value * COALESCE(NEW.amount, 1)) - (OLD.value * COALESCE(OLD.amount, 1));
        IF delta = 0 THEN
            RETURN NEW;
        END IF;
    ELSE
        tgt_type := NEW.target_type;
        tgt_id := NEW.target_id;
        delta := NEW.value * COALESCE(NEW.amount, 1);
    END IF;

    IF tgt_type = 'comment' THEN
        SELECT author_id INTO aid FROM comments WHERE id = tgt_id;
    ELSIF tgt_type = 'wall_post' THEN
        SELECT author_id INTO aid FROM wall_posts WHERE id = tgt_id;
    ELSE
        RETURN CASE WHEN TG_OP = 'DELETE' THEN OLD ELSE NEW END;
    END IF;

    IF aid IS NOT NULL THEN
        UPDATE users
        SET comment_karma = comment_karma + delta
        WHERE id = aid;
    END IF;

    RETURN CASE WHEN TG_OP = 'DELETE' THEN OLD ELSE NEW END;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_votes_user_comment_karma_ins ON votes;
DROP TRIGGER IF EXISTS trg_votes_user_comment_karma_upd ON votes;
DROP TRIGGER IF EXISTS trg_votes_user_comment_karma_del ON votes;
CREATE TRIGGER trg_votes_user_comment_karma_ins AFTER INSERT ON votes
    FOR EACH ROW WHEN (NEW.target_type IN ('comment', 'wall_post'))
    EXECUTE FUNCTION update_user_comment_karma_on_vote();
CREATE TRIGGER trg_votes_user_comment_karma_upd AFTER UPDATE ON votes
    FOR EACH ROW WHEN (NEW.target_type IN ('comment', 'wall_post') OR OLD.target_type IN ('comment', 'wall_post'))
    EXECUTE FUNCTION update_user_comment_karma_on_vote();
CREATE TRIGGER trg_votes_user_comment_karma_del AFTER DELETE ON votes
    FOR EACH ROW WHEN (OLD.target_type IN ('comment', 'wall_post'))
    EXECUTE FUNCTION update_user_comment_karma_on_vote();

-- Adjust comment karma when wall posts are removed (subtract accumulated karma)
CREATE OR REPLACE FUNCTION update_user_comment_karma_on_wall_post()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        UPDATE users
        SET comment_karma = comment_karma - OLD.karma_score
        WHERE id = OLD.author_id;
        RETURN OLD;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_wall_posts_user_comment_karma_del ON wall_posts;
CREATE TRIGGER trg_wall_posts_user_comment_karma_del AFTER DELETE ON wall_posts
    FOR EACH ROW EXECUTE FUNCTION update_user_comment_karma_on_wall_post();
