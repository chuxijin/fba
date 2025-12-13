-- 为收藏表添加冗余字段（bank_id, bank_name, chapter_id, chapter_name）
-- 日期：2025-12-10
-- 目的：提升收藏列表查询性能，避免 JOIN 多张表

-- 1. 添加冗余字段
ALTER TABLE study_question_favorite
ADD COLUMN bank_id BIGINT DEFAULT NULL COMMENT '题库 ID（冗余字段）',
ADD COLUMN bank_name VARCHAR(200) DEFAULT NULL COMMENT '题库名称（冗余字段，收藏时快照）',
ADD COLUMN chapter_id BIGINT DEFAULT NULL COMMENT '章节 ID（冗余字段）',
ADD COLUMN chapter_name VARCHAR(200) DEFAULT NULL COMMENT '章节名称（冗余字段，收藏时快照）';

-- 2. 回填已有数据的冗余字段（可选，如果数据库已有收藏记录）
-- 注意：这个查询会执行一次 JOIN 操作来填充历史数据
UPDATE study_question_favorite f
INNER JOIN study_question q ON f.question_id = q.id
LEFT JOIN study_question_bank b ON q.bank_id = b.id
LEFT JOIN study_question_chapter c ON q.chapter_id = c.id
SET
    f.bank_id = q.bank_id,
    f.bank_name = b.name,
    f.chapter_id = q.chapter_id,
    f.chapter_name = c.name
WHERE f.bank_id IS NULL;

-- 3. 创建索引（可选，提升查询性能）
CREATE INDEX idx_favorite_bank ON study_question_favorite(bank_id);
CREATE INDEX idx_favorite_chapter ON study_question_favorite(chapter_id);
