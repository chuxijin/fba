-- OC 求职工具平台 - 数据库初始化脚本 (MySQL + Snowflake ID)

-- 校招岗位表
CREATE TABLE IF NOT EXISTS `oc_campus_recruit` (
    `id` BIGINT PRIMARY KEY,
    `company_name` TEXT NOT NULL,
    `company_type` VARCHAR(64) NOT NULL,
    `industry` VARCHAR(128) NOT NULL,
    `recruitment_type` VARCHAR(64) NOT NULL,
    `recruit_target` VARCHAR(128) NOT NULL,
    `location` TEXT NOT NULL,
    `positions` TEXT NOT NULL,
    `update_time` DATE NOT NULL,
    `application_status` VARCHAR(32) DEFAULT '未投递',
    `company_size` VARCHAR(100),
    `deadline` VARCHAR(64),
    `apply_link` TEXT,
    `notice_link` TEXT,
    `referral_code` VARCHAR(64),
    `exam_info` VARCHAR(500),
    `remark` TEXT,
    `created_time` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `updated_time` DATETIME ON UPDATE CURRENT_TIMESTAMP,
    INDEX `idx_oc_campus_recruit_company_name` (`company_name`(100))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='校招岗位表';

-- 实习岗位表
CREATE TABLE IF NOT EXISTS `oc_intern_recruit` (
    `id` BIGINT PRIMARY KEY,
    `company_name` TEXT NOT NULL,
    `company_type` VARCHAR(64) NOT NULL,
    `industry` VARCHAR(128) NOT NULL,
    `recruitment_type` VARCHAR(64) NOT NULL,
    `recruit_target` VARCHAR(128) NOT NULL,
    `location` TEXT NOT NULL,
    `positions` TEXT NOT NULL,
    `update_time` DATE NOT NULL,
    `application_status` VARCHAR(32) DEFAULT '未投递',
    `deadline` VARCHAR(64),
    `apply_link` TEXT,
    `notice_link` TEXT,
    `referral_code` VARCHAR(64),
    `remark` TEXT,
    `created_time` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `updated_time` DATETIME ON UPDATE CURRENT_TIMESTAMP,
    INDEX `idx_oc_intern_recruit_company_name` (`company_name`(100))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='实习岗位表';

-- 用户投递记录表
CREATE TABLE IF NOT EXISTS `oc_user_application` (
    `id` BIGINT PRIMARY KEY,
    `user_id` BIGINT NOT NULL,
    `job_id` BIGINT NOT NULL,
    `job_type` VARCHAR(16) NOT NULL,
    `application_status` VARCHAR(32) DEFAULT '未投递',
    `applied_at` DATETIME,
    `remark` TEXT,
    `created_time` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `updated_time` DATETIME ON UPDATE CURRENT_TIMESTAMP,
    INDEX `idx_oc_user_application_user_id` (`user_id`),
    INDEX `idx_oc_user_application_job_id` (`job_id`),
    CONSTRAINT `fk_oc_user_application_user_id` FOREIGN KEY (`user_id`) REFERENCES `sys_user`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户投递记录表';

-- 笔面试资料包表
CREATE TABLE IF NOT EXISTS `oc_resource` (
    `id` BIGINT PRIMARY KEY,
    `title` VARCHAR(255) NOT NULL,
    `image` VARCHAR(500),
    `baidu_link` VARCHAR(500),
    `extract_code` VARCHAR(10),
    `created_time` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `updated_time` DATETIME ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='笔试面试资料包表';

-- 字段配置表
CREATE TABLE IF NOT EXISTS `oc_formatter_field` (
    `id` BIGINT PRIMARY KEY,
    `category` VARCHAR(50) NOT NULL,
    `field_name` VARCHAR(50) NOT NULL,
    `chinese` VARCHAR(100) NOT NULL,
    `strategy` VARCHAR(30) DEFAULT 'input',
    `level` SMALLINT DEFAULT 0,
    `field_order` SMALLINT DEFAULT 0,
    `tips` VARCHAR(500),
    `default_value` VARCHAR(200),
    `is_array` TINYINT(1) DEFAULT 0,
    `is_hidden` TINYINT(1) DEFAULT 0,
    `parent_field_id` BIGINT,
    `created_time` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `updated_time` DATETIME ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY `uq_formatter_field` (`category`, `field_name`, `parent_field_id`),
    INDEX `idx_oc_formatter_field_category` (`category`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='字段配置表';

-- 标签匹配规则表
CREATE TABLE IF NOT EXISTS `oc_formatter_embedding` (
    `id` BIGINT PRIMARY KEY,
    `field_id` BIGINT NOT NULL,
    `label` VARCHAR(200) NOT NULL,
    `value_script` TEXT,
    `share_data_list` VARCHAR(500),
    `created_time` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `updated_time` DATETIME ON UPDATE CURRENT_TIMESTAMP,
    INDEX `idx_oc_formatter_embedding_field_id` (`field_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='标签匹配规则表';

-- 下拉选项映射表
CREATE TABLE IF NOT EXISTS `oc_formatter_mapping` (
    `id` BIGINT PRIMARY KEY,
    `field_id` BIGINT NOT NULL,
    `source_value` VARCHAR(100) NOT NULL,
    `target_values` VARCHAR(500) NOT NULL,
    `created_time` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `updated_time` DATETIME ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY `uq_formatter_mapping` (`field_id`, `source_value`),
    INDEX `idx_oc_formatter_mapping_field_id` (`field_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='下拉选项映射表';

-- 内推码表
CREATE TABLE IF NOT EXISTS `oc_referral_code` (
    `id` BIGINT PRIMARY KEY,
    `company_name` VARCHAR(128) NOT NULL,
    `referral_code` VARCHAR(128) NOT NULL,
    `remark` TEXT,
    `created_by` BIGINT,
    `updated_by` BIGINT,
    `created_time` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `updated_time` DATETIME ON UPDATE CURRENT_TIMESTAMP,
    INDEX `idx_oc_referral_code_company_name` (`company_name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='内推码表';

-- 用户反馈表
CREATE TABLE IF NOT EXISTS `oc_feedback` (
    `id` BIGINT PRIMARY KEY,
    `type` VARCHAR(20) NOT NULL,
    `content` TEXT NOT NULL,
    `ip` VARCHAR(50),
    `user_agent` VARCHAR(500),
    `status` VARCHAR(20) DEFAULT 'pending',
    `created_by` BIGINT,
    `updated_by` BIGINT,
    `created_time` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `updated_time` DATETIME ON UPDATE CURRENT_TIMESTAMP,
    INDEX `idx_oc_feedback_created_by` (`created_by`),
    INDEX `idx_oc_feedback_type` (`type`),
    INDEX `idx_oc_feedback_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户反馈表';

-- 用户简历表
CREATE TABLE IF NOT EXISTS `oc_user_resume` (
    `id` BIGINT PRIMARY KEY,
    `user_id` BIGINT NOT NULL UNIQUE,
    `encrypted_data` TEXT NOT NULL,
    `data_hash` VARCHAR(64) NOT NULL,
    `created_time` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `updated_time` DATETIME ON UPDATE CURRENT_TIMESTAMP,
    INDEX `idx_oc_user_resume_user_id` (`user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户简历表';
