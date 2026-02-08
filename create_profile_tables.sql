-- 用户画像及字典表建表语句
-- 执行前请先备份数据库

BEGIN;

-- ==================== 地区字典表 ====================
CREATE TABLE IF NOT EXISTS gk_dict_region (
    id BIGSERIAL PRIMARY KEY,
    code VARCHAR(20) NOT NULL UNIQUE,
    name VARCHAR(100) NOT NULL,
    short_name VARCHAR(50),
    level INTEGER NOT NULL,
    parent_code VARCHAR(20),
    longitude FLOAT,
    latitude FLOAT,
    is_remote_area BOOLEAN DEFAULT FALSE,
    sort_order INTEGER DEFAULT 0,
    created_time TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_time TIMESTAMP WITH TIME ZONE
);

CREATE INDEX IF NOT EXISTS ix_dict_region_code ON gk_dict_region(code);
CREATE INDEX IF NOT EXISTS ix_dict_region_name ON gk_dict_region(name);
CREATE INDEX IF NOT EXISTS ix_dict_region_parent ON gk_dict_region(parent_code);
CREATE INDEX IF NOT EXISTS ix_dict_region_level ON gk_dict_region(level);

COMMENT ON TABLE gk_dict_region IS '地区字典表';
COMMENT ON COLUMN gk_dict_region.code IS '地区代码';
COMMENT ON COLUMN gk_dict_region.name IS '地区名称';
COMMENT ON COLUMN gk_dict_region.short_name IS '简称';
COMMENT ON COLUMN gk_dict_region.level IS '级别: 1省 2市 3县/区';
COMMENT ON COLUMN gk_dict_region.parent_code IS '父级代码';
COMMENT ON COLUMN gk_dict_region.is_remote_area IS '是否艰苦边远地区';

-- ==================== 专业目录字典表 ====================
CREATE TABLE IF NOT EXISTS gk_dict_major (
    id BIGSERIAL PRIMARY KEY,
    code VARCHAR(20) NOT NULL UNIQUE,
    name VARCHAR(200) NOT NULL,
    level INTEGER NOT NULL,
    parent_code VARCHAR(20),
    edu_level VARCHAR(20) DEFAULT '本科',
    aliases TEXT[],
    description TEXT,
    sort_order INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    created_time TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_time TIMESTAMP WITH TIME ZONE
);

CREATE INDEX IF NOT EXISTS ix_dict_major_code ON gk_dict_major(code);
CREATE INDEX IF NOT EXISTS ix_dict_major_name ON gk_dict_major(name);
CREATE INDEX IF NOT EXISTS ix_dict_major_parent ON gk_dict_major(parent_code);
CREATE INDEX IF NOT EXISTS ix_dict_major_level ON gk_dict_major(level);
CREATE INDEX IF NOT EXISTS ix_dict_major_edu ON gk_dict_major(edu_level);

COMMENT ON TABLE gk_dict_major IS '专业目录字典表';
COMMENT ON COLUMN gk_dict_major.code IS '专业代码';
COMMENT ON COLUMN gk_dict_major.name IS '专业名称';
COMMENT ON COLUMN gk_dict_major.level IS '级别: 1学科门类 2专业类 3专业';
COMMENT ON COLUMN gk_dict_major.edu_level IS '学历层次: 本科/研究生';
COMMENT ON COLUMN gk_dict_major.aliases IS '专业别名列表';

-- ==================== 用户画像主表 ====================
CREATE TABLE IF NOT EXISTS gk_user_profile (
    id BIGSERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL UNIQUE,
    birth_date DATE,
    gender VARCHAR(10),
    ethnicity VARCHAR(50),
    hukou_region_code VARCHAR(20),
    origin_region_code VARCHAR(20),
    politics VARCHAR(50),
    special_identity VARCHAR(200),
    is_fresh_graduate BOOLEAN DEFAULT FALSE,
    total_work_years INTEGER DEFAULT 0,
    created_time TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_time TIMESTAMP WITH TIME ZONE
);

CREATE INDEX IF NOT EXISTS ix_user_profile_user ON gk_user_profile(user_id);

COMMENT ON TABLE gk_user_profile IS '用户画像主表';
COMMENT ON COLUMN gk_user_profile.user_id IS '关联用户ID';
COMMENT ON COLUMN gk_user_profile.birth_date IS '出生日期';
COMMENT ON COLUMN gk_user_profile.gender IS '性别';
COMMENT ON COLUMN gk_user_profile.ethnicity IS '民族';
COMMENT ON COLUMN gk_user_profile.hukou_region_code IS '户籍地区代码';
COMMENT ON COLUMN gk_user_profile.origin_region_code IS '生源地代码';
COMMENT ON COLUMN gk_user_profile.politics IS '政治面貌';
COMMENT ON COLUMN gk_user_profile.special_identity IS '特殊身份';
COMMENT ON COLUMN gk_user_profile.is_fresh_graduate IS '是否为择业期应届生';
COMMENT ON COLUMN gk_user_profile.total_work_years IS '总工作年限（月）';

-- ==================== 教育经历表 ====================
CREATE TABLE IF NOT EXISTS gk_user_education (
    id BIGSERIAL PRIMARY KEY,
    profile_id BIGINT NOT NULL REFERENCES gk_user_profile(id) ON DELETE CASCADE,
    edu_level VARCHAR(50) NOT NULL,
    degree VARCHAR(50),
    edu_type VARCHAR(50) DEFAULT '全日制',
    major_code VARCHAR(20),
    major_name VARCHAR(200),
    major_category VARCHAR(100),
    major_discipline VARCHAR(100),
    school_name VARCHAR(200),
    school_type VARCHAR(100),
    enrollment_batch VARCHAR(50),
    start_date DATE,
    end_date DATE,
    is_highest BOOLEAN DEFAULT FALSE,
    created_time TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_time TIMESTAMP WITH TIME ZONE
);

CREATE INDEX IF NOT EXISTS ix_user_education_profile ON gk_user_education(profile_id);
CREATE INDEX IF NOT EXISTS ix_user_education_major ON gk_user_education(major_code);

COMMENT ON TABLE gk_user_education IS '用户教育经历表';

-- ==================== 地区偏好表 ====================
CREATE TABLE IF NOT EXISTS gk_user_region_preference (
    id BIGSERIAL PRIMARY KEY,
    profile_id BIGINT NOT NULL REFERENCES gk_user_profile(id) ON DELETE CASCADE,
    province_code VARCHAR(20),
    city_code VARCHAR(20),
    county_code VARCHAR(20),
    priority INTEGER DEFAULT 1,
    include_sub_regions BOOLEAN DEFAULT TRUE,
    accept_remote_area BOOLEAN DEFAULT FALSE,
    created_time TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_time TIMESTAMP WITH TIME ZONE
);

CREATE INDEX IF NOT EXISTS ix_user_region_pref_profile ON gk_user_region_preference(profile_id);

COMMENT ON TABLE gk_user_region_preference IS '用户地区偏好表';

-- ==================== 资格证书表 ====================
CREATE TABLE IF NOT EXISTS gk_user_certificate (
    id BIGSERIAL PRIMARY KEY,
    profile_id BIGINT NOT NULL REFERENCES gk_user_profile(id) ON DELETE CASCADE,
    cert_type VARCHAR(100) NOT NULL,
    cert_name VARCHAR(200) NOT NULL,
    cert_level VARCHAR(100),
    cert_no VARCHAR(100),
    issue_date DATE,
    expire_date DATE,
    created_time TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_time TIMESTAMP WITH TIME ZONE
);

CREATE INDEX IF NOT EXISTS ix_user_certificate_profile ON gk_user_certificate(profile_id);

COMMENT ON TABLE gk_user_certificate IS '用户资格证书表';

-- ==================== 工作经历表 ====================
CREATE TABLE IF NOT EXISTS gk_user_work_experience (
    id BIGSERIAL PRIMARY KEY,
    profile_id BIGINT NOT NULL REFERENCES gk_user_profile(id) ON DELETE CASCADE,
    company_name VARCHAR(200) NOT NULL,
    company_type VARCHAR(100),
    position VARCHAR(200),
    department VARCHAR(200),
    start_date DATE,
    end_date DATE,
    is_current BOOLEAN DEFAULT FALSE,
    is_grassroots BOOLEAN DEFAULT FALSE,
    grassroots_project VARCHAR(100),
    service_region_code VARCHAR(20),
    description TEXT,
    created_time TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_time TIMESTAMP WITH TIME ZONE
);

CREATE INDEX IF NOT EXISTS ix_user_work_exp_profile ON gk_user_work_experience(profile_id);

COMMENT ON TABLE gk_user_work_experience IS '用户工作经历表';

-- ==================== 荣誉成就表 ====================
CREATE TABLE IF NOT EXISTS gk_user_honor (
    id BIGSERIAL PRIMARY KEY,
    profile_id BIGINT NOT NULL REFERENCES gk_user_profile(id) ON DELETE CASCADE,
    honor_type VARCHAR(100) NOT NULL,
    honor_name VARCHAR(200) NOT NULL,
    honor_level VARCHAR(100),
    issue_org VARCHAR(200),
    issue_date DATE,
    description TEXT,
    created_time TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_time TIMESTAMP WITH TIME ZONE
);

CREATE INDEX IF NOT EXISTS ix_user_honor_profile ON gk_user_honor(profile_id);

COMMENT ON TABLE gk_user_honor IS '用户荣誉成就表';

COMMIT;
