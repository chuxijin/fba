-- Webhook 插件菜单清理 (MySQL Snowflake)

DELETE FROM `sys_menu` WHERE `name` = 'PluginWebhook';
DELETE FROM `sys_menu` WHERE `name` IN (
    'PluginWebhookEndpoint', 'PluginWebhookDelivery', 'PluginWebhookInbound', 'PluginWebhookEventType'
);
DELETE FROM `sys_menu` WHERE `name` IN (
    'WebhookEndpointAdd', 'WebhookEndpointEdit', 'WebhookEndpointDelete', 'WebhookEndpointRotate', 'WebhookEndpointTest',
    'WebhookDeliveryRetry', 'WebhookDeliveryProcess',
    'WebhookEventTypeAdd', 'WebhookEventTypeEdit', 'WebhookEventTypeDelete'
);

-- Webhook 数据表清理
DROP TABLE IF EXISTS `webhook_delivery`;
DROP TABLE IF EXISTS `webhook_event_log`;
DROP TABLE IF EXISTS `webhook_event_type`;
DROP TABLE IF EXISTS `webhook_endpoint`;
