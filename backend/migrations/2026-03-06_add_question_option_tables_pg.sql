-- Add normalized option tables (PostgreSQL)
-- Date: 2026-03-06

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS study_option_content (
    id BIGSERIAL PRIMARY KEY,
    content_hash VARCHAR(64) NOT NULL,
    content TEXT NOT NULL,
    created_time TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_time TIMESTAMPTZ NULL
);

ALTER TABLE study_option_content
    ADD CONSTRAINT uq_study_option_content_hash UNIQUE (content_hash);

CREATE INDEX idx_study_option_content_hash
    ON study_option_content(content_hash);

CREATE TABLE IF NOT EXISTS study_question_option (
    id BIGSERIAL PRIMARY KEY,
    question_id BIGINT NOT NULL,
    option_code VARCHAR(16) NOT NULL,
    content_id BIGINT NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 0,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_time TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_time TIMESTAMPTZ NULL
);

ALTER TABLE study_question_option
    ADD CONSTRAINT uq_study_question_option_question_code UNIQUE (question_id, option_code);

ALTER TABLE study_question_option
    ADD CONSTRAINT fk_study_question_option_question
    FOREIGN KEY (question_id) REFERENCES study_question(id) ON DELETE CASCADE;

ALTER TABLE study_question_option
    ADD CONSTRAINT fk_study_question_option_content
    FOREIGN KEY (content_id) REFERENCES study_option_content(id) ON DELETE RESTRICT;

CREATE INDEX idx_study_question_option_question_sort
    ON study_question_option(question_id, sort_order);

CREATE TABLE IF NOT EXISTS study_question_option_stats (
    id BIGSERIAL PRIMARY KEY,
    placement_id BIGINT NOT NULL,
    question_id BIGINT NOT NULL,
    option_id BIGINT NOT NULL,
    option_code VARCHAR(16) NOT NULL,
    selected_count INTEGER NOT NULL DEFAULT 0,
    correct_selected_count INTEGER NOT NULL DEFAULT 0,
    wrong_selected_count INTEGER NOT NULL DEFAULT 0,
    created_time TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_time TIMESTAMPTZ NULL
);

ALTER TABLE study_question_option_stats
    ADD CONSTRAINT uq_study_question_option_stats_placement_code UNIQUE (placement_id, option_code);

ALTER TABLE study_question_option_stats
    ADD CONSTRAINT fk_study_question_option_stats_placement
    FOREIGN KEY (placement_id) REFERENCES study_question_placement(id) ON DELETE CASCADE;

ALTER TABLE study_question_option_stats
    ADD CONSTRAINT fk_study_question_option_stats_question
    FOREIGN KEY (question_id) REFERENCES study_question(id) ON DELETE CASCADE;

ALTER TABLE study_question_option_stats
    ADD CONSTRAINT fk_study_question_option_stats_option
    FOREIGN KEY (option_id) REFERENCES study_question_option(id) ON DELETE CASCADE;

CREATE INDEX idx_study_question_option_stats_question
    ON study_question_option_stats(question_id);

CREATE INDEX idx_study_question_option_stats_option
    ON study_question_option_stats(option_id);

-- Backfill option content dictionary from legacy study_question.options_data JSON.
INSERT INTO study_option_content (content_hash, content, created_time)
SELECT DISTINCT
    encode(digest(trim(option_item.value ->> 'content'), 'sha256'), 'hex') AS content_hash,
    trim(option_item.value ->> 'content') AS content,
    now() AS created_time
FROM study_question q
CROSS JOIN LATERAL jsonb_each(q.options_data::jsonb) AS option_item(option_key, value)
WHERE q.options_data IS NOT NULL
  AND option_item.value ? 'content'
  AND trim(COALESCE(option_item.value ->> 'content', '')) <> ''
ON CONFLICT (content_hash) DO NOTHING;

-- Backfill question options from legacy study_question.options_data JSON.
INSERT INTO study_question_option (
    question_id,
    option_code,
    content_id,
    sort_order,
    is_active,
    created_time
)
SELECT
    q.id AS question_id,
    upper(trim(COALESCE(option_item.value ->> 'code', option_item.option_key))) AS option_code,
    c.id AS content_id,
    CASE
        WHEN upper(trim(COALESCE(option_item.value ->> 'code', option_item.option_key))) ~ '^[A-Z]$'
            THEN ascii(upper(trim(COALESCE(option_item.value ->> 'code', option_item.option_key)))) - 64
        ELSE 999
    END AS sort_order,
    TRUE AS is_active,
    now() AS created_time
FROM study_question q
CROSS JOIN LATERAL jsonb_each(q.options_data::jsonb) AS option_item(option_key, value)
JOIN study_option_content c
    ON c.content_hash = encode(digest(trim(option_item.value ->> 'content'), 'sha256'), 'hex')
WHERE q.options_data IS NOT NULL
  AND option_item.value ? 'content'
  AND trim(COALESCE(option_item.value ->> 'content', '')) <> ''
ON CONFLICT (question_id, option_code) DO UPDATE
SET
    content_id = EXCLUDED.content_id,
    sort_order = EXCLUDED.sort_order,
    is_active = EXCLUDED.is_active;
