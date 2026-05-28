-- OC 求职工具平台 - 数据库初始化脚本 (PostgreSQL)

-- 校招岗位表
CREATE TABLE IF NOT EXISTS oc_campus_recruit (
    id BIGINT PRIMARY KEY,
    company_name TEXT NOT NULL,
    company_type VARCHAR(64) NOT NULL,
    industry VARCHAR(128) NOT NULL,
    recruitment_type VARCHAR(64) NOT NULL,
    recruit_target VARCHAR(128) NOT NULL,
    location TEXT NOT NULL,
    positions TEXT NOT NULL,
    update_time DATE NOT NULL,
    application_status VARCHAR(32) DEFAULT '未投递',
    company_size VARCHAR(100),
    deadline VARCHAR(64),
    apply_link TEXT,
    notice_link TEXT,
    referral_code VARCHAR(64),
    exam_info VARCHAR(500),
    remark TEXT,
    created_time TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_time TIMESTAMP WITH TIME ZONE
);
CREATE INDEX IF NOT EXISTS idx_oc_campus_recruit_company_name ON oc_campus_recruit(company_name);
COMMENT ON TABLE oc_campus_recruit IS '校招岗位表';

-- 实习岗位表
CREATE TABLE IF NOT EXISTS oc_intern_recruit (
    id BIGINT PRIMARY KEY,
    company_name TEXT NOT NULL,
    company_type VARCHAR(64) NOT NULL,
    industry VARCHAR(128) NOT NULL,
    recruitment_type VARCHAR(64) NOT NULL,
    recruit_target VARCHAR(128) NOT NULL,
    location TEXT NOT NULL,
    positions TEXT NOT NULL,
    update_time DATE NOT NULL,
    application_status VARCHAR(32) DEFAULT '未投递',
    deadline VARCHAR(64),
    apply_link TEXT,
    notice_link TEXT,
    referral_code VARCHAR(64),
    remark TEXT,
    created_time TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_time TIMESTAMP WITH TIME ZONE
);
CREATE INDEX IF NOT EXISTS idx_oc_intern_recruit_company_name ON oc_intern_recruit(company_name);
COMMENT ON TABLE oc_intern_recruit IS '实习岗位表';

-- 用户投递记录表
CREATE TABLE IF NOT EXISTS oc_user_application (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES sys_user(id) ON DELETE CASCADE,
    job_id BIGINT NOT NULL,
    job_type VARCHAR(16) NOT NULL,
    application_status VARCHAR(32) DEFAULT '未投递',
    applied_at TIMESTAMP,
    remark TEXT,
    created_time TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_time TIMESTAMP WITH TIME ZONE
);
CREATE INDEX IF NOT EXISTS idx_oc_user_application_user_id ON oc_user_application(user_id);
CREATE INDEX IF NOT EXISTS idx_oc_user_application_job_id ON oc_user_application(job_id);
COMMENT ON TABLE oc_user_application IS '用户投递记录表';

-- 笔面试资料包表
CREATE TABLE IF NOT EXISTS oc_resource (
    id BIGSERIAL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    image VARCHAR(500),
    baidu_link VARCHAR(500),
    extract_code VARCHAR(10),
    created_time TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_time TIMESTAMP WITH TIME ZONE
);
COMMENT ON TABLE oc_resource IS '笔试面试资料包表';

-- 字段配置表
CREATE TABLE IF NOT EXISTS oc_formatter_field (
    id BIGSERIAL PRIMARY KEY,
    category VARCHAR(50) NOT NULL,
    field_name VARCHAR(50) NOT NULL,
    chinese VARCHAR(100) NOT NULL,
    strategy VARCHAR(30) DEFAULT 'input',
    level SMALLINT DEFAULT 0,
    field_order SMALLINT DEFAULT 0,
    tips VARCHAR(500),
    default_value VARCHAR(200),
    is_array BOOLEAN DEFAULT FALSE,
    is_hidden BOOLEAN DEFAULT FALSE,
    parent_field_id BIGINT,
    created_time TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_time TIMESTAMP WITH TIME ZONE,
    CONSTRAINT uq_formatter_field UNIQUE (category, field_name, parent_field_id)
);
CREATE INDEX IF NOT EXISTS idx_oc_formatter_field_category ON oc_formatter_field(category);
COMMENT ON TABLE oc_formatter_field IS '字段配置表';

-- 标签匹配规则表
CREATE TABLE IF NOT EXISTS oc_formatter_embedding (
    id BIGSERIAL PRIMARY KEY,
    field_id BIGINT NOT NULL,
    label VARCHAR(200) NOT NULL,
    value_script TEXT,
    share_data_list VARCHAR(500),
    created_time TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_time TIMESTAMP WITH TIME ZONE
);
CREATE INDEX IF NOT EXISTS idx_oc_formatter_embedding_field_id ON oc_formatter_embedding(field_id);
COMMENT ON TABLE oc_formatter_embedding IS '标签匹配规则表';

-- 下拉选项映射表
CREATE TABLE IF NOT EXISTS oc_formatter_mapping (
    id BIGSERIAL PRIMARY KEY,
    field_id BIGINT NOT NULL,
    source_value VARCHAR(100) NOT NULL,
    target_values VARCHAR(500) NOT NULL,
    created_time TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_time TIMESTAMP WITH TIME ZONE,
    CONSTRAINT uq_formatter_mapping UNIQUE (field_id, source_value)
);
CREATE INDEX IF NOT EXISTS idx_oc_formatter_mapping_field_id ON oc_formatter_mapping(field_id);
COMMENT ON TABLE oc_formatter_mapping IS '下拉选项映射表';

-- 内推码表
CREATE TABLE IF NOT EXISTS oc_referral_code (
    id BIGSERIAL PRIMARY KEY,
    company_name VARCHAR(128) NOT NULL,
    referral_code VARCHAR(128) NOT NULL,
    remark TEXT,
    created_by BIGINT,
    updated_by BIGINT,
    created_time TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_time TIMESTAMP WITH TIME ZONE
);
CREATE INDEX IF NOT EXISTS idx_oc_referral_code_company_name ON oc_referral_code(company_name);
COMMENT ON TABLE oc_referral_code IS '内推码表';

-- 用户反馈表
CREATE TABLE IF NOT EXISTS oc_feedback (
    id BIGSERIAL PRIMARY KEY,
    type VARCHAR(20) NOT NULL,
    content TEXT NOT NULL,
    ip VARCHAR(50),
    user_agent VARCHAR(500),
    status VARCHAR(20) DEFAULT 'pending',
    created_by BIGINT,
    updated_by BIGINT,
    created_time TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_time TIMESTAMP WITH TIME ZONE
);
CREATE INDEX IF NOT EXISTS idx_oc_feedback_created_by ON oc_feedback(created_by);
CREATE INDEX IF NOT EXISTS idx_oc_feedback_type ON oc_feedback(type);
CREATE INDEX IF NOT EXISTS idx_oc_feedback_status ON oc_feedback(status);
COMMENT ON TABLE oc_feedback IS '用户反馈表';

-- 用户简历表
CREATE TABLE IF NOT EXISTS oc_user_resume (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL UNIQUE,
    encrypted_data TEXT NOT NULL,
    data_hash VARCHAR(64) NOT NULL,
    created_time TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_time TIMESTAMP WITH TIME ZONE
);
CREATE INDEX IF NOT EXISTS idx_oc_user_resume_user_id ON oc_user_resume(user_id);
COMMENT ON TABLE oc_user_resume IS '用户简历表';
