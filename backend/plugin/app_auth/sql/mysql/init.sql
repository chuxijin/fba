-- 应用授权管理插件数据表创建SQL
-- 注意：请根据实际数据库类型调整字段类型

-- 1. 应用表
CREATE TABLE `app_application` (
    `id` int NOT NULL AUTO_INCREMENT COMMENT '主键 ID',
    `name` varchar(100) NOT NULL COMMENT '应用名称',
    `app_key` varchar(50) NOT NULL COMMENT '应用标识',
    `description` text COMMENT '应用描述',
    `icon` varchar(255) DEFAULT NULL COMMENT '应用图标',
    `status` tinyint NOT NULL DEFAULT 1 COMMENT '状态（0停用 1启用）',
    `is_free` tinyint NOT NULL DEFAULT 0 COMMENT '是否免费（0否 1是）',
    `created_time` datetime(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) COMMENT '创建时间',
    `updated_time` datetime(6) DEFAULT NULL ON UPDATE CURRENT_TIMESTAMP(6) COMMENT '更新时间',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_app_key` (`app_key`),
    UNIQUE KEY `uk_name` (`name`),
    KEY `idx_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='应用表';

-- 2. 设备表
CREATE TABLE `app_device` (
    `id` int NOT NULL AUTO_INCREMENT COMMENT '主键 ID',
    `device_id` varchar(100) NOT NULL COMMENT '设备标识',
    `device_name` varchar(100) DEFAULT NULL COMMENT '设备名称',
    `device_type` varchar(50) DEFAULT NULL COMMENT '设备类型',
    `os_info` varchar(200) DEFAULT NULL COMMENT '操作系统信息',
    `ip_address` varchar(45) DEFAULT NULL COMMENT 'IP地址',
    `status` tinyint NOT NULL DEFAULT 1 COMMENT '状态（0停用 1启用）',
    `last_seen` datetime(6) DEFAULT NULL COMMENT '最后活跃时间',
    `created_time` datetime(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) COMMENT '创建时间',
    `updated_time` datetime(6) DEFAULT NULL ON UPDATE CURRENT_TIMESTAMP(6) COMMENT '更新时间',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_device_id` (`device_id`),
    KEY `idx_device_name` (`device_name`),
    KEY `idx_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='设备表';

-- 3. 套餐表
CREATE TABLE `app_package` (
    `id` int NOT NULL AUTO_INCREMENT COMMENT '主键 ID',
    `application_id` int NOT NULL COMMENT '应用ID',
    `name` varchar(100) NOT NULL COMMENT '套餐名称',
    `description` text COMMENT '套餐描述',
    `original_price` decimal(10,2) NOT NULL COMMENT '原价',
    `duration_days` int NOT NULL COMMENT '有效期（天）',
    `discount_rate` decimal(3,2) DEFAULT NULL COMMENT '折扣率（0.1-1.0）',
    `discount_start_time` datetime(6) DEFAULT NULL COMMENT '折扣开始时间',
    `discount_end_time` datetime(6) DEFAULT NULL COMMENT '折扣结束时间',
    `is_active` tinyint NOT NULL DEFAULT 1 COMMENT '是否启用',
    `created_time` datetime(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) COMMENT '创建时间',
    `updated_time` datetime(6) DEFAULT NULL ON UPDATE CURRENT_TIMESTAMP(6) COMMENT '更新时间',
    PRIMARY KEY (`id`),
    KEY `idx_application_id` (`application_id`),
    KEY `idx_name` (`name`),
    KEY `idx_is_active` (`is_active`),
    CONSTRAINT `fk_package_application` FOREIGN KEY (`application_id`) REFERENCES `app_application` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='套餐表';

-- 4. 兑换码表
CREATE TABLE `app_redeem_code` (
    `id` int NOT NULL AUTO_INCREMENT COMMENT '主键 ID',
    `application_id` int NOT NULL COMMENT '应用ID',
    `package_id` int NOT NULL COMMENT '套餐ID',
    `code` varchar(50) NOT NULL COMMENT '兑换码',
    `batch_no` varchar(50) NOT NULL COMMENT '批次号',
    `is_used` tinyint NOT NULL DEFAULT 0 COMMENT '是否已使用',
    `used_by_device_id` int DEFAULT NULL COMMENT '使用设备ID',
    `used_time` datetime(6) DEFAULT NULL COMMENT '使用时间',
    `expires_at` datetime(6) DEFAULT NULL COMMENT '过期时间',
    `created_time` datetime(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) COMMENT '创建时间',
    `updated_time` datetime(6) DEFAULT NULL ON UPDATE CURRENT_TIMESTAMP(6) COMMENT '更新时间',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_code` (`code`),
    KEY `idx_application_id` (`application_id`),
    KEY `idx_package_id` (`package_id`),
    KEY `idx_batch_no` (`batch_no`),
    KEY `idx_is_used` (`is_used`),
    KEY `idx_used_by_device_id` (`used_by_device_id`),
    CONSTRAINT `fk_redeem_application` FOREIGN KEY (`application_id`) REFERENCES `app_application` (`id`) ON DELETE CASCADE,
    CONSTRAINT `fk_redeem_package` FOREIGN KEY (`package_id`) REFERENCES `app_package` (`id`) ON DELETE CASCADE,
    CONSTRAINT `fk_redeem_device` FOREIGN KEY (`used_by_device_id`) REFERENCES `app_device` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='兑换码表';

-- 5. 版本表
CREATE TABLE `app_version` (
    `id` int NOT NULL AUTO_INCREMENT COMMENT '主键 ID',
    `application_id` int NOT NULL COMMENT '应用ID',
    `version_number` varchar(20) NOT NULL COMMENT '版本号',
    `version_name` varchar(100) NOT NULL COMMENT '版本名称',
    `version_code` int NOT NULL COMMENT '版本代码',
    `description` text COMMENT '版本描述',
    `download_url` varchar(500) DEFAULT NULL COMMENT '下载地址',
    `is_latest` tinyint NOT NULL DEFAULT 0 COMMENT '是否最新版本',
    `is_active` tinyint NOT NULL DEFAULT 1 COMMENT '是否启用',
    `created_time` datetime(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) COMMENT '创建时间',
    `updated_time` datetime(6) DEFAULT NULL ON UPDATE CURRENT_TIMESTAMP(6) COMMENT '更新时间',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_app_version_code` (`application_id`, `version_code`),
    KEY `idx_application_id` (`application_id`),
    KEY `idx_version_number` (`version_number`),
    KEY `idx_is_latest` (`is_latest`),
    KEY `idx_is_active` (`is_active`),
    CONSTRAINT `fk_version_application` FOREIGN KEY (`application_id`) REFERENCES `app_application` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='版本表';

-- 6. 订单表
CREATE TABLE `app_order` (
    `id` int NOT NULL AUTO_INCREMENT COMMENT '主键 ID',
    `order_no` varchar(50) NOT NULL COMMENT '订单号',
    `package_id` int NOT NULL COMMENT '套餐ID',
    `device_id` int NOT NULL COMMENT '设备ID',
    `amount` decimal(10,2) NOT NULL COMMENT '订单金额',
    `status` tinyint NOT NULL DEFAULT 0 COMMENT '订单状态（0待支付 1已支付 2已取消 3已退款）',
    `payment_method` varchar(20) DEFAULT NULL COMMENT '支付方式',
    `payment_time` datetime(6) DEFAULT NULL COMMENT '支付时间',
    `created_time` datetime(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) COMMENT '创建时间',
    `updated_time` datetime(6) DEFAULT NULL ON UPDATE CURRENT_TIMESTAMP(6) COMMENT '更新时间',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_order_no` (`order_no`),
    KEY `idx_package_id` (`package_id`),
    KEY `idx_device_id` (`device_id`),
    KEY `idx_status` (`status`),
    CONSTRAINT `fk_order_package` FOREIGN KEY (`package_id`) REFERENCES `app_package` (`id`) ON DELETE CASCADE,
    CONSTRAINT `fk_order_device` FOREIGN KEY (`device_id`) REFERENCES `app_device` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='订单表';

-- 7. 授权表
CREATE TABLE `app_authorization` (
    `id` int NOT NULL AUTO_INCREMENT COMMENT '主键 ID',
    `application_id` int NOT NULL COMMENT '应用ID',
    `device_id` int NOT NULL COMMENT '设备ID',
    `package_id` int DEFAULT NULL COMMENT '套餐ID',
    `order_id` int DEFAULT NULL COMMENT '订单ID',
    `redeem_code_id` int DEFAULT NULL COMMENT '兑换码ID',
    `auth_type` tinyint NOT NULL COMMENT '授权类型（1手动授权 2购买套餐 3兑换码）',
    `start_time` datetime(6) NOT NULL COMMENT '授权开始时间',
    `end_time` datetime(6) NOT NULL COMMENT '授权结束时间',
    `is_active` tinyint NOT NULL DEFAULT 1 COMMENT '是否有效',
    `created_time` datetime(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) COMMENT '创建时间',
    `updated_time` datetime(6) DEFAULT NULL ON UPDATE CURRENT_TIMESTAMP(6) COMMENT '更新时间',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_app_device` (`application_id`, `device_id`),
    KEY `idx_device_id` (`device_id`),
    KEY `idx_package_id` (`package_id`),
    KEY `idx_order_id` (`order_id`),
    KEY `idx_redeem_code_id` (`redeem_code_id`),
    KEY `idx_auth_type` (`auth_type`),
    KEY `idx_is_active` (`is_active`),
    CONSTRAINT `fk_auth_application` FOREIGN KEY (`application_id`) REFERENCES `app_application` (`id`) ON DELETE CASCADE,
    CONSTRAINT `fk_auth_device` FOREIGN KEY (`device_id`) REFERENCES `app_device` (`id`) ON DELETE CASCADE,
    CONSTRAINT `fk_auth_package` FOREIGN KEY (`package_id`) REFERENCES `app_package` (`id`) ON DELETE SET NULL,
    CONSTRAINT `fk_auth_order` FOREIGN KEY (`order_id`) REFERENCES `app_order` (`id`) ON DELETE SET NULL,
    CONSTRAINT `fk_auth_redeem_code` FOREIGN KEY (`redeem_code_id`) REFERENCES `app_redeem_code` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='授权表'; 