ALTER TABLE study_practice_session
    ADD COLUMN IF NOT EXISTS source_key VARCHAR(64),
    ADD COLUMN IF NOT EXISTS source_snapshot JSONB;

CREATE INDEX IF NOT EXISTS idx_session_user_status_source_key
    ON study_practice_session (user_id, status, source_key);
