-- Add question placement table (MySQL)
-- Date: 2026-03-06

CREATE TABLE IF NOT EXISTS study_question_placement (
    id BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键 ID',
    bank_id BIGINT NOT NULL COMMENT '题库 ID',
    chapter_id BIGINT DEFAULT NULL COMMENT '章节 ID',
    question_id BIGINT NOT NULL COMMENT '题目 ID',
    sort_order INT NOT NULL DEFAULT 0 COMMENT '排序权重',
    is_active BOOLEAN NOT NULL DEFAULT TRUE COMMENT '是否启用',
    score DECIMAL(6, 2) DEFAULT NULL COMMENT '投放分值',
    review_status SMALLINT NOT NULL DEFAULT 10 COMMENT '审核状态',
    created_by BIGINT NOT NULL COMMENT '创建者',
    updated_by BIGINT DEFAULT NULL COMMENT '修改者',
    created_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_time DATETIME DEFAULT NULL ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (id),
    UNIQUE KEY uq_study_question_placement_bank_question (bank_id, question_id),
    KEY idx_study_question_placement_bank_chapter_sort (bank_id, chapter_id, sort_order),
    KEY idx_study_question_placement_question (question_id),
    CONSTRAINT fk_study_question_placement_bank FOREIGN KEY (bank_id) REFERENCES study_question_bank(id) ON DELETE CASCADE,
    CONSTRAINT fk_study_question_placement_chapter FOREIGN KEY (chapter_id) REFERENCES study_question_chapter(id) ON DELETE SET NULL,
    CONSTRAINT fk_study_question_placement_question FOREIGN KEY (question_id) REFERENCES study_question(id) ON DELETE CASCADE
) COMMENT='题目挂载表';

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
LEFT JOIN study_question_placement p
    ON p.bank_id = q.bank_id AND p.question_id = q.id
WHERE q.bank_id IS NOT NULL AND p.id IS NULL;

-- Recalculate chapter q_count from placement table.
UPDATE study_question_chapter c
LEFT JOIN (
    SELECT chapter_id, COUNT(*) AS q_count
    FROM study_question_placement
    WHERE chapter_id IS NOT NULL
    GROUP BY chapter_id
) t ON t.chapter_id = c.id
SET c.q_count = COALESCE(t.q_count, 0);

-- Recalculate bank q_count from placement table.
UPDATE study_question_bank b
LEFT JOIN (
    SELECT bank_id, COUNT(*) AS q_count
    FROM study_question_placement
    GROUP BY bank_id
) t ON t.bank_id = b.id
SET b.q_count = COALESCE(t.q_count, 0);
