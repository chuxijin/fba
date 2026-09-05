DELETE FROM sys_menu WHERE name IN ('PluginWebAnalyticsOverview', 'PluginWebAnalyticsBehavior', 'PluginWebAnalyticsSites');
DELETE FROM sys_menu WHERE name = 'PluginWebAnalytics';
DROP TABLE IF EXISTS plugin_web_analytics_replay_chunk CASCADE;
DROP TABLE IF EXISTS plugin_web_analytics_replay_session CASCADE;
DROP TABLE IF EXISTS plugin_web_analytics_daily CASCADE;
DROP TABLE IF EXISTS plugin_web_analytics_event CASCADE;
DROP TABLE IF EXISTS plugin_web_analytics_session CASCADE;
DROP TABLE IF EXISTS plugin_web_analytics_site CASCADE;
