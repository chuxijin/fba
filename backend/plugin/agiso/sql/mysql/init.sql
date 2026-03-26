-- 阿奇索推送日志表
CREATE TABLE IF NOT EXISTS `agiso_push_log` (
    `id` INT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '主键ID',
    `push_type` VARCHAR(50) NOT NULL COMMENT '推送类型(payment:支付推送 delivery:发卡推送)',
    `order_no` VARCHAR(100) NOT NULL COMMENT '订单编号',
    `platform` VARCHAR(50) DEFAULT NULL COMMENT '来源平台',
    `push_data` TEXT NOT NULL COMMENT '推送原始数据',
    `process_status` INT NOT NULL DEFAULT 0 COMMENT '处理状态(0:待处理 1:处理成功 2:处理失败)',
    `process_result` TEXT DEFAULT NULL COMMENT '处理结果',
    `error_message` TEXT DEFAULT NULL COMMENT '错误信息',
    `retry_count` INT NOT NULL DEFAULT 0 COMMENT '重试次数',
    `created_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `processed_time` DATETIME DEFAULT NULL COMMENT '处理时间',
    PRIMARY KEY (`id`),
    INDEX `idx_order_no` (`order_no`),
    INDEX `idx_push_type` (`push_type`),
    INDEX `idx_process_status` (`process_status`),
    INDEX `idx_created_time` (`created_time`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='阿奇索推送日志表';
