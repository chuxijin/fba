-- Add year field to question bank table (PostgreSQL)
-- Date: 2026-04-14

ALTER TABLE study_question_bank
    ADD COLUMN IF NOT EXISTS year SMALLINT NULL;

COMMENT ON COLUMN study_question_bank.year IS '年份（试卷用）';

CREATE INDEX IF NOT EXISTS idx_study_question_bank_year
    ON study_question_bank(year);

