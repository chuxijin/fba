-- 用户反馈表
CREATE TABLE IF NOT EXISTS oc_feedback (
    id BIGSERIAL PRIMARY KEY,
    type VARCHAR(20) NOT NULL,
    content TEXT NOT NULL,
    ip VARCHAR(50),
    user_agent VARCHAR(500),
    status VARCHAR(20) DEFAULT 'pending',
    created_by BIGINT NOT NULL,
    updated_by BIGINT,
    created_time TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_time TIMESTAMP WITH TIME ZONE
);

COMMENT ON TABLE oc_feedback IS '用户反馈表';
COMMENT ON COLUMN oc_feedback.type IS '反馈类型: bug/feature/data/other';
COMMENT ON COLUMN oc_feedback.content IS '内容';
COMMENT ON COLUMN oc_feedback.ip IS 'IP地址';
COMMENT ON COLUMN oc_feedback.user_agent IS '浏览器信息';
COMMENT ON COLUMN oc_feedback.status IS '状态: pending/processing/resolved/closed';
COMMENT ON COLUMN oc_feedback.created_by IS '创建者';
COMMENT ON COLUMN oc_feedback.updated_by IS '修改者';
COMMENT ON COLUMN oc_feedback.created_time IS '创建时间';
COMMENT ON COLUMN oc_feedback.updated_time IS '更新时间';

CREATE INDEX IF NOT EXISTS idx_oc_feedback_created_by ON oc_feedback(created_by);
CREATE INDEX IF NOT EXISTS idx_oc_feedback_type ON oc_feedback(type);
CREATE INDEX IF NOT EXISTS idx_oc_feedback_status ON oc_feedback(status);
