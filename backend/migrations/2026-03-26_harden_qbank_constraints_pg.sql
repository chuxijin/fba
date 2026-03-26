-- 题库上线前约束加固（PostgreSQL）
-- 目标：
-- 1. 允许 note 类型练习会话
-- 2. 笔记改为同一用户同一题仅一条
-- 3. 一级章节名称在同题库内唯一

BEGIN;

ALTER TABLE study_practice_session
    DROP CONSTRAINT IF EXISTS ck_practice_session_type;

ALTER TABLE study_practice_session
    ADD CONSTRAINT ck_practice_session_type
    CHECK (session_type IN ('chapter', 'bank', 'random', 'exam', 'wrong', 'favorite', 'note'));

WITH ranked_notes AS (
    SELECT
        id,
        ROW_NUMBER() OVER (
            PARTITION BY user_id, question_id
            ORDER BY updated_time DESC NULLS LAST, created_time DESC, id DESC
        ) AS row_num
    FROM study_question_note
),
duplicate_notes AS (
    SELECT id
    FROM ranked_notes
    WHERE row_num > 1
)
DELETE FROM study_question_note
WHERE id IN (SELECT id FROM duplicate_notes);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'uq_user_question_note'
    ) THEN
        ALTER TABLE study_question_note
            ADD CONSTRAINT uq_user_question_note UNIQUE (user_id, question_id);
    END IF;
END $$;

UPDATE study_question_statistics stats
SET note_count = source.note_count,
    last_updated = NOW()
FROM (
    SELECT question_id, COUNT(*) AS note_count
    FROM study_question_note
    GROUP BY question_id
) AS source
WHERE stats.question_id = source.question_id;

UPDATE study_question_statistics stats
SET note_count = 0,
    last_updated = NOW()
WHERE stats.note_count <> 0
  AND NOT EXISTS (
      SELECT 1
      FROM study_question_note note
      WHERE note.question_id = stats.question_id
  );

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM study_question_chapter
        WHERE parent_id IS NULL
        GROUP BY bank_id, name
        HAVING COUNT(*) > 1
    ) THEN
        RAISE EXCEPTION '存在重复的一级章节名称，请先清理后再执行本脚本';
    END IF;
END $$;

CREATE UNIQUE INDEX IF NOT EXISTS uq_study_question_chapter_root_name
    ON study_question_chapter (bank_id, name)
    WHERE parent_id IS NULL;

COMMIT;
