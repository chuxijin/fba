-- 修改 job_posting 表字段长度的 SQL 脚本
-- 执行前请备份数据库！

-- MySQL 版本
-- 修改字段长度以支持更长的数据
ALTER TABLE job_posting 
MODIFY COLUMN company_name VARCHAR(500) COMMENT '公司名称',
MODIFY COLUMN company_type VARCHAR(500) COMMENT '公司类型',
MODIFY COLUMN industry VARCHAR(500) COMMENT '所属行业',
MODIFY COLUMN recruitment_type VARCHAR(500) COMMENT '招聘类型',
MODIFY COLUMN work_location VARCHAR(1000) COMMENT '工作地点',
MODIFY COLUMN recruitment_object VARCHAR(500) COMMENT '招聘对象',
MODIFY COLUMN position TEXT COMMENT '岗位';

-- 如果你使用的是 PostgreSQL，请使用以下语句：
-- ALTER TABLE job_posting 
-- ALTER COLUMN company_name TYPE VARCHAR(500),
-- ALTER COLUMN company_type TYPE VARCHAR(500),
-- ALTER COLUMN industry TYPE VARCHAR(500),
-- ALTER COLUMN recruitment_type TYPE VARCHAR(500),
-- ALTER COLUMN work_location TYPE VARCHAR(1000),
-- ALTER COLUMN recruitment_object TYPE VARCHAR(500),
-- ALTER COLUMN position TYPE TEXT;

-- 验证修改结果
DESCRIBE job_posting;

-- 或者使用 SHOW COLUMNS (MySQL)
-- SHOW COLUMNS FROM job_posting;

-- PostgreSQL 用户可以使用：
-- \d job_posting
