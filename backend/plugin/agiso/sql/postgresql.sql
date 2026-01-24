-- 阿奇索推送日志表
CREATE TABLE IF NOT EXISTS agiso_push_log (
    id SERIAL PRIMARY KEY,
    push_type VARCHAR(50) NOT NULL,
    order_no VARCHAR(100) NOT NULL,
    platform VARCHAR(50) DEFAULT NULL,
    push_data TEXT NOT NULL,
    process_status INTEGER NOT NULL DEFAULT 0,
    process_result TEXT DEFAULT NULL,
    error_message TEXT DEFAULT NULL,
    retry_count INTEGER NOT NULL DEFAULT 0,
    created_time TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    processed_time TIMESTAMP WITH TIME ZONE DEFAULT NULL
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_agiso_push_log_order_no ON agiso_push_log(order_no);
CREATE INDEX IF NOT EXISTS idx_agiso_push_log_push_type ON agiso_push_log(push_type);
CREATE INDEX IF NOT EXISTS idx_agiso_push_log_process_status ON agiso_push_log(process_status);
CREATE INDEX IF NOT EXISTS idx_agiso_push_log_created_time ON agiso_push_log(created_time);

-- 添加注释
COMMENT ON TABLE agiso_push_log IS '阿奇索推送日志表';
COMMENT ON COLUMN agiso_push_log.id IS '主键ID';
COMMENT ON COLUMN agiso_push_log.push_type IS '推送类型(payment:支付推送 delivery:发卡推送)';
COMMENT ON COLUMN agiso_push_log.order_no IS '订单编号';
COMMENT ON COLUMN agiso_push_log.platform IS '来源平台';
COMMENT ON COLUMN agiso_push_log.push_data IS '推送原始数据';
COMMENT ON COLUMN agiso_push_log.process_status IS '处理状态(0:待处理 1:处理成功 2:处理失败)';
COMMENT ON COLUMN agiso_push_log.process_result IS '处理结果';
COMMENT ON COLUMN agiso_push_log.error_message IS '错误信息';
COMMENT ON COLUMN agiso_push_log.retry_count IS '重试次数';
COMMENT ON COLUMN agiso_push_log.created_time IS '创建时间';
COMMENT ON COLUMN agiso_push_log.processed_time IS '处理时间';
