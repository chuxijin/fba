-- Add year field to question bank table (MySQL)
-- Date: 2026-04-14

ALTER TABLE study_question_bank
    ADD COLUMN year SMALLINT NULL COMMENT '年份（试卷用）';

ALTER TABLE study_question_bank
    ADD INDEX idx_study_question_bank_year (year);

