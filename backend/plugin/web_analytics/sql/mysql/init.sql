CREATE TABLE IF NOT EXISTS `plugin_web_analytics_site` (
  `id` BIGINT NOT NULL AUTO_INCREMENT, `site_key` VARCHAR(32) NOT NULL, `name` VARCHAR(100) NOT NULL,
  `domains` JSON NOT NULL, `timezone` VARCHAR(64) NOT NULL DEFAULT 'Asia/Shanghai',
  `is_active` BOOLEAN NOT NULL DEFAULT TRUE, `is_public` BOOLEAN NOT NULL DEFAULT FALSE,
  `heatmap_enabled` BOOLEAN NOT NULL DEFAULT TRUE, `replay_enabled` BOOLEAN NOT NULL DEFAULT TRUE,
  `replay_sample_rate` DOUBLE NOT NULL DEFAULT 0.05, `event_retention_days` INT NOT NULL DEFAULT 180,
  `replay_retention_days` INT NOT NULL DEFAULT 30, `deleted` BIGINT NOT NULL DEFAULT 0,
  `deleted_time` DATETIME(6) NULL, `created_time` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `updated_time` DATETIME(6) NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`), UNIQUE KEY `uq_web_analytics_site_key` (`site_key`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS `plugin_web_analytics_session` (
  `id` BIGINT NOT NULL AUTO_INCREMENT, `site_id` BIGINT NOT NULL, `session_key` VARCHAR(64) NOT NULL,
  `visitor_hash` VARCHAR(64) NOT NULL, `ip_hash` VARCHAR(64) NOT NULL, `started_at` DATETIME(6) NOT NULL,
  `last_seen_at` DATETIME(6) NOT NULL, `entry_path` VARCHAR(1024) NOT NULL, `exit_path` VARCHAR(1024) NOT NULL,
  `referrer` VARCHAR(2048) NULL, `referrer_host` VARCHAR(255) NULL, `utm_source` VARCHAR(255) NULL,
  `utm_medium` VARCHAR(255) NULL, `utm_campaign` VARCHAR(255) NULL, `country` VARCHAR(64) NULL,
  `region` VARCHAR(64) NULL, `city` VARCHAR(64) NULL, `browser` VARCHAR(128) NULL, `os` VARCHAR(128) NULL,
  `device` VARCHAR(128) NULL, `pageviews` INT NOT NULL DEFAULT 0, `event_count` INT NOT NULL DEFAULT 0,
  `duration_seconds` INT NOT NULL DEFAULT 0, `deleted` BIGINT NOT NULL DEFAULT 0, `deleted_time` DATETIME(6) NULL,
  `created_time` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `updated_time` DATETIME(6) NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`), UNIQUE KEY `uq_web_analytics_session_site_key` (`site_id`,`session_key`),
  KEY `ix_web_analytics_session_site_started` (`site_id`,`started_at`),
  KEY `ix_web_analytics_session_site_visitor` (`site_id`,`visitor_hash`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS `plugin_web_analytics_event` (
  `id` BIGINT NOT NULL AUTO_INCREMENT, `site_id` BIGINT NOT NULL, `event_key` VARCHAR(64) NOT NULL,
  `session_key` VARCHAR(64) NOT NULL, `visitor_hash` VARCHAR(64) NOT NULL, `event_type` VARCHAR(32) NOT NULL,
  `path` VARCHAR(1024) NOT NULL, `occurred_at` DATETIME(6) NOT NULL, `received_at` DATETIME(6) NOT NULL,
  `event_name` VARCHAR(128) NULL, `title` VARCHAR(512) NULL, `referrer` VARCHAR(2048) NULL,
  `properties` JSON NULL, `screen_width` INT NULL, `screen_height` INT NULL, `viewport_width` INT NULL,
  `viewport_height` INT NULL, `deleted` BIGINT NOT NULL DEFAULT 0, `deleted_time` DATETIME(6) NULL,
  `created_time` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `updated_time` DATETIME(6) NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`), UNIQUE KEY `uq_web_analytics_event_site_key` (`site_id`,`event_key`),
  KEY `ix_web_analytics_event_site_time` (`site_id`,`occurred_at`),
  KEY `ix_web_analytics_event_site_type_time` (`site_id`,`event_type`,`occurred_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS `plugin_web_analytics_daily` (
  `id` BIGINT NOT NULL AUTO_INCREMENT, `site_id` BIGINT NOT NULL, `stats_date` DATE NOT NULL,
  `pv` INT NOT NULL DEFAULT 0, `uv` INT NOT NULL DEFAULT 0, `sessions` INT NOT NULL DEFAULT 0,
  `events` INT NOT NULL DEFAULT 0, `bounces` INT NOT NULL DEFAULT 0, `duration_seconds` INT NOT NULL DEFAULT 0,
  `deleted` BIGINT NOT NULL DEFAULT 0, `deleted_time` DATETIME(6) NULL,
  `created_time` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `updated_time` DATETIME(6) NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`), UNIQUE KEY `uq_web_analytics_daily_site_date` (`site_id`,`stats_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS `plugin_web_analytics_replay_session` (
  `id` BIGINT NOT NULL AUTO_INCREMENT, `site_id` BIGINT NOT NULL, `replay_key` VARCHAR(64) NOT NULL,
  `session_key` VARCHAR(64) NOT NULL, `visitor_hash` VARCHAR(64) NOT NULL, `path` VARCHAR(1024) NOT NULL,
  `started_at` DATETIME(6) NOT NULL, `last_event_at` DATETIME(6) NOT NULL, `chunk_count` INT NOT NULL DEFAULT 0,
  `total_bytes` INT NOT NULL DEFAULT 0, `deleted` BIGINT NOT NULL DEFAULT 0, `deleted_time` DATETIME(6) NULL,
  `created_time` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `updated_time` DATETIME(6) NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`), UNIQUE KEY `uq_web_analytics_replay_site_key` (`site_id`,`replay_key`),
  KEY `ix_web_analytics_replay_site_started` (`site_id`,`started_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS `plugin_web_analytics_replay_chunk` (
  `id` BIGINT NOT NULL AUTO_INCREMENT, `site_id` BIGINT NOT NULL, `replay_key` VARCHAR(64) NOT NULL,
  `sequence` INT NOT NULL, `payload` LONGTEXT NOT NULL, `occurred_at` DATETIME(6) NOT NULL,
  `encoding` VARCHAR(16) NOT NULL DEFAULT 'json', `event_count` INT NOT NULL DEFAULT 0,
  `deleted` BIGINT NOT NULL DEFAULT 0, `deleted_time` DATETIME(6) NULL,
  `created_time` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `updated_time` DATETIME(6) NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`), UNIQUE KEY `uq_web_analytics_replay_chunk_sequence` (`site_id`,`replay_key`,`sequence`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

INSERT INTO `sys_menu` (`title`, `name`, `path`, `sort`, `icon`, `type`, `component`, `perms`, `status`, `display`, `cache`, `link`, `remark`, `parent_id`, `created_time`)
SELECT 'web_analytics.menu', 'PluginWebAnalytics', '/plugins/web-analytics', 45, 'carbon:analytics', 0, NULL, NULL, 1, 1, 1, NULL, '网站访问与行为统计', NULL, NOW()
WHERE NOT EXISTS (SELECT 1 FROM `sys_menu` WHERE `name` = 'PluginWebAnalytics');
SET @web_analytics_menu_id = (SELECT `id` FROM `sys_menu` WHERE `name` = 'PluginWebAnalytics' LIMIT 1);
INSERT INTO `sys_menu` (`title`, `name`, `path`, `sort`, `icon`, `type`, `component`, `perms`, `status`, `display`, `cache`, `link`, `remark`, `parent_id`, `created_time`)
SELECT 'web_analytics.overview', 'PluginWebAnalyticsOverview', '/plugins/web-analytics', 1, 'carbon:chart-line-data', 1, '/plugins/web_analytics/views/overview', NULL, 1, 1, 1, NULL, '网站统计流量总览', @web_analytics_menu_id, NOW()
WHERE NOT EXISTS (SELECT 1 FROM `sys_menu` WHERE `name` = 'PluginWebAnalyticsOverview');
INSERT INTO `sys_menu` (`title`, `name`, `path`, `sort`, `icon`, `type`, `component`, `perms`, `status`, `display`, `cache`, `link`, `remark`, `parent_id`, `created_time`)
SELECT 'web_analytics.behavior', 'PluginWebAnalyticsBehavior', '/plugins/web-analytics/behavior', 2, 'carbon:heat-map', 1, '/plugins/web_analytics/views/behavior', NULL, 1, 1, 1, NULL, '热力图与会话回放', @web_analytics_menu_id, NOW()
WHERE NOT EXISTS (SELECT 1 FROM `sys_menu` WHERE `name` = 'PluginWebAnalyticsBehavior');
INSERT INTO `sys_menu` (`title`, `name`, `path`, `sort`, `icon`, `type`, `component`, `perms`, `status`, `display`, `cache`, `link`, `remark`, `parent_id`, `created_time`)
SELECT 'web_analytics.sites', 'PluginWebAnalyticsSites', '/plugins/web-analytics/sites', 3, 'carbon:web-services-container', 1, '/plugins/web_analytics/views/sites', NULL, 1, 1, 1, NULL, '统计站点配置', @web_analytics_menu_id, NOW()
WHERE NOT EXISTS (SELECT 1 FROM `sys_menu` WHERE `name` = 'PluginWebAnalyticsSites');
