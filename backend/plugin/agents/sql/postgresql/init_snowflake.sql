CREATE TABLE IF NOT EXISTS plugin_agents_task (
    id BIGINT PRIMARY KEY,
    agent_type VARCHAR(64) NOT NULL,
    user_id BIGINT NOT NULL,
    provider_id BIGINT NOT NULL,
    model_id VARCHAR(128) NOT NULL,
    input_payload JSONB NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'pending',
    stage VARCHAR(64) NULL,
    progress DOUBLE PRECISION NOT NULL DEFAULT 0,
    state_snapshot JSONB NULL,
    report JSONB NULL,
    traces JSONB NULL,
    quota_consumed BOOLEAN NOT NULL DEFAULT FALSE,
    error_code VARCHAR(64) NULL,
    error_message TEXT NULL,
    created_time TIMESTAMP WITH TIME ZONE NOT NULL,
    updated_time TIMESTAMP WITH TIME ZONE NULL
);
CREATE INDEX IF NOT EXISTS idx_plugin_agents_task_status ON plugin_agents_task (status);
CREATE INDEX IF NOT EXISTS idx_plugin_agents_task_user_id ON plugin_agents_task (user_id);
CREATE INDEX IF NOT EXISTS idx_plugin_agents_task_agent_type ON plugin_agents_task (agent_type);
COMMENT ON TABLE plugin_agents_task IS 'Agent 任务表';
