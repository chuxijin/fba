-- 扩展 gk_gangwei 表字段长度
-- 执行前请先备份数据库或在测试环境验证

BEGIN;

-- ========== 基础标识 ==========
ALTER TABLE gk_gangwei ALTER COLUMN dept_code TYPE VARCHAR(100);

-- ========== 部门信息 ==========
ALTER TABLE gk_gangwei ALTER COLUMN dept_name TYPE VARCHAR(300);
ALTER TABLE gk_gangwei ALTER COLUMN bureau TYPE VARCHAR(300);
ALTER TABLE gk_gangwei ALTER COLUMN org_nature TYPE VARCHAR(200);
ALTER TABLE gk_gangwei ALTER COLUMN org_level TYPE VARCHAR(100);

-- ========== 职位信息 ==========
ALTER TABLE gk_gangwei ALTER COLUMN position_name TYPE VARCHAR(300);
ALTER TABLE gk_gangwei ALTER COLUMN position_attr TYPE VARCHAR(200);
ALTER TABLE gk_gangwei ALTER COLUMN recruit_scope TYPE VARCHAR(300);
ALTER TABLE gk_gangwei ALTER COLUMN exam_category TYPE VARCHAR(200);
ALTER TABLE gk_gangwei ALTER COLUMN job_rank TYPE VARCHAR(200);

-- ========== 报考条件 ==========
ALTER TABLE gk_gangwei ALTER COLUMN education TYPE VARCHAR(200);
ALTER TABLE gk_gangwei ALTER COLUMN degree TYPE VARCHAR(200);
ALTER TABLE gk_gangwei ALTER COLUMN edu_type TYPE VARCHAR(200);
ALTER TABLE gk_gangwei ALTER COLUMN politics TYPE VARCHAR(200);
ALTER TABLE gk_gangwei ALTER COLUMN age_requirement TYPE VARCHAR(500);
ALTER TABLE gk_gangwei ALTER COLUMN ethnicity_requirement TYPE VARCHAR(500);
ALTER TABLE gk_gangwei ALTER COLUMN grassroots_years TYPE VARCHAR(500);
ALTER TABLE gk_gangwei ALTER COLUMN grassroots_project TYPE VARCHAR(300);
ALTER TABLE gk_gangwei ALTER COLUMN special_position TYPE VARCHAR(300);

-- ========== 地点信息 ==========
ALTER TABLE gk_gangwei ALTER COLUMN region TYPE VARCHAR(200);
ALTER TABLE gk_gangwei ALTER COLUMN work_location TYPE VARCHAR(300);
ALTER TABLE gk_gangwei ALTER COLUMN settlement_location TYPE VARCHAR(300);

-- ========== 面试相关 ==========
ALTER TABLE gk_gangwei ALTER COLUMN interview_ratio TYPE VARCHAR(100);
ALTER TABLE gk_gangwei ALTER COLUMN has_professional_test TYPE VARCHAR(100);

-- ========== 联系方式 ==========
ALTER TABLE gk_gangwei ALTER COLUMN phone1 TYPE VARCHAR(200);
ALTER TABLE gk_gangwei ALTER COLUMN phone2 TYPE VARCHAR(200);
ALTER TABLE gk_gangwei ALTER COLUMN phone3 TYPE VARCHAR(200);

-- ========== 统计字段 ==========
ALTER TABLE gk_gangwei ALTER COLUMN exam_type TYPE VARCHAR(100);
ALTER TABLE gk_gangwei ALTER COLUMN competition_ratio TYPE VARCHAR(100);

COMMIT;
