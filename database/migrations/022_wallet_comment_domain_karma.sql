-- Migration: Per-user (wallet) comment_karma and domain_karma, updated by triggers when karma changes.
-- comment_karma = sum of karma_score of user's approved comments (updated when votes on their comments change, or comments added/deleted/moderation changes).
-- domain_karma = sum of (value * amount) of votes on domains owned by the user (updated when votes on their domains change, or domain deleted).

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'users' AND column_name = 'comment_karma') THEN
        ALTER TABLE users ADD COLUMN comment_karma INTEGER NOT NULL DEFAULT 0;
        COMMENT ON COLUMN users.comment_karma IS 'Sum of karma_score of all approved comments by this user; updated by triggers.';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'users' AND column_name = 'domain_karma') THEN
        ALTER TABLE users ADD COLUMN domain_karma INTEGER NOT NULL DEFAULT 0;
        COMMENT ON COLUMN users.domain_karma IS 'Sum of (value*amount) of votes on domains owned by this user; updated by triggers.';
    END IF;
END $$;

-- Backfill comment_karma: sum of karma_score of approved comments per author
UPDATE users u
SET comment_karma = COALESCE((
    SELECT SUM(c.karma_score)::int FROM comments c
    WHERE c.author_id = u.id AND c.moderation_status = 'approved'
), 0);

-- Backfill domain_karma: sum of (value*amount) of votes on domains owned by user
UPDATE users u
SET domain_karma = COALESCE((
    SELECT SUM(v.value * COALESCE(v.amount, 1))::int FROM votes v
    JOIN domains d ON d.id = v.target_id AND v.target_type = 'domain'
    WHERE d.user_id = u.id
), 0);

-- Trigger: when a vote on a comment changes, update that comment's author's comment_karma by the vote delta
CREATE OR REPLACE FUNCTION update_user_comment_karma_on_vote()
RETURNS TRIGGER AS $$
DECLARE
    aid INT;
    delta INT;
BEGIN
    IF TG_OP = 'DELETE' THEN
        SELECT c.author_id INTO aid FROM comments c WHERE c.id = OLD.target_id;
        IF aid IS NOT NULL THEN
            delta := -(OLD.value * COALESCE(OLD.amount, 1));
            UPDATE users SET comment_karma = comment_karma + delta WHERE id = aid;
        END IF;
        RETURN OLD;
    ELSIF TG_OP = 'UPDATE' THEN
        delta := (NEW.value * COALESCE(NEW.amount, 1)) - (OLD.value * COALESCE(OLD.amount, 1));
        IF delta = 0 THEN RETURN NEW; END IF;
        SELECT c.author_id INTO aid FROM comments c WHERE c.id = NEW.target_id;
        IF aid IS NOT NULL THEN
            UPDATE users SET comment_karma = comment_karma + delta WHERE id = aid;
        END IF;
        RETURN NEW;
    ELSE
        SELECT c.author_id INTO aid FROM comments c WHERE c.id = NEW.target_id;
        IF aid IS NOT NULL THEN
            delta := NEW.value * COALESCE(NEW.amount, 1);
            UPDATE users SET comment_karma = comment_karma + delta WHERE id = aid;
        END IF;
        RETURN NEW;
    END IF;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_votes_user_comment_karma_ins ON votes;
DROP TRIGGER IF EXISTS trg_votes_user_comment_karma_upd ON votes;
DROP TRIGGER IF EXISTS trg_votes_user_comment_karma_del ON votes;
CREATE TRIGGER trg_votes_user_comment_karma_ins AFTER INSERT ON votes
    FOR EACH ROW WHEN (NEW.target_type = 'comment') EXECUTE FUNCTION update_user_comment_karma_on_vote();
CREATE TRIGGER trg_votes_user_comment_karma_upd AFTER UPDATE ON votes
    FOR EACH ROW WHEN (NEW.target_type = 'comment') EXECUTE FUNCTION update_user_comment_karma_on_vote();
CREATE TRIGGER trg_votes_user_comment_karma_del AFTER DELETE ON votes
    FOR EACH ROW WHEN (OLD.target_type = 'comment') EXECUTE FUNCTION update_user_comment_karma_on_vote();

-- Trigger: when a vote on a domain changes, update that domain owner's domain_karma by the vote delta
CREATE OR REPLACE FUNCTION update_user_domain_karma_on_vote()
RETURNS TRIGGER AS $$
DECLARE
    owner_id INT;
    delta INT;
BEGIN
    IF TG_OP = 'DELETE' THEN
        SELECT d.user_id INTO owner_id FROM domains d WHERE d.id = OLD.target_id;
        IF owner_id IS NOT NULL THEN
            delta := -(OLD.value * COALESCE(OLD.amount, 1));
            UPDATE users SET domain_karma = domain_karma + delta WHERE id = owner_id;
        END IF;
        RETURN OLD;
    ELSIF TG_OP = 'UPDATE' THEN
        delta := (NEW.value * COALESCE(NEW.amount, 1)) - (OLD.value * COALESCE(OLD.amount, 1));
        IF delta = 0 THEN RETURN NEW; END IF;
        SELECT d.user_id INTO owner_id FROM domains d WHERE d.id = NEW.target_id;
        IF owner_id IS NOT NULL THEN
            UPDATE users SET domain_karma = domain_karma + delta WHERE id = owner_id;
        END IF;
        RETURN NEW;
    ELSE
        SELECT d.user_id INTO owner_id FROM domains d WHERE d.id = NEW.target_id;
        IF owner_id IS NOT NULL THEN
            delta := NEW.value * COALESCE(NEW.amount, 1);
            UPDATE users SET domain_karma = domain_karma + delta WHERE id = owner_id;
        END IF;
        RETURN NEW;
    END IF;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_votes_user_domain_karma_ins ON votes;
DROP TRIGGER IF EXISTS trg_votes_user_domain_karma_upd ON votes;
DROP TRIGGER IF EXISTS trg_votes_user_domain_karma_del ON votes;
CREATE TRIGGER trg_votes_user_domain_karma_ins AFTER INSERT ON votes
    FOR EACH ROW WHEN (NEW.target_type = 'domain') EXECUTE FUNCTION update_user_domain_karma_on_vote();
CREATE TRIGGER trg_votes_user_domain_karma_upd AFTER UPDATE ON votes
    FOR EACH ROW WHEN (NEW.target_type = 'domain') EXECUTE FUNCTION update_user_domain_karma_on_vote();
CREATE TRIGGER trg_votes_user_domain_karma_del AFTER DELETE ON votes
    FOR EACH ROW WHEN (OLD.target_type = 'domain') EXECUTE FUNCTION update_user_domain_karma_on_vote();

-- Trigger: when a comment is deleted or moderation_status changes, update author's comment_karma
CREATE OR REPLACE FUNCTION update_user_comment_karma_on_comment()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        IF OLD.moderation_status = 'approved' THEN
            UPDATE users SET comment_karma = comment_karma - OLD.karma_score WHERE id = OLD.author_id;
        END IF;
        RETURN OLD;
    ELSIF TG_OP = 'UPDATE' THEN
        IF OLD.moderation_status = 'approved' AND NEW.moderation_status != 'approved' THEN
            UPDATE users SET comment_karma = comment_karma - OLD.karma_score WHERE id = OLD.author_id;
        ELSIF OLD.moderation_status != 'approved' AND NEW.moderation_status = 'approved' THEN
            UPDATE users SET comment_karma = comment_karma + NEW.karma_score WHERE id = NEW.author_id;
        END IF;
        RETURN NEW;
    ELSE
        RETURN NEW;
    END IF;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_comments_user_comment_karma_ins ON comments;
DROP TRIGGER IF EXISTS trg_comments_user_comment_karma_upd ON comments;
DROP TRIGGER IF EXISTS trg_comments_user_comment_karma_del ON comments;
CREATE TRIGGER trg_comments_user_comment_karma_del AFTER DELETE ON comments
    FOR EACH ROW EXECUTE FUNCTION update_user_comment_karma_on_comment();
CREATE TRIGGER trg_comments_user_comment_karma_upd AFTER UPDATE ON comments
    FOR EACH ROW EXECUTE FUNCTION update_user_comment_karma_on_comment();

-- Trigger: when a domain is deleted, subtract that domain's vote sum from owner's domain_karma
CREATE OR REPLACE FUNCTION update_user_domain_karma_on_domain_delete()
RETURNS TRIGGER AS $$
DECLARE
    vote_sum INT;
BEGIN
    SELECT COALESCE(SUM(v.value * COALESCE(v.amount, 1)), 0)::int INTO vote_sum
    FROM votes v WHERE v.target_type = 'domain' AND v.target_id = OLD.id;
    UPDATE users SET domain_karma = domain_karma - vote_sum WHERE id = OLD.user_id;
    RETURN OLD;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_domains_user_domain_karma_del ON domains;
CREATE TRIGGER trg_domains_user_domain_karma_del AFTER DELETE ON domains
    FOR EACH ROW EXECUTE FUNCTION update_user_domain_karma_on_domain_delete();
