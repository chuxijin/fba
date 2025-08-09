-- 创建Celery任务结果表
-- 这些表用于存储Celery任务的执行结果和状态

-- 创建task_result表
CREATE TABLE IF NOT EXISTS `task_result` (
    `id` int NOT NULL AUTO_INCREMENT,
    `task_id` varchar(255) NOT NULL,
    `status` varchar(50) NOT NULL,
    `result` longblob,
    `date_done` datetime(6) DEFAULT NULL,
    `traceback` longtext,
    `name` varchar(255) DEFAULT NULL,
    `args` longblob,
    `kwargs` longblob,
    `worker` varchar(100) DEFAULT NULL,
    `retries` int DEFAULT NULL,
    `queue` varchar(100) DEFAULT NULL,
    PRIMARY KEY (`id`),
    UNIQUE KEY `task_id` (`task_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='Celery任务结果表';

-- 创建task_group_result表
CREATE TABLE IF NOT EXISTS `task_group_result` (
    `id` int NOT NULL AUTO_INCREMENT,
    `group_id` varchar(255) NOT NULL,
    `result` longblob,
    `date_done` datetime(6) DEFAULT NULL,
    PRIMARY KEY (`id`),
    UNIQUE KEY `group_id` (`group_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='Celery任务组结果表'; 