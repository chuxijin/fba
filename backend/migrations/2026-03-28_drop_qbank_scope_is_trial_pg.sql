BEGIN;

ALTER TABLE study_question_bank
    DROP COLUMN IF EXISTS scope;

ALTER TABLE study_question_chapter
    DROP COLUMN IF EXISTS is_trial;

COMMIT;
