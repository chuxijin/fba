-- question_bank 用户 ID 统一到 sys_user.id（MySQL）
-- Date: 2026-03-22

SET FOREIGN_KEY_CHECKS = 0;

-- 1) 删除所有 user_id -> study_user_account.* 的旧外键（逐表处理）
SET @fk_name := (
    SELECT kcu.CONSTRAINT_NAME
    FROM information_schema.KEY_COLUMN_USAGE kcu
    WHERE kcu.TABLE_SCHEMA = DATABASE()
      AND kcu.TABLE_NAME = 'study_practice_session'
      AND kcu.COLUMN_NAME = 'user_id'
      AND kcu.REFERENCED_TABLE_NAME = 'study_user_account'
    LIMIT 1
);
SET @sql := IF(@fk_name IS NULL, 'SELECT 1', CONCAT('ALTER TABLE `study_practice_session` DROP FOREIGN KEY `', @fk_name, '`'));
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @fk_name := (
    SELECT kcu.CONSTRAINT_NAME
    FROM information_schema.KEY_COLUMN_USAGE kcu
    WHERE kcu.TABLE_SCHEMA = DATABASE()
      AND kcu.TABLE_NAME = 'study_practice_record'
      AND kcu.COLUMN_NAME = 'user_id'
      AND kcu.REFERENCED_TABLE_NAME = 'study_user_account'
    LIMIT 1
);
SET @sql := IF(@fk_name IS NULL, 'SELECT 1', CONCAT('ALTER TABLE `study_practice_record` DROP FOREIGN KEY `', @fk_name, '`'));
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @fk_name := (
    SELECT kcu.CONSTRAINT_NAME
    FROM information_schema.KEY_COLUMN_USAGE kcu
    WHERE kcu.TABLE_SCHEMA = DATABASE()
      AND kcu.TABLE_NAME = 'study_wrong_question_book'
      AND kcu.COLUMN_NAME = 'user_id'
      AND kcu.REFERENCED_TABLE_NAME = 'study_user_account'
    LIMIT 1
);
SET @sql := IF(@fk_name IS NULL, 'SELECT 1', CONCAT('ALTER TABLE `study_wrong_question_book` DROP FOREIGN KEY `', @fk_name, '`'));
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @fk_name := (
    SELECT kcu.CONSTRAINT_NAME
    FROM information_schema.KEY_COLUMN_USAGE kcu
    WHERE kcu.TABLE_SCHEMA = DATABASE()
      AND kcu.TABLE_NAME = 'study_question_note'
      AND kcu.COLUMN_NAME = 'user_id'
      AND kcu.REFERENCED_TABLE_NAME = 'study_user_account'
    LIMIT 1
);
SET @sql := IF(@fk_name IS NULL, 'SELECT 1', CONCAT('ALTER TABLE `study_question_note` DROP FOREIGN KEY `', @fk_name, '`'));
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @fk_name := (
    SELECT kcu.CONSTRAINT_NAME
    FROM information_schema.KEY_COLUMN_USAGE kcu
    WHERE kcu.TABLE_SCHEMA = DATABASE()
      AND kcu.TABLE_NAME = 'study_user_note_vote'
      AND kcu.COLUMN_NAME = 'user_id'
      AND kcu.REFERENCED_TABLE_NAME = 'study_user_account'
    LIMIT 1
);
SET @sql := IF(@fk_name IS NULL, 'SELECT 1', CONCAT('ALTER TABLE `study_user_note_vote` DROP FOREIGN KEY `', @fk_name, '`'));
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @fk_name := (
    SELECT kcu.CONSTRAINT_NAME
    FROM information_schema.KEY_COLUMN_USAGE kcu
    WHERE kcu.TABLE_SCHEMA = DATABASE()
      AND kcu.TABLE_NAME = 'study_question_favorite'
      AND kcu.COLUMN_NAME = 'user_id'
      AND kcu.REFERENCED_TABLE_NAME = 'study_user_account'
    LIMIT 1
);
SET @sql := IF(@fk_name IS NULL, 'SELECT 1', CONCAT('ALTER TABLE `study_question_favorite` DROP FOREIGN KEY `', @fk_name, '`'));
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @fk_name := (
    SELECT kcu.CONSTRAINT_NAME
    FROM information_schema.KEY_COLUMN_USAGE kcu
    WHERE kcu.TABLE_SCHEMA = DATABASE()
      AND kcu.TABLE_NAME = 'study_user_check_in'
      AND kcu.COLUMN_NAME = 'user_id'
      AND kcu.REFERENCED_TABLE_NAME = 'study_user_account'
    LIMIT 1
);
SET @sql := IF(@fk_name IS NULL, 'SELECT 1', CONCAT('ALTER TABLE `study_user_check_in` DROP FOREIGN KEY `', @fk_name, '`'));
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 2) 数据迁移：将历史 user_id（study_user_account.id）映射为 sys_user.id（study_user_account.user_id）
UPDATE study_practice_session s
JOIN study_user_account a ON a.id = s.user_id
SET s.user_id = a.user_id;

UPDATE study_practice_record r
JOIN study_user_account a ON a.id = r.user_id
SET r.user_id = a.user_id;

UPDATE study_wrong_question_book w
JOIN study_user_account a ON a.id = w.user_id
SET w.user_id = a.user_id;

UPDATE study_question_note n
JOIN study_user_account a ON a.id = n.user_id
SET n.user_id = a.user_id;

UPDATE study_user_note_vote v
JOIN study_user_account a ON a.id = v.user_id
SET v.user_id = a.user_id;

UPDATE study_question_favorite f
JOIN study_user_account a ON a.id = f.user_id
SET f.user_id = a.user_id;

UPDATE study_user_check_in c
JOIN study_user_account a ON a.id = c.user_id
SET c.user_id = a.user_id;

UPDATE study_user_daily_rank d
JOIN study_user_account a ON a.id = d.user_id
SET d.user_id = a.user_id;

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

SET FOREIGN_KEY_CHECKS = 1;
