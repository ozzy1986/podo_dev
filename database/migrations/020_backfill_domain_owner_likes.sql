-- One-time backfill: give each existing domain one like from its owner.
-- Domains created before the "auto-like on add" feature have no vote row, so karma shows 0.
-- This inserts a vote (value=1) for each domain where the owner has not already voted.

INSERT INTO votes (user_id, target_type, target_id, target_key, value)
SELECT d.user_id, 'domain', d.id, NULL, 1
FROM domains d
WHERE NOT EXISTS (
    SELECT 1 FROM votes v
    WHERE v.user_id = d.user_id AND v.target_type = 'domain' AND v.target_id = d.id
);
