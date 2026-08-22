CREATE TABLE IF NOT EXISTS agent_run (
  id BIGSERIAL PRIMARY KEY,
  agent_key VARCHAR(64) NOT NULL,
  agent_version VARCHAR(32) NOT NULL,
  workflow_key VARCHAR(64) NOT NULL,
  workflow_version VARCHAR(32) NOT NULL,
  user_id BIGINT NOT NULL,
  subject_type VARCHAR(64) NOT NULL,
  subject_id BIGINT NOT NULL,
  idempotency_key VARCHAR(160) NOT NULL UNIQUE,
  status VARCHAR(24) NOT NULL DEFAULT 'queued',
  stage VARCHAR(64),
  progress DOUBLE PRECISION NOT NULL DEFAULT 0,
  input_snapshot JSONB NOT NULL,
  result_summary TEXT,
  result_payload JSONB,
  config_snapshot JSONB NOT NULL,
  error_code VARCHAR(64),
  error_message TEXT,
  started_time TIMESTAMPTZ,
  finished_time TIMESTAMPTZ,
  created_time TIMESTAMPTZ NOT NULL,
  updated_time TIMESTAMPTZ,
  deleted BIGINT NOT NULL DEFAULT 0,
  deleted_time TIMESTAMPTZ
  ,CONSTRAINT fk_agent_run_user FOREIGN KEY (user_id) REFERENCES sys_user (id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_agent_run_user_status ON agent_run (user_id, status, created_time);
CREATE INDEX IF NOT EXISTS idx_agent_run_subject ON agent_run (subject_type, subject_id, created_time);

CREATE TABLE IF NOT EXISTS agent_run_step (
  id BIGSERIAL PRIMARY KEY,
  run_id BIGINT NOT NULL,
  step_no INTEGER NOT NULL,
  node_key VARCHAR(64) NOT NULL,
  status VARCHAR(24) NOT NULL DEFAULT 'running',
  input_snapshot JSONB NOT NULL,
  output_snapshot JSONB,
  model_name VARCHAR(128),
  tokens_in INTEGER NOT NULL DEFAULT 0,
  tokens_out INTEGER NOT NULL DEFAULT 0,
  duration_ms INTEGER NOT NULL DEFAULT 0,
  error_message TEXT,
  started_time TIMESTAMPTZ,
  finished_time TIMESTAMPTZ,
  created_time TIMESTAMPTZ NOT NULL,
  updated_time TIMESTAMPTZ,
  deleted BIGINT NOT NULL DEFAULT 0,
  deleted_time TIMESTAMPTZ,
  UNIQUE (run_id, step_no)
  ,CONSTRAINT fk_agent_run_step_run FOREIGN KEY (run_id) REFERENCES agent_run (id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_agent_run_step_run ON agent_run_step (run_id, step_no);

CREATE TABLE IF NOT EXISTS agent_rubric (
  id BIGSERIAL PRIMARY KEY,
  agent_key VARCHAR(64) NOT NULL,
  question_id BIGINT NOT NULL,
  reference_set_hash VARCHAR(64) NOT NULL,
  source_hash VARCHAR(64) NOT NULL,
  rubric_version VARCHAR(64) NOT NULL,
  status VARCHAR(24) NOT NULL DEFAULT 'ready',
  provider VARCHAR(128),
  model_name VARCHAR(128),
  rubric_payload JSONB NOT NULL,
  error_message TEXT,
  created_time TIMESTAMPTZ NOT NULL,
  updated_time TIMESTAMPTZ,
  deleted BIGINT NOT NULL DEFAULT 0,
  deleted_time TIMESTAMPTZ,
  UNIQUE (agent_key, question_id, reference_set_hash, source_hash, rubric_version)
);
CREATE INDEX IF NOT EXISTS idx_agent_rubric_question
  ON agent_rubric (agent_key, question_id, status);

CREATE TABLE IF NOT EXISTS agent_grading_feedback (
  id BIGSERIAL PRIMARY KEY,
  run_id BIGINT NOT NULL REFERENCES agent_run (id) ON DELETE CASCADE,
  user_id BIGINT NOT NULL,
  question_id BIGINT NOT NULL,
  point_key VARCHAR(80) NOT NULL,
  scope VARCHAR(16) NOT NULL DEFAULT 'report',
  corrected_status VARCHAR(16) NOT NULL,
  corrected_quote TEXT NOT NULL DEFAULT '',
  note TEXT NOT NULL DEFAULT '',
  before_snapshot JSONB NOT NULL,
  after_snapshot JSONB NOT NULL,
  created_time TIMESTAMPTZ NOT NULL,
  updated_time TIMESTAMPTZ,
  deleted BIGINT NOT NULL DEFAULT 0,
  deleted_time TIMESTAMPTZ,
  UNIQUE (run_id, point_key, scope)
);

CREATE TABLE IF NOT EXISTS agent_calibration_anchor (
  id BIGSERIAL PRIMARY KEY,
  agent_key VARCHAR(64) NOT NULL,
  bank_revision_id BIGINT NOT NULL,
  session_id BIGINT NOT NULL,
  user_id BIGINT NOT NULL,
  actual_score_percent NUMERIC(7,3) NOT NULL,
  predicted_score_percent NUMERIC(7,3) NOT NULL,
  actual_total_score NUMERIC(10,3) NOT NULL,
  predicted_total_score NUMERIC(10,3) NOT NULL,
  paper_total_score NUMERIC(10,3) NOT NULL,
  source_type VARCHAR(32) NOT NULL,
  source_hash VARCHAR(64) NOT NULL,
  status VARCHAR(16) NOT NULL DEFAULT 'ready',
  exclusion_reason TEXT,
  metadata_payload JSONB NOT NULL,
  created_time TIMESTAMPTZ NOT NULL,
  updated_time TIMESTAMPTZ,
  deleted BIGINT NOT NULL DEFAULT 0,
  deleted_time TIMESTAMPTZ,
  UNIQUE (agent_key, session_id)
);
CREATE INDEX IF NOT EXISTS idx_agent_calibration_anchor_ready
  ON agent_calibration_anchor (agent_key, status, bank_revision_id);
CREATE INDEX IF NOT EXISTS idx_agent_calibration_anchor_session
  ON agent_calibration_anchor (session_id, created_time);

CREATE TABLE IF NOT EXISTS agent_calibration_policy (
  id BIGSERIAL PRIMARY KEY,
  agent_key VARCHAR(64) NOT NULL,
  policy_version VARCHAR(64) NOT NULL,
  scope_type VARCHAR(24) NOT NULL,
  scope_key VARCHAR(160) NOT NULL,
  active_key VARCHAR(192),
  status VARCHAR(16) NOT NULL DEFAULT 'draft',
  anchor_count INTEGER NOT NULL DEFAULT 0,
  paper_count INTEGER NOT NULL DEFAULT 0,
  source_hash VARCHAR(64) NOT NULL,
  policy_payload JSONB NOT NULL,
  metrics_payload JSONB NOT NULL,
  created_time TIMESTAMPTZ NOT NULL,
  updated_time TIMESTAMPTZ,
  deleted BIGINT NOT NULL DEFAULT 0,
  deleted_time TIMESTAMPTZ,
  UNIQUE (agent_key, source_hash),
  UNIQUE (agent_key, active_key)
);
CREATE INDEX IF NOT EXISTS idx_agent_calibration_policy_scope
  ON agent_calibration_policy (agent_key, scope_type, scope_key, status);
CREATE INDEX IF NOT EXISTS idx_agent_grading_feedback_question
  ON agent_grading_feedback (question_id, scope, created_time);

CREATE TABLE IF NOT EXISTS agent_shenlun_coach_session (
  id BIGSERIAL PRIMARY KEY,
  user_id BIGINT NOT NULL REFERENCES sys_user (id) ON DELETE CASCADE,
  title VARCHAR(160) NOT NULL DEFAULT '申论训练教练',
  status VARCHAR(24) NOT NULL DEFAULT 'active',
  context_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb,
  last_summary TEXT,
  created_time TIMESTAMPTZ NOT NULL,
  updated_time TIMESTAMPTZ,
  deleted BIGINT NOT NULL DEFAULT 0,
  deleted_time TIMESTAMPTZ,
  CONSTRAINT ck_agent_coach_session_status CHECK (status IN ('active','archived'))
);
CREATE INDEX IF NOT EXISTS idx_agent_coach_session_user_status
  ON agent_shenlun_coach_session (user_id, status, updated_time);

CREATE TABLE IF NOT EXISTS agent_shenlun_coach_message (
  id BIGSERIAL PRIMARY KEY,
  session_id BIGINT NOT NULL REFERENCES agent_shenlun_coach_session (id) ON DELETE CASCADE,
  user_id BIGINT NOT NULL REFERENCES sys_user (id) ON DELETE CASCADE,
  role VARCHAR(16) NOT NULL,
  content TEXT NOT NULL,
  request_id VARCHAR(80),
  metadata_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_time TIMESTAMPTZ NOT NULL,
  updated_time TIMESTAMPTZ,
  deleted BIGINT NOT NULL DEFAULT 0,
  deleted_time TIMESTAMPTZ,
  CONSTRAINT uq_agent_coach_message_request UNIQUE (session_id, request_id),
  CONSTRAINT ck_agent_coach_message_role CHECK (role IN ('user','coach','system'))
);
CREATE INDEX IF NOT EXISTS idx_agent_coach_message_session_time
  ON agent_shenlun_coach_message (session_id, created_time);

CREATE TABLE IF NOT EXISTS agent_shenlun_coach_memory (
  id BIGSERIAL PRIMARY KEY,
  user_id BIGINT NOT NULL REFERENCES sys_user (id) ON DELETE CASCADE,
  memory_key VARCHAR(120) NOT NULL,
  memory_type VARCHAR(32) NOT NULL,
  content TEXT NOT NULL,
  confidence DOUBLE PRECISION NOT NULL DEFAULT 0.5,
  source_ref VARCHAR(160),
  evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
  last_seen_time TIMESTAMPTZ,
  created_time TIMESTAMPTZ NOT NULL,
  updated_time TIMESTAMPTZ,
  deleted BIGINT NOT NULL DEFAULT 0,
  deleted_time TIMESTAMPTZ,
  CONSTRAINT uq_agent_coach_memory_user_key UNIQUE (user_id, memory_key, deleted),
  CONSTRAINT ck_agent_coach_memory_type CHECK (memory_type IN ('weakness','strength','preference','goal')),
  CONSTRAINT ck_agent_coach_memory_confidence CHECK (confidence BETWEEN 0 AND 1)
);
CREATE INDEX IF NOT EXISTS idx_agent_coach_memory_user_type
  ON agent_shenlun_coach_memory (user_id, memory_type, updated_time);

CREATE TABLE IF NOT EXISTS agent_shenlun_training_plan (
  id BIGSERIAL PRIMARY KEY,
  user_id BIGINT NOT NULL REFERENCES sys_user (id) ON DELETE CASCADE,
  request_id VARCHAR(80),
  title VARCHAR(160) NOT NULL,
  status VARCHAR(24) NOT NULL DEFAULT 'active',
  goal TEXT NOT NULL,
  start_date TIMESTAMPTZ,
  end_date TIMESTAMPTZ,
  summary JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_time TIMESTAMPTZ NOT NULL,
  updated_time TIMESTAMPTZ,
  deleted BIGINT NOT NULL DEFAULT 0,
  deleted_time TIMESTAMPTZ,
  CONSTRAINT ck_agent_training_plan_status CHECK (status IN ('draft','active','completed','archived'))
);
CREATE INDEX IF NOT EXISTS idx_agent_training_plan_user_status
  ON agent_shenlun_training_plan (user_id, status, created_time);
CREATE UNIQUE INDEX IF NOT EXISTS uq_agent_training_plan_user_request
  ON agent_shenlun_training_plan (user_id, request_id, deleted)
  WHERE request_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS agent_shenlun_training_plan_item (
  id BIGSERIAL PRIMARY KEY,
  plan_id BIGINT NOT NULL REFERENCES agent_shenlun_training_plan (id) ON DELETE CASCADE,
  user_id BIGINT NOT NULL REFERENCES sys_user (id) ON DELETE CASCADE,
  due_date TIMESTAMPTZ,
  task_type VARCHAR(32) NOT NULL,
  title VARCHAR(200) NOT NULL,
  instruction TEXT NOT NULL,
  target JSONB NOT NULL DEFAULT '{}'::jsonb,
  status VARCHAR(24) NOT NULL DEFAULT 'pending',
  completed_time TIMESTAMPTZ,
  created_time TIMESTAMPTZ NOT NULL,
  updated_time TIMESTAMPTZ,
  deleted BIGINT NOT NULL DEFAULT 0,
  deleted_time TIMESTAMPTZ,
  CONSTRAINT ck_agent_training_plan_item_type CHECK (task_type IN ('practice','review','reflection')),
  CONSTRAINT ck_agent_training_plan_item_status CHECK (status IN ('pending','in_progress','completed','skipped'))
);
CREATE INDEX IF NOT EXISTS idx_agent_training_plan_item_plan_due
  ON agent_shenlun_training_plan_item (plan_id, due_date, status);
