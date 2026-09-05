CREATE TABLE IF NOT EXISTS `plugin_web_analytics_site` (
 `id` BIGINT NOT NULL, `site_key` VARCHAR(32) NOT NULL, `name` VARCHAR(100) NOT NULL, `domains` JSON NOT NULL,
 `timezone` VARCHAR(64) NOT NULL DEFAULT 'Asia/Shanghai', `is_active` BOOLEAN NOT NULL DEFAULT TRUE,
 `is_public` BOOLEAN NOT NULL DEFAULT FALSE, `heatmap_enabled` BOOLEAN NOT NULL DEFAULT TRUE,
 `replay_enabled` BOOLEAN NOT NULL DEFAULT TRUE, `replay_sample_rate` DOUBLE NOT NULL DEFAULT 0.05,
 `event_retention_days` INT NOT NULL DEFAULT 180, `replay_retention_days` INT NOT NULL DEFAULT 30,
 `deleted` BIGINT NOT NULL DEFAULT 0, `deleted_time` DATETIME(6), `created_time` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
 `updated_time` DATETIME(6) NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6), PRIMARY KEY (`id`), UNIQUE KEY (`site_key`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS `plugin_web_analytics_session` (
 `id` BIGINT NOT NULL, `site_id` BIGINT NOT NULL, `session_key` VARCHAR(64) NOT NULL, `visitor_hash` VARCHAR(64) NOT NULL,
 `ip_hash` VARCHAR(64) NOT NULL, `started_at` DATETIME(6) NOT NULL, `last_seen_at` DATETIME(6) NOT NULL,
 `entry_path` VARCHAR(1024) NOT NULL, `exit_path` VARCHAR(1024) NOT NULL, `referrer` VARCHAR(2048), `referrer_host` VARCHAR(255),
 `utm_source` VARCHAR(255), `utm_medium` VARCHAR(255), `utm_campaign` VARCHAR(255), `country` VARCHAR(64), `region` VARCHAR(64), `city` VARCHAR(64),
 `browser` VARCHAR(128), `os` VARCHAR(128), `device` VARCHAR(128), `pageviews` INT NOT NULL DEFAULT 0,
 `event_count` INT NOT NULL DEFAULT 0, `duration_seconds` INT NOT NULL DEFAULT 0, `deleted` BIGINT NOT NULL DEFAULT 0,
 `deleted_time` DATETIME(6), `created_time` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
 `updated_time` DATETIME(6) NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6), PRIMARY KEY (`id`),
 UNIQUE KEY `uq_web_analytics_session_site_key` (`site_id`,`session_key`), KEY (`site_id`,`started_at`), KEY (`site_id`,`visitor_hash`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS `plugin_web_analytics_event` (
 `id` BIGINT NOT NULL, `site_id` BIGINT NOT NULL, `event_key` VARCHAR(64) NOT NULL, `session_key` VARCHAR(64) NOT NULL,
 `visitor_hash` VARCHAR(64) NOT NULL, `event_type` VARCHAR(32) NOT NULL, `path` VARCHAR(1024) NOT NULL,
 `occurred_at` DATETIME(6) NOT NULL, `received_at` DATETIME(6) NOT NULL, `event_name` VARCHAR(128), `title` VARCHAR(512),
 `referrer` VARCHAR(2048), `properties` JSON, `screen_width` INT, `screen_height` INT, `viewport_width` INT, `viewport_height` INT,
 `deleted` BIGINT NOT NULL DEFAULT 0, `deleted_time` DATETIME(6), `created_time` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
 `updated_time` DATETIME(6) NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6), PRIMARY KEY (`id`),
 UNIQUE KEY `uq_web_analytics_event_site_key` (`site_id`,`event_key`), KEY (`site_id`,`occurred_at`),
 KEY (`site_id`,`event_type`,`occurred_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS `plugin_web_analytics_daily` (
 `id` BIGINT NOT NULL, `site_id` BIGINT NOT NULL, `stats_date` DATE NOT NULL, `pv` INT NOT NULL DEFAULT 0,
 `uv` INT NOT NULL DEFAULT 0, `sessions` INT NOT NULL DEFAULT 0, `events` INT NOT NULL DEFAULT 0,
 `bounces` INT NOT NULL DEFAULT 0, `duration_seconds` INT NOT NULL DEFAULT 0, `deleted` BIGINT NOT NULL DEFAULT 0,
 `deleted_time` DATETIME(6), `created_time` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
 `updated_time` DATETIME(6) NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6), PRIMARY KEY (`id`), UNIQUE KEY (`site_id`,`stats_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS `plugin_web_analytics_replay_session` (
 `id` BIGINT NOT NULL, `site_id` BIGINT NOT NULL, `replay_key` VARCHAR(64) NOT NULL, `session_key` VARCHAR(64) NOT NULL,
 `visitor_hash` VARCHAR(64) NOT NULL, `path` VARCHAR(1024) NOT NULL, `started_at` DATETIME(6) NOT NULL,
 `last_event_at` DATETIME(6) NOT NULL, `chunk_count` INT NOT NULL DEFAULT 0, `total_bytes` INT NOT NULL DEFAULT 0,
 `deleted` BIGINT NOT NULL DEFAULT 0, `deleted_time` DATETIME(6), `created_time` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
 `updated_time` DATETIME(6) NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6), PRIMARY KEY (`id`),
 UNIQUE KEY (`site_id`,`replay_key`), KEY (`site_id`,`started_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS `plugin_web_analytics_replay_chunk` (
 `id` BIGINT NOT NULL, `site_id` BIGINT NOT NULL, `replay_key` VARCHAR(64) NOT NULL, `sequence` INT NOT NULL,
 `payload` LONGTEXT NOT NULL, `occurred_at` DATETIME(6) NOT NULL, `encoding` VARCHAR(16) NOT NULL DEFAULT 'json',
 `event_count` INT NOT NULL DEFAULT 0, `deleted` BIGINT NOT NULL DEFAULT 0, `deleted_time` DATETIME(6),
 `created_time` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
 `updated_time` DATETIME(6) NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6), PRIMARY KEY (`id`),
 UNIQUE KEY (`site_id`,`replay_key`,`sequence`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
INSERT INTO `sys_menu` (`id`, `title`, `name`, `path`, `sort`, `icon`, `type`, `component`, `perms`, `status`, `display`, `cache`, `link`, `remark`, `parent_id`, `created_time`)
SELECT 2071000000000000000, 'web_analytics.menu', 'PluginWebAnalytics', '/plugins/web-analytics', 45, 'carbon:analytics', 0, NULL, NULL, 1, 1, 1, NULL, '网站访问与行为统计', NULL, NOW()
WHERE NOT EXISTS (SELECT 1 FROM `sys_menu` WHERE `name` = 'PluginWebAnalytics');
INSERT INTO `sys_menu` (`id`, `title`, `name`, `path`, `sort`, `icon`, `type`, `component`, `perms`, `status`, `display`, `cache`, `link`, `remark`, `parent_id`, `created_time`)
SELECT 2071000000000000001, 'web_analytics.overview', 'PluginWebAnalyticsOverview', '/plugins/web-analytics', 1, 'carbon:chart-line-data', 1, '/plugins/web_analytics/views/overview', NULL, 1, 1, 1, NULL, '网站统计流量总览', 2071000000000000000, NOW()
WHERE NOT EXISTS (SELECT 1 FROM `sys_menu` WHERE `name` = 'PluginWebAnalyticsOverview');
INSERT INTO `sys_menu` (`id`, `title`, `name`, `path`, `sort`, `icon`, `type`, `component`, `perms`, `status`, `display`, `cache`, `link`, `remark`, `parent_id`, `created_time`)
SELECT 2071000000000000002, 'web_analytics.behavior', 'PluginWebAnalyticsBehavior', '/plugins/web-analytics/behavior', 2, 'carbon:heat-map', 1, '/plugins/web_analytics/views/behavior', NULL, 1, 1, 1, NULL, '热力图与会话回放', 2071000000000000000, NOW()
WHERE NOT EXISTS (SELECT 1 FROM `sys_menu` WHERE `name` = 'PluginWebAnalyticsBehavior');
INSERT INTO `sys_menu` (`id`, `title`, `name`, `path`, `sort`, `icon`, `type`, `component`, `perms`, `status`, `display`, `cache`, `link`, `remark`, `parent_id`, `created_time`)
SELECT 2071000000000000003, 'web_analytics.sites', 'PluginWebAnalyticsSites', '/plugins/web-analytics/sites', 3, 'carbon:web-services-container', 1, '/plugins/web_analytics/views/sites', NULL, 1, 1, 1, NULL, '统计站点配置', 2071000000000000000, NOW()
WHERE NOT EXISTS (SELECT 1 FROM `sys_menu` WHERE `name` = 'PluginWebAnalyticsSites');
