-- Migration: Comments (threaded) and votes (likes/dislikes) for social layer.
-- Entities: domain, wallet, registrar, hoster, zone. Moderation: prem moderation support, default approved.

-- Ensure registrars and hosters tables exist (used by verification; may already exist)
CREATE TABLE IF NOT EXISTS registrars (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(255) NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS hosters (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(255) NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Add registrar_id / hoster_id to domains if missing (for existing schemas)
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'domains' AND column_name = 'registrar_id') THEN
        ALTER TABLE domains ADD COLUMN registrar_id INTEGER REFERENCES registrars(id) ON DELETE SET NULL;
        CREATE INDEX IF NOT EXISTS idx_domains_registrar_id ON domains(registrar_id);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'domains' AND column_name = 'hoster_id') THEN
        ALTER TABLE domains ADD COLUMN hoster_id INTEGER REFERENCES hosters(id) ON DELETE SET NULL;
        CREATE INDEX IF NOT EXISTS idx_domains_hoster_id ON domains(hoster_id);
    END IF;
END $$;

-- Comments: threaded; target is any entity (domain, wallet, registrar, hoster, zone)
CREATE TABLE IF NOT EXISTS comments (
    id SERIAL PRIMARY KEY,
    author_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    parent_id INTEGER REFERENCES comments(id) ON DELETE CASCADE,
    entity_type VARCHAR(32) NOT NULL,
    entity_id INTEGER,
    entity_key VARCHAR(255),
    body TEXT NOT NULL,
    moderation_status VARCHAR(32) NOT NULL DEFAULT 'approved',
    karma_score INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_entity_target CHECK (
        (entity_type = 'domain' AND entity_id IS NOT NULL AND entity_key IS NULL) OR
        (entity_type = 'wallet' AND entity_id IS NULL AND entity_key IS NOT NULL) OR
        (entity_type = 'registrar' AND entity_id IS NOT NULL AND entity_key IS NULL) OR
        (entity_type = 'hoster' AND entity_id IS NOT NULL AND entity_key IS NULL) OR
        (entity_type = 'zone' AND entity_id IS NULL AND entity_key IS NOT NULL)
    ),
    CONSTRAINT chk_moderation_status CHECK (moderation_status IN ('pending', 'approved', 'rejected'))
);

COMMENT ON TABLE comments IS 'Comments on entities (domain, wallet, registrar, hoster, zone). Threaded via parent_id.';
COMMENT ON COLUMN comments.entity_type IS 'domain | wallet | registrar | hoster | zone';
COMMENT ON COLUMN comments.entity_id IS 'domain_id, registrar_id, or hoster_id';
COMMENT ON COLUMN comments.entity_key IS 'wallet address or zone name (e.g. com)';
COMMENT ON COLUMN comments.moderation_status IS 'pending | approved | rejected. Default approved so comments pass until prem moderation is enabled.';
COMMENT ON COLUMN comments.karma_score IS 'Sum of vote values; updated on vote add/change/remove.';

CREATE INDEX IF NOT EXISTS idx_comments_entity ON comments(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_comments_entity_key ON comments(entity_type, entity_key);
CREATE INDEX IF NOT EXISTS idx_comments_parent ON comments(parent_id);
CREATE INDEX IF NOT EXISTS idx_comments_author ON comments(author_id);
CREATE INDEX IF NOT EXISTS idx_comments_created ON comments(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_comments_moderation ON comments(moderation_status) WHERE moderation_status = 'approved';

CREATE TRIGGER trg_comments_updated_at
    BEFORE UPDATE ON comments
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Votes: one row per user per target; value +1 or -1. Targets: comment, domain, registrar, hoster, zone, wallet.
CREATE TABLE IF NOT EXISTS votes (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    target_type VARCHAR(32) NOT NULL,
    target_id INTEGER,
    target_key VARCHAR(255),
    value SMALLINT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_vote_value CHECK (value IN (1, -1)),
    CONSTRAINT chk_vote_target CHECK (
        (target_type = 'comment' AND target_id IS NOT NULL AND target_key IS NULL) OR
        (target_type = 'domain' AND target_id IS NOT NULL AND target_key IS NULL) OR
        (target_type = 'registrar' AND target_id IS NOT NULL AND target_key IS NULL) OR
        (target_type = 'hoster' AND target_id IS NOT NULL AND target_key IS NULL) OR
        (target_type = 'zone' AND target_id IS NULL AND target_key IS NOT NULL) OR
        (target_type = 'wallet' AND target_id IS NULL AND target_key IS NOT NULL)
    )
);

COMMENT ON TABLE votes IS 'Like/dislike votes on comments and entities. One vote per user per target.';
COMMENT ON COLUMN votes.target_type IS 'comment | domain | registrar | hoster | zone | wallet';
COMMENT ON COLUMN votes.target_id IS 'comment_id, domain_id, registrar_id, or hoster_id';
COMMENT ON COLUMN votes.target_key IS 'zone name or wallet address';
COMMENT ON COLUMN votes.value IS '1 or -1';

CREATE UNIQUE INDEX IF NOT EXISTS idx_votes_user_target
    ON votes(user_id, target_type, COALESCE(target_id::text, ''), COALESCE(target_key, ''));
CREATE INDEX IF NOT EXISTS idx_votes_target ON votes(target_type, target_id);
CREATE INDEX IF NOT EXISTS idx_votes_target_key ON votes(target_type, target_key);

CREATE TRIGGER trg_votes_updated_at
    BEFORE UPDATE ON votes
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Function: update comment karma when votes on this comment change
CREATE OR REPLACE FUNCTION update_comment_karma()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        UPDATE comments SET karma_score = COALESCE((
            SELECT SUM(v.value) FROM votes v
            WHERE v.target_type = 'comment' AND v.target_id = OLD.target_id
        ), 0), updated_at = CURRENT_TIMESTAMP
        WHERE id = OLD.target_id;
        RETURN OLD;
    END IF;
    UPDATE comments SET karma_score = COALESCE((
        SELECT SUM(v.value) FROM votes v
        WHERE v.target_type = 'comment' AND v.target_id = NEW.target_id
    ), 0), updated_at = CURRENT_TIMESTAMP
    WHERE id = NEW.target_id;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_votes_comment_karma_ins ON votes;
DROP TRIGGER IF EXISTS trg_votes_comment_karma_upd ON votes;
DROP TRIGGER IF EXISTS trg_votes_comment_karma_del ON votes;
CREATE TRIGGER trg_votes_comment_karma_ins AFTER INSERT ON votes
    FOR EACH ROW WHEN (NEW.target_type = 'comment') EXECUTE FUNCTION update_comment_karma();
CREATE TRIGGER trg_votes_comment_karma_upd AFTER UPDATE ON votes
    FOR EACH ROW WHEN (NEW.target_type = 'comment') EXECUTE FUNCTION update_comment_karma();
CREATE TRIGGER trg_votes_comment_karma_del AFTER DELETE ON votes
    FOR EACH ROW WHEN (OLD.target_type = 'comment') EXECUTE FUNCTION update_comment_karma();
