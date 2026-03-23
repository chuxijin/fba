-- question_bank 用户 ID 统一到 sys_user.id（PostgreSQL）
-- Date: 2026-03-22

BEGIN;

-- 1) 删除所有 user_id -> study_user_account.* 的旧外键（逐表动态删除）
DO $$
DECLARE
    table_name text;
    fk_name text;
BEGIN
    FOREACH table_name IN ARRAY ARRAY[
        'study_practice_session',
        'study_practice_record',
        'study_wrong_question_book',
        'study_question_note',
        'study_user_note_vote',
        'study_question_favorite',
        'study_user_check_in'
    ]
    LOOP
        FOR fk_name IN
            SELECT con.conname
            FROM pg_constraint con
            JOIN pg_class tbl ON tbl.oid = con.conrelid
            JOIN pg_namespace ns ON ns.oid = tbl.relnamespace
            JOIN pg_class ref_tbl ON ref_tbl.oid = con.confrelid
            JOIN unnest(con.conkey) AS col(attnum) ON TRUE
            JOIN pg_attribute att ON att.attrelid = tbl.oid AND att.attnum = col.attnum
            WHERE con.contype = 'f'
              AND ns.nspname = current_schema()
              AND tbl.relname = table_name
              AND ref_tbl.relname = 'study_user_account'
              AND att.attname = 'user_id'
        LOOP
            EXECUTE format('ALTER TABLE %I DROP CONSTRAINT %I', table_name, fk_name);
        END LOOP;
    END LOOP;
END $$;

-- 2) 数据迁移：将历史 user_id（study_user_account.id）映射为 sys_user.id（study_user_account.user_id）
UPDATE study_practice_session s
SET user_id = a.user_id
FROM study_user_account a
WHERE s.user_id = a.id;

UPDATE study_practice_record r
SET user_id = a.user_id
FROM study_user_account a
WHERE r.user_id = a.id;

UPDATE study_wrong_question_book w
SET user_id = a.user_id
FROM study_user_account a
WHERE w.user_id = a.id;

UPDATE study_question_note n
SET user_id = a.user_id
FROM study_user_account a
WHERE n.user_id = a.id;

UPDATE study_user_note_vote v
SET user_id = a.user_id
FROM study_user_account a
WHERE v.user_id = a.id;

UPDATE study_question_favorite f
SET user_id = a.user_id
FROM study_user_account a
WHERE f.user_id = a.id;

UPDATE study_user_check_in c
SET user_id = a.user_id
FROM study_user_account a
WHERE c.user_id = a.id;

UPDATE study_user_daily_rank d
SET user_id = a.user_id
FROM study_user_account a
WHERE d.user_id = a.id;

-- 3) 新增外键：统一引用 study_user_account.user_id（= sys_user.id）
ALTER TABLE study_practice_session
    ADD CONSTRAINT fk_sps_user_id_user_account_uid
    FOREIGN KEY (user_id) REFERENCES study_user_account(user_id) ON DELETE CASCADE;

ALTER TABLE study_practice_record
    ADD CONSTRAINT fk_spr_user_id_user_account_uid
    FOREIGN KEY (user_id) REFERENCES study_user_account(user_id) ON DELETE CASCADE;

ALTER TABLE study_wrong_question_book
    ADD CONSTRAINT fk_swb_user_id_user_account_uid
    FOREIGN KEY (user_id) REFERENCES study_user_account(user_id) ON DELETE CASCADE;

ALTER TABLE study_question_note
    ADD CONSTRAINT fk_sqn_user_id_user_account_uid
    FOREIGN KEY (user_id) REFERENCES study_user_account(user_id) ON DELETE CASCADE;

ALTER TABLE study_user_note_vote
    ADD CONSTRAINT fk_sunv_user_id_user_account_uid
    FOREIGN KEY (user_id) REFERENCES study_user_account(user_id) ON DELETE CASCADE;

ALTER TABLE study_question_favorite
    ADD CONSTRAINT fk_sqf_user_id_user_account_uid
    FOREIGN KEY (user_id) REFERENCES study_user_account(user_id) ON DELETE CASCADE;

ALTER TABLE study_user_check_in
    ADD CONSTRAINT fk_suci_user_id_user_account_uid
    FOREIGN KEY (user_id) REFERENCES study_user_account(user_id) ON DELETE CASCADE;

COMMIT;
