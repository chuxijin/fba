-- Add question placement table (PostgreSQL)
-- Date: 2026-03-06

CREATE TABLE IF NOT EXISTS study_question_placement (
    id BIGSERIAL PRIMARY KEY,
    bank_id BIGINT NOT NULL,
    chapter_id BIGINT NULL,
    question_id BIGINT NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 0,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    score NUMERIC(6, 2) NULL,
    review_status SMALLINT NOT NULL DEFAULT 10,
    created_by BIGINT NOT NULL,
    updated_by BIGINT NULL,
    created_time TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_time TIMESTAMPTZ NULL
);

ALTER TABLE study_question_placement
    ADD CONSTRAINT uq_study_question_placement_bank_question UNIQUE (bank_id, question_id);

ALTER TABLE study_question_placement
    ADD CONSTRAINT fk_study_question_placement_bank
    FOREIGN KEY (bank_id) REFERENCES study_question_bank(id) ON DELETE CASCADE;

ALTER TABLE study_question_placement
    ADD CONSTRAINT fk_study_question_placement_chapter
    FOREIGN KEY (chapter_id) REFERENCES study_question_chapter(id) ON DELETE SET NULL;

ALTER TABLE study_question_placement
    ADD CONSTRAINT fk_study_question_placement_question
    FOREIGN KEY (question_id) REFERENCES study_question(id) ON DELETE CASCADE;

CREATE INDEX idx_study_question_placement_bank_chapter_sort
    ON study_question_placement(bank_id, chapter_id, sort_order);

CREATE INDEX idx_study_question_placement_question
    ON study_question_placement(question_id);

-- Backfill from legacy fields in study_question.
INSERT INTO study_question_placement (
    bank_id,
    chapter_id,
    question_id,
    sort_order,
    is_active,
    score,
    review_status,
    created_by,
    updated_by,
    created_time,
    updated_time
)
SELECT
    q.bank_id,
    q.chapter_id,
    q.id,
    q.sort_order,
    q.is_active,
    q.score,
    q.review_status,
    q.created_by,
    q.updated_by,
    q.created_time,
    q.updated_time
FROM study_question q
WHERE q.bank_id IS NOT NULL
ON CONFLICT (bank_id, question_id) DO NOTHING;

-- Recalculate chapter q_count from placement table.
UPDATE study_question_chapter c
SET q_count = COALESCE(t.q_count, 0)
FROM (
    SELECT chapter_id, COUNT(*) AS q_count
    FROM study_question_placement
    WHERE chapter_id IS NOT NULL
    GROUP BY chapter_id
) t
WHERE t.chapter_id = c.id;

UPDATE study_question_chapter c
SET q_count = 0
WHERE NOT EXISTS (
    SELECT 1
    FROM study_question_placement p
    WHERE p.chapter_id = c.id
);

-- Recalculate bank q_count from placement table.
UPDATE study_question_bank b
SET q_count = COALESCE(t.q_count, 0)
FROM (
    SELECT bank_id, COUNT(*) AS q_count
    FROM study_question_placement
    GROUP BY bank_id
) t
WHERE t.bank_id = b.id;

UPDATE study_question_bank b
SET q_count = 0
WHERE NOT EXISTS (
    SELECT 1
    FROM study_question_placement p
    WHERE p.bank_id = b.id
);
