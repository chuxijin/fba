DELETE FROM `sys_menu` WHERE `name` IN ('PluginWebAnalyticsOverview', 'PluginWebAnalyticsBehavior', 'PluginWebAnalyticsSites');
DELETE FROM `sys_menu` WHERE `name` = 'PluginWebAnalytics';
DROP TABLE IF EXISTS `plugin_web_analytics_replay_chunk`;
DROP TABLE IF EXISTS `plugin_web_analytics_replay_session`;
DROP TABLE IF EXISTS `plugin_web_analytics_daily`;
DROP TABLE IF EXISTS `plugin_web_analytics_event`;
DROP TABLE IF EXISTS `plugin_web_analytics_session`;
DROP TABLE IF EXISTS `plugin_web_analytics_site`;
