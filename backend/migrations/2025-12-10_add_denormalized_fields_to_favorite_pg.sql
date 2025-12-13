-- 为收藏表添加冗余字段（bank_id, bank_name, chapter_id, chapter_name）
-- 数据库：PostgreSQL
-- 日期：2025-12-10
-- 目的：提升收藏列表查询性能，避免 JOIN 多张表

-- 1. 添加冗余字段
ALTER TABLE study_question_favorite
ADD COLUMN bank_id BIGINT DEFAULT NULL,
ADD COLUMN bank_name VARCHAR(200) DEFAULT NULL,
ADD COLUMN chapter_id BIGINT DEFAULT NULL,
ADD COLUMN chapter_name VARCHAR(200) DEFAULT NULL;

-- 2. 添加字段注释
COMMENT ON COLUMN study_question_favorite.bank_id IS '题库 ID（冗余字段）';
COMMENT ON COLUMN study_question_favorite.bank_name IS '题库名称（冗余字段，收藏时快照）';
COMMENT ON COLUMN study_question_favorite.chapter_id IS '章节 ID（冗余字段）';
COMMENT ON COLUMN study_question_favorite.chapter_name IS '章节名称（冗余字段，收藏时快照）';

-- 3. 回填已有数据的冗余字段（可选，如果数据库已有收藏记录）
-- 注意：这个查询会执行一次 JOIN 操作来填充历史数据
UPDATE study_question_favorite f
SET
    bank_id = q.bank_id,
    bank_name = b.name,
    chapter_id = q.chapter_id,
    chapter_name = c.name
FROM study_question q
LEFT JOIN study_question_bank b ON q.bank_id = b.id
LEFT JOIN study_question_chapter c ON q.chapter_id = c.id
WHERE f.question_id = q.id
AND f.bank_id IS NULL;

-- 4. 创建索引（可选，提升查询性能）
CREATE INDEX IF NOT EXISTS idx_favorite_bank ON study_question_favorite(bank_id);
CREATE INDEX IF NOT EXISTS idx_favorite_chapter ON study_question_favorite(chapter_id);
