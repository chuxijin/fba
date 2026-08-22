CREATE TABLE IF NOT EXISTS agent_run (
  id BIGINT PRIMARY KEY,
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
  id BIGINT PRIMARY KEY,
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
  id BIGINT PRIMARY KEY,
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
  id BIGINT PRIMARY KEY,
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
  id BIGINT PRIMARY KEY,
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
  id BIGINT PRIMARY KEY,
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
