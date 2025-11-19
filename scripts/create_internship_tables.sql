-- 创建实习信息表
CREATE TABLE internship_posting (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    company_name VARCHAR(500) NOT NULL COMMENT '公司名称',
    company_type VARCHAR(500) COMMENT '公司类型',
    industry VARCHAR(500) COMMENT '所属行业',
    recruitment_type VARCHAR(500) COMMENT '招聘类型',
    work_location VARCHAR(1000) COMMENT '工作地点',
    recruitment_object VARCHAR(500) COMMENT '招聘对象',
    position TEXT NOT NULL COMMENT '岗位',
    delivery_start DATE COMMENT '投递开始日期',
    delivery_end DATE COMMENT '投递截止日期',
    delivery_link TEXT COMMENT '投递链接',
    recruitment_announcement TEXT COMMENT '招聘公告',
    referral_code VARCHAR(255) COMMENT '内推码',
    remark TEXT COMMENT '备注',
    salary_range VARCHAR(255) COMMENT '薪资范围',
    is_exempt_from_written_test BOOLEAN DEFAULT FALSE COMMENT '是否免笔试',
    logo_url VARCHAR(500) COMMENT '公司Logo URL',
    created_by BIGINT NOT NULL COMMENT '创建者',
    updated_by BIGINT COMMENT '更新者',
    created_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间'
);

-- 创建实习投递记录表
CREATE TABLE internship_application (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    internship_posting_id BIGINT NOT NULL COMMENT '实习信息 ID',
    application_status VARCHAR(50) NOT NULL COMMENT '投递状态',
    created_by BIGINT NOT NULL COMMENT '创建者',
    updated_by BIGINT COMMENT '更新者',
    created_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    FOREIGN KEY (internship_posting_id) REFERENCES internship_posting(id)
);

-- 为job_application表添加类型字段
ALTER TABLE job_application 
ADD COLUMN job_type VARCHAR(20) DEFAULT '校招' COMMENT '招聘类型';

-- 创建索引
CREATE INDEX idx_internship_posting_company ON internship_posting(company_name);
CREATE INDEX idx_internship_posting_type ON internship_posting(company_type);
CREATE INDEX idx_internship_posting_location ON internship_posting(work_location(255));
CREATE INDEX idx_internship_posting_created_by ON internship_posting(created_by);
CREATE INDEX idx_internship_application_posting_id ON internship_application(internship_posting_id);
CREATE INDEX idx_internship_application_created_by ON internship_application(created_by);
CREATE INDEX idx_job_application_type ON job_application(job_type);




