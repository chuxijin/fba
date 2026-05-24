-- Webhook 插件菜单初始化 (MySQL Snowflake ID)

-- 1. 一级目录
INSERT INTO `sys_menu` (
    `id`, `title`, `name`, `path`, `sort`, `icon`, `type`, `component`,
    `perms`, `status`, `display`, `cache`, `link`, `remark`, `parent_id`, `created_time`
) VALUES (
    2049629108257816600, 'webhook.menu', 'PluginWebhook', '/plugins/webhook', 50, 'mdi:webhook', 0, NULL,
    NULL, 1, 1, 1, NULL, 'Webhook 事件管理模块', NULL, NULL, NOW()
);

-- 2. 二级菜单页面
INSERT INTO `sys_menu` (
    `id`, `title`, `name`, `path`, `sort`, `icon`, `type`, `component`,
    `perms`, `status`, `display`, `cache`, `link`, `remark`, `parent_id`, `created_time`
) VALUES
(2049629108257816601, 'webhook.endpoint', 'PluginWebhookEndpoint', '/plugins/webhook/endpoints', 1, 'mdi:webhook', 1,
 '/plugins/webhook/views/endpoint', 'webhook:endpoint:list', 1, 1, 1, NULL, '出站端点管理', 2049629108257816600, NOW()),
(2049629108257816602, 'webhook.delivery', 'PluginWebhookDelivery', '/plugins/webhook/deliveries', 2, 'mdi:send-clock', 1,
 '/plugins/webhook/views/delivery', 'webhook:delivery:list', 1, 1, 1, NULL, '投递记录查看', 2049629108257816600, NOW()),
(2049629108257816603, 'webhook.inbound', 'PluginWebhookInbound', '/plugins/webhook/inbound', 3, 'mdi:inbox-arrow-down', 1,
 '/plugins/webhook/views/inbound', 'webhook:inbound:list', 1, 1, 1, NULL, '入站事件日志', 2049629108257816600, NOW()),
(2049629108257816604, 'webhook.eventType', 'PluginWebhookEventType', '/plugins/webhook/event-types', 4, 'mdi:tag-multiple', 1,
 '/plugins/webhook/views/event-type', 'webhook:event_type:list', 1, 1, 1, NULL, '事件类型注册', 2049629108257816600, NOW());

-- 3. 出站端点 - 按钮权限
INSERT INTO `sys_menu` (
    `id`, `title`, `name`, `path`, `sort`, `icon`, `type`, `component`,
    `perms`, `status`, `display`, `cache`, `link`, `remark`, `parent_id`, `created_time`
) VALUES
(2049629108257816611, '新增端点', 'WebhookEndpointAdd', NULL, 1, NULL, 2, NULL, 'webhook:endpoint:add', 1, 0, 1, NULL, '新增端点权限', 2049629108257816601, NOW()),
(2049629108257816612, '编辑端点', 'WebhookEndpointEdit', NULL, 2, NULL, 2, NULL, 'webhook:endpoint:edit', 1, 0, 1, NULL, '编辑端点权限', 2049629108257816601, NOW()),
(2049629108257816613, '删除端点', 'WebhookEndpointDelete', NULL, 3, NULL, 2, NULL, 'webhook:endpoint:delete', 1, 0, 1, NULL, '删除端点权限', 2049629108257816601, NOW()),
(2049629108257816614, '轮换密钥', 'WebhookEndpointRotate', NULL, 4, NULL, 2, NULL, 'webhook:endpoint:rotate', 1, 0, 1, NULL, '轮换签名密钥权限', 2049629108257816601, NOW()),
(2049629108257816615, '测试推送', 'WebhookEndpointTest', NULL, 5, NULL, 2, NULL, 'webhook:endpoint:test', 1, 0, 1, NULL, '测试推送权限', 2049629108257816601, NOW());

-- 4. 投递记录 - 按钮权限
INSERT INTO `sys_menu` (
    `id`, `title`, `name`, `path`, `sort`, `icon`, `type`, `component`,
    `perms`, `status`, `display`, `cache`, `link`, `remark`, `parent_id`, `created_time`
) VALUES
(2049629108257816621, '重试投递', 'WebhookDeliveryRetry', NULL, 1, NULL, 2, NULL, 'webhook:delivery:retry', 1, 0, 1, NULL, '重试投递权限', 2049629108257816602, NOW()),
(2049629108257816622, '处理待发', 'WebhookDeliveryProcess', NULL, 2, NULL, 2, NULL, 'webhook:delivery:process', 1, 0, 1, NULL, '处理待发投递权限', 2049629108257816602, NOW());

-- 5. 事件类型 - 按钮权限
INSERT INTO `sys_menu` (
    `id`, `title`, `name`, `path`, `sort`, `icon`, `type`, `component`,
    `perms`, `status`, `display`, `cache`, `link`, `remark`, `parent_id`, `created_time`
) VALUES
(2049629108257816631, '新增事件类型', 'WebhookEventTypeAdd', NULL, 1, NULL, 2, NULL, 'webhook:event_type:add', 1, 0, 1, NULL, '新增事件类型权限', 2049629108257816604, NOW()),
(2049629108257816632, '编辑事件类型', 'WebhookEventTypeEdit', NULL, 2, NULL, 2, NULL, 'webhook:event_type:edit', 1, 0, 1, NULL, '编辑事件类型权限', 2049629108257816604, NOW()),
(2049629108257816633, '删除事件类型', 'WebhookEventTypeDelete', NULL, 3, NULL, 2, NULL, 'webhook:event_type:delete', 1, 0, 1, NULL, '删除事件类型权限', 2049629108257816604, NOW());
