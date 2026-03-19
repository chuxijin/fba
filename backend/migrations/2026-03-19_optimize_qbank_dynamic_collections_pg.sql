-- 动态题目合集接口性能优化（PostgreSQL）
-- 适用接口：/api/v1/qbank/questions/collections

-- 1) 文本检索索引（ILIKE）
CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE INDEX IF NOT EXISTS idx_study_question_stem_trgm
    ON study_question USING GIN (stem gin_trgm_ops);

CREATE INDEX IF NOT EXISTS idx_study_option_content_content_trgm
    ON study_option_content USING GIN (content gin_trgm_ops);

CREATE INDEX IF NOT EXISTS idx_study_question_analysis_content_trgm_active
    ON study_question_analysis USING GIN (content gin_trgm_ops)
    WHERE status = 10;

CREATE INDEX IF NOT EXISTS idx_study_question_bank_name_trgm
    ON study_question_bank USING GIN (name gin_trgm_ops);

CREATE INDEX IF NOT EXISTS idx_study_question_bank_code_trgm
    ON study_question_bank USING GIN (code gin_trgm_ops);

CREATE INDEX IF NOT EXISTS idx_study_question_bank_desc_trgm
    ON study_question_bank USING GIN ("desc" gin_trgm_ops);

-- 2) 知识点 JSONB 索引（@>）
CREATE INDEX IF NOT EXISTS idx_study_question_knowledge_point_gin
    ON study_question USING GIN ((knowledge_point::jsonb));

-- 3) 挂载聚合辅助索引
CREATE INDEX IF NOT EXISTS idx_study_question_placement_active_qid_bid
    ON study_question_placement (question_id, bank_id)
    WHERE is_active IS TRUE;
