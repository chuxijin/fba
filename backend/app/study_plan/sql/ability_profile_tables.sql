-- 学习规划能力画像建表脚本
-- schema = fba
-- 前置依赖：fba.study_user_account / fba.study_plan_item / fba.study_plan_record / fba.sys_category 已存在

BEGIN;

-- ===== study_ability_catalog =====
CREATE TABLE fba.study_ability_catalog (
  id BIGSERIAL NOT NULL,
  ability_key VARCHAR(64) NOT NULL,
  title VARCHAR(128) NOT NULL,
  category VARCHAR(64) NOT NULL,
  url VARCHAR(512) NOT NULL,
  domain VARCHAR(32) NOT NULL,
  description VARCHAR(512),
  default_minutes INTEGER NOT NULL,
  default_question_count INTEGER,
  default_accuracy NUMERIC(5, 4),
  benchmark_seconds NUMERIC(8, 2),
  supports_study_plan BOOLEAN NOT NULL,
  supports_result BOOLEAN NOT NULL,
  is_active BOOLEAN NOT NULL,
  extra JSONB,
  created_by INTEGER NOT NULL,
  updated_by INTEGER,
  created_time TIMESTAMP WITH TIME ZONE NOT NULL,
  updated_time TIMESTAMP WITH TIME ZONE,
  deleted BIGINT DEFAULT '0' NOT NULL,
  deleted_time TIMESTAMP WITH TIME ZONE,
  PRIMARY KEY (id),
  CONSTRAINT uq_study_ability_catalog_domain_key UNIQUE (domain, ability_key),
  CONSTRAINT ck_study_ability_catalog_minutes CHECK (
    default_minutes >= 0
  ),
  CONSTRAINT ck_study_ability_catalog_question_count CHECK (
    default_question_count IS NULL OR default_question_count > 0
  ),
  CONSTRAINT ck_study_ability_catalog_accuracy CHECK (
    default_accuracy IS NULL OR (default_accuracy >= 0 AND default_accuracy <= 1)
  ),
  CONSTRAINT ck_study_ability_catalog_benchmark CHECK (
    benchmark_seconds IS NULL OR benchmark_seconds > 0
  )
);
CREATE UNIQUE INDEX ix_study_ability_catalog_id ON fba.study_ability_catalog (id);
CREATE INDEX idx_study_ability_catalog_domain_active ON fba.study_ability_catalog (domain, is_active);

-- ===== study_ability_category_binding =====
CREATE TABLE fba.study_ability_category_binding (
  id BIGSERIAL NOT NULL,
  ability_key VARCHAR(64) NOT NULL,
  category_id BIGINT NOT NULL,
  mode VARCHAR(64),
  role VARCHAR(32) NOT NULL,
  weight NUMERIC(6, 4) NOT NULL,
  is_primary BOOLEAN NOT NULL,
  source VARCHAR(32) NOT NULL,
  confidence NUMERIC(6, 4) NOT NULL,
  created_by INTEGER NOT NULL,
  updated_by INTEGER,
  created_time TIMESTAMP WITH TIME ZONE NOT NULL,
  updated_time TIMESTAMP WITH TIME ZONE,
  deleted BIGINT DEFAULT '0' NOT NULL,
  deleted_time TIMESTAMP WITH TIME ZONE,
  PRIMARY KEY (id),
  CONSTRAINT uq_study_ability_binding_key_mode_category_role UNIQUE (
    ability_key, mode, category_id, role
  ),
  CONSTRAINT ck_study_ability_binding_role CHECK (
    role IN ('knowledge_point','solution_method','ability')
  ),
  CONSTRAINT ck_study_ability_binding_weight CHECK (weight > 0),
  CONSTRAINT ck_study_ability_binding_confidence CHECK (confidence >= 0 AND confidence <= 1),
  FOREIGN KEY(category_id) REFERENCES fba.sys_category (id) ON DELETE RESTRICT
);
CREATE UNIQUE INDEX ix_study_ability_category_binding_id ON fba.study_ability_category_binding (id);
CREATE INDEX idx_study_ability_binding_key_mode ON fba.study_ability_category_binding (ability_key, mode);
CREATE INDEX idx_study_ability_binding_category ON fba.study_ability_category_binding (category_id);

-- ===== study_ability_attempt =====
CREATE TABLE fba.study_ability_attempt (
  id BIGSERIAL NOT NULL,
  user_id BIGINT NOT NULL,
  ability_key VARCHAR(64) NOT NULL,
  client_session_id VARCHAR(64) NOT NULL,
  mode VARCHAR(64),
  difficulty VARCHAR(32),
  source VARCHAR(32) NOT NULL,
  study_plan_item_id BIGINT,
  study_plan_record_id BIGINT,
  total_count INTEGER NOT NULL,
  correct_count INTEGER NOT NULL,
  wrong_count INTEGER NOT NULL,
  duration_seconds INTEGER NOT NULL,
  avg_seconds NUMERIC(8, 2),
  score NUMERIC(6, 2),
  metric_data JSONB,
  records JSONB,
  completed_at TIMESTAMP WITH TIME ZONE NOT NULL,
  completed_date DATE NOT NULL,
  created_time TIMESTAMP WITH TIME ZONE NOT NULL,
  updated_time TIMESTAMP WITH TIME ZONE,
  deleted BIGINT DEFAULT '0' NOT NULL,
  deleted_time TIMESTAMP WITH TIME ZONE,
  PRIMARY KEY (id),
  CONSTRAINT uq_study_ability_attempt_user_session UNIQUE (user_id, client_session_id),
  CONSTRAINT ck_study_ability_attempt_counts_nonneg CHECK (
    total_count >= 0 AND correct_count >= 0 AND wrong_count >= 0
  ),
  CONSTRAINT ck_study_ability_attempt_counts_logic CHECK (
    correct_count <= total_count AND wrong_count <= total_count
  ),
  CONSTRAINT ck_study_ability_attempt_duration CHECK (duration_seconds >= 0),
  CONSTRAINT ck_study_ability_attempt_score CHECK (score IS NULL OR (score >= 0 AND score <= 100)),
  FOREIGN KEY(user_id) REFERENCES fba.study_user_account (user_id) ON DELETE CASCADE,
  FOREIGN KEY(study_plan_item_id) REFERENCES fba.study_plan_item (id) ON DELETE SET NULL,
  FOREIGN KEY(study_plan_record_id) REFERENCES fba.study_plan_record (id) ON DELETE SET NULL
);
CREATE UNIQUE INDEX ix_study_ability_attempt_id ON fba.study_ability_attempt (id);
CREATE INDEX idx_study_ability_attempt_user_time ON fba.study_ability_attempt (user_id, completed_at);
CREATE INDEX idx_study_ability_attempt_key_time ON fba.study_ability_attempt (ability_key, completed_at);
CREATE INDEX idx_study_ability_attempt_plan_item ON fba.study_ability_attempt (study_plan_item_id);

-- ===== study_ability_attempt_category =====
CREATE TABLE fba.study_ability_attempt_category (
  id BIGSERIAL NOT NULL,
  attempt_id BIGINT NOT NULL,
  user_id BIGINT NOT NULL,
  category_id BIGINT NOT NULL,
  completed_at TIMESTAMP WITH TIME ZONE NOT NULL,
  completed_date DATE NOT NULL,
  role VARCHAR(32) NOT NULL,
  weight NUMERIC(6, 4) NOT NULL,
  total_count INTEGER NOT NULL,
  correct_count INTEGER NOT NULL,
  duration_seconds INTEGER NOT NULL,
  score NUMERIC(6, 2),
  created_time TIMESTAMP WITH TIME ZONE NOT NULL,
  updated_time TIMESTAMP WITH TIME ZONE,
  deleted BIGINT DEFAULT '0' NOT NULL,
  deleted_time TIMESTAMP WITH TIME ZONE,
  PRIMARY KEY (id),
  CONSTRAINT ck_study_ability_attempt_category_role CHECK (
    role IN ('knowledge_point','solution_method','ability')
  ),
  CONSTRAINT ck_study_ability_attempt_category_weight CHECK (weight > 0),
  CONSTRAINT ck_study_ability_attempt_category_counts CHECK (total_count >= 0 AND correct_count >= 0),
  CONSTRAINT ck_study_ability_attempt_category_duration CHECK (duration_seconds >= 0),
  FOREIGN KEY(attempt_id) REFERENCES fba.study_ability_attempt (id) ON DELETE CASCADE,
  FOREIGN KEY(user_id) REFERENCES fba.study_user_account (user_id) ON DELETE CASCADE,
  FOREIGN KEY(category_id) REFERENCES fba.sys_category (id) ON DELETE RESTRICT
);
CREATE UNIQUE INDEX ix_study_ability_attempt_category_id ON fba.study_ability_attempt_category (id);
CREATE INDEX idx_study_ability_attempt_category_attempt ON fba.study_ability_attempt_category (attempt_id);
CREATE INDEX idx_study_ability_attempt_category_user_cat_time
  ON fba.study_ability_attempt_category (user_id, category_id, completed_at);
CREATE INDEX idx_study_ability_attempt_category_cat_time
  ON fba.study_ability_attempt_category (category_id, completed_at);

-- ===== study_user_category_profile =====
CREATE TABLE fba.study_user_category_profile (
  id BIGSERIAL NOT NULL,
  user_id BIGINT NOT NULL,
  category_id BIGINT NOT NULL,
  source_type VARCHAR(32) NOT NULL,
  attempt_count INTEGER NOT NULL,
  total_count INTEGER NOT NULL,
  correct_count INTEGER NOT NULL,
  duration_seconds INTEGER NOT NULL,
  accuracy_rate NUMERIC(6, 2) NOT NULL,
  avg_seconds NUMERIC(8, 2),
  mastery_score NUMERIC(6, 2) NOT NULL,
  speed_score NUMERIC(6, 2) NOT NULL,
  confidence_score NUMERIC(6, 2) NOT NULL,
  trend_score NUMERIC(6, 2) NOT NULL,
  weakness_score NUMERIC(6, 2) NOT NULL,
  last_attempt_at TIMESTAMP WITH TIME ZONE,
  algorithm_version VARCHAR(32) NOT NULL,
  created_time TIMESTAMP WITH TIME ZONE NOT NULL,
  updated_time TIMESTAMP WITH TIME ZONE,
  deleted BIGINT DEFAULT '0' NOT NULL,
  deleted_time TIMESTAMP WITH TIME ZONE,
  PRIMARY KEY (id),
  CONSTRAINT uq_study_user_category_profile_source UNIQUE (user_id, category_id, source_type),
  CONSTRAINT ck_study_user_category_profile_source CHECK (source_type IN ('ability','question_bank')),
  CONSTRAINT ck_study_user_category_profile_counts CHECK (
    attempt_count >= 0 AND total_count >= 0 AND correct_count >= 0
  ),
  CONSTRAINT ck_study_user_category_profile_duration CHECK (duration_seconds >= 0),
  FOREIGN KEY(user_id) REFERENCES fba.study_user_account (user_id) ON DELETE CASCADE,
  FOREIGN KEY(category_id) REFERENCES fba.sys_category (id) ON DELETE RESTRICT
);
CREATE UNIQUE INDEX ix_study_user_category_profile_id ON fba.study_user_category_profile (id);
CREATE INDEX idx_study_user_category_profile_user ON fba.study_user_category_profile (user_id);
CREATE INDEX idx_study_user_category_profile_category ON fba.study_user_category_profile (category_id);
CREATE INDEX idx_study_user_category_profile_mastery ON fba.study_user_category_profile (mastery_score);

COMMIT;
