-- PostgreSQL 增量结构，与 e1f2a3b4c5d6 一致；在事务内执行，不改既有 Alembic 版本记录。
ALTER TABLE gongkao_practice_log
  ADD COLUMN IF NOT EXISTS subject_name VARCHAR(100) NOT NULL DEFAULT '行测',
  ADD COLUMN IF NOT EXISTS source_platform VARCHAR(20) NOT NULL DEFAULT 'manual',
  ADD COLUMN IF NOT EXISTS source_key VARCHAR(128),
  ADD COLUMN IF NOT EXISTS source_url VARCHAR(512),
  ADD COLUMN IF NOT EXISTS source_updated_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS time_source VARCHAR(24) NOT NULL DEFAULT 'manual',
  ADD COLUMN IF NOT EXISTS unanswered_count INTEGER,
  ADD COLUMN IF NOT EXISTS score NUMERIC(10,2),
  ADD COLUMN IF NOT EXISTS full_score NUMERIC(10,2);
ALTER TABLE gongkao_practice_module
  ADD COLUMN IF NOT EXISTS parent_id BIGINT,
  ADD COLUMN IF NOT EXISTS unanswered_count INTEGER;
DO $migration$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid = 'gongkao_practice_log'::regclass AND conname = 'uq_gk_practice_log_source') THEN
    ALTER TABLE gongkao_practice_log ADD CONSTRAINT uq_gk_practice_log_source UNIQUE(user_id, source_platform, source_key);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid = 'gongkao_practice_module'::regclass AND conname = 'fk_gk_practice_module_parent') THEN
    ALTER TABLE gongkao_practice_module ADD CONSTRAINT fk_gk_practice_module_parent FOREIGN KEY(parent_id) REFERENCES gongkao_practice_module(id) ON DELETE CASCADE;
  END IF;
END
$migration$;
CREATE INDEX IF NOT EXISTS idx_gk_practice_module_parent_id ON gongkao_practice_module(parent_id);
