-- 创建Celery任务结果表
-- 这些表用于存储Celery任务的执行结果和状态

-- 创建task_result表
CREATE TABLE IF NOT EXISTS task_result (
    id SERIAL PRIMARY KEY,
    task_id VARCHAR(255) NOT NULL UNIQUE,
    status VARCHAR(50) NOT NULL,
    result BYTEA,
    date_done TIMESTAMP,
    traceback TEXT,
    name VARCHAR(255),
    args BYTEA,
    kwargs BYTEA,
    worker VARCHAR(100),
    retries INTEGER,
    queue VARCHAR(100)
);

-- 创建表注释
COMMENT ON TABLE task_result IS 'Celery任务结果表';

-- 创建task_group_result表
CREATE TABLE IF NOT EXISTS task_group_result (
    id SERIAL PRIMARY KEY,
    group_id VARCHAR(255) NOT NULL UNIQUE,
    result BYTEA,
    date_done TIMESTAMP
);

-- 创建表注释
COMMENT ON TABLE task_group_result IS 'Celery任务组结果表'; 