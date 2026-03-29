BEGIN;

ALTER TABLE study_question_bank
    ADD COLUMN IF NOT EXISTS access_entitlement_code VARCHAR(64);

CREATE INDEX IF NOT EXISTS idx_study_question_bank_access_entitlement
    ON study_question_bank (access_entitlement_code);

COMMENT ON COLUMN study_question_bank.access_entitlement_code IS '访问所需权益编码，为空表示公开';

COMMIT;
