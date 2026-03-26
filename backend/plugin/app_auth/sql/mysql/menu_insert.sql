-- 应用授权管理插件菜单插入SQL
-- 注意：请根据实际的菜单ID情况调整起始ID值

-- 1. 应用授权管理 (一级菜单 - 目录)
INSERT INTO `sys_menu` (`title`, `name`, `path`, `sort`, `icon`, `type`, `component`, `perms`, `status`, `display`, `cache`, `link`, `remark`, `parent_id`, `created_time`) 
VALUES ('应用授权管理', 'AppAuth', '/app-auth', 100, 'lucide:shield-check', 0, NULL, NULL, 1, 1, 1, NULL, '应用授权管理模块', NULL, NOW());

-- 获取刚插入的一级菜单ID (假设为 @parent_id)
SET @parent_id = LAST_INSERT_ID();

-- 2. 应用管理 (二级菜单)
INSERT INTO `sys_menu` (`title`, `name`, `path`, `sort`, `icon`, `type`, `component`, `perms`, `status`, `display`, `cache`, `link`, `remark`, `parent_id`, `created_time`) 
VALUES ('应用管理', 'AppAuthApplication', '/app-auth/application', 1, 'lucide:app-window', 1, '/app-auth/application/index', 'app_auth:application:list', 1, 1, 1, NULL, '应用信息管理', @parent_id, NOW());

-- 3. 设备管理 (二级菜单)
INSERT INTO `sys_menu` (`title`, `name`, `path`, `sort`, `icon`, `type`, `component`, `perms`, `status`, `display`, `cache`, `link`, `remark`, `parent_id`, `created_time`) 
VALUES ('设备管理', 'AppAuthDevice', '/app-auth/device', 2, 'lucide:smartphone', 1, '/app-auth/device/index', 'app_auth:device:list', 1, 1, 1, NULL, '设备信息管理', @parent_id, NOW());

-- 4. 套餐管理 (二级菜单)
INSERT INTO `sys_menu` (`title`, `name`, `path`, `sort`, `icon`, `type`, `component`, `perms`, `status`, `display`, `cache`, `link`, `remark`, `parent_id`, `created_time`) 
VALUES ('套餐管理', 'AppAuthPackage', '/app-auth/package', 3, 'lucide:package', 1, '/app-auth/package/index', 'app_auth:package:list', 1, 1, 1, NULL, '套餐信息管理', @parent_id, NOW());

-- 5. 兑换码管理 (二级菜单)
INSERT INTO `sys_menu` (`title`, `name`, `path`, `sort`, `icon`, `type`, `component`, `perms`, `status`, `display`, `cache`, `link`, `remark`, `parent_id`, `created_time`) 
VALUES ('兑换码管理', 'AppAuthRedeemCode', '/app-auth/redeem-code', 4, 'lucide:ticket', 1, '/app-auth/redeem-code/index', 'app_auth:redeem_code:list', 1, 1, 1, NULL, '兑换码管理', @parent_id, NOW());

-- 6. 版本管理 (二级菜单)
INSERT INTO `sys_menu` (`title`, `name`, `path`, `sort`, `icon`, `type`, `component`, `perms`, `status`, `display`, `cache`, `link`, `remark`, `parent_id`, `created_time`) 
VALUES ('版本管理', 'AppAuthVersion', '/app-auth/version', 5, 'lucide:git-branch', 1, '/app-auth/version/index', 'app_auth:version:list', 1, 1, 1, NULL, '应用版本管理', @parent_id, NOW());

-- 7. 订单管理 (二级菜单)
INSERT INTO `sys_menu` (`title`, `name`, `path`, `sort`, `icon`, `type`, `component`, `perms`, `status`, `display`, `cache`, `link`, `remark`, `parent_id`, `created_time`) 
VALUES ('订单管理', 'AppAuthOrder', '/app-auth/order', 6, 'lucide:shopping-cart', 1, '/app-auth/order/index', 'app_auth:order:list', 1, 1, 1, NULL, '订单信息管理', @parent_id, NOW());

-- 8. 授权管理 (二级菜单)
INSERT INTO `sys_menu` (`title`, `name`, `path`, `sort`, `icon`, `type`, `component`, `perms`, `status`, `display`, `cache`, `link`, `remark`, `parent_id`, `created_time`) 
VALUES ('授权管理', 'AppAuthAuthorization', '/app-auth/authorization', 7, 'lucide:key', 1, '/app-auth/authorization/index', 'app_auth:authorization:list', 1, 1, 1, NULL, '设备授权管理', @parent_id, NOW());

-- 按钮权限 (三级菜单 - 按钮类型)
-- 应用管理按钮权限
SET @app_menu_id = (SELECT id FROM sys_menu WHERE name = 'AppAuthApplication');

INSERT INTO `sys_menu` (`title`, `name`, `path`, `sort`, `icon`, `type`, `component`, `perms`, `status`, `display`, `cache`, `link`, `remark`, `parent_id`, `created_time`) VALUES
('新增应用', 'AppAuthApplicationAdd', NULL, 1, NULL, 2, NULL, 'app_auth:application:add', 1, 0, 1, NULL, '新增应用权限', @app_menu_id, NOW()),
('编辑应用', 'AppAuthApplicationEdit', NULL, 2, NULL, 2, NULL, 'app_auth:application:edit', 1, 0, 1, NULL, '编辑应用权限', @app_menu_id, NOW()),
('删除应用', 'AppAuthApplicationDelete', NULL, 3, NULL, 2, NULL, 'app_auth:application:delete', 1, 0, 1, NULL, '删除应用权限', @app_menu_id, NOW());

-- 设备管理按钮权限
SET @device_menu_id = (SELECT id FROM sys_menu WHERE name = 'AppAuthDevice');

INSERT INTO `sys_menu` (`title`, `name`, `path`, `sort`, `icon`, `type`, `component`, `perms`, `status`, `display`, `cache`, `link`, `remark`, `parent_id`, `created_time`) VALUES
('新增设备', 'AppAuthDeviceAdd', NULL, 1, NULL, 2, NULL, 'app_auth:device:add', 1, 0, 1, NULL, '新增设备权限', @device_menu_id, NOW()),
('编辑设备', 'AppAuthDeviceEdit', NULL, 2, NULL, 2, NULL, 'app_auth:device:edit', 1, 0, 1, NULL, '编辑设备权限', @device_menu_id, NOW()),
('删除设备', 'AppAuthDeviceDelete', NULL, 3, NULL, 2, NULL, 'app_auth:device:delete', 1, 0, 1, NULL, '删除设备权限', @device_menu_id, NOW());

-- 套餐管理按钮权限
SET @package_menu_id = (SELECT id FROM sys_menu WHERE name = 'AppAuthPackage');

INSERT INTO `sys_menu` (`title`, `name`, `path`, `sort`, `icon`, `type`, `component`, `perms`, `status`, `display`, `cache`, `link`, `remark`, `parent_id`, `created_time`) VALUES
('新增套餐', 'AppAuthPackageAdd', NULL, 1, NULL, 2, NULL, 'app_auth:package:add', 1, 0, 1, NULL, '新增套餐权限', @package_menu_id, NOW()),
('编辑套餐', 'AppAuthPackageEdit', NULL, 2, NULL, 2, NULL, 'app_auth:package:edit', 1, 0, 1, NULL, '编辑套餐权限', @package_menu_id, NOW()),
('删除套餐', 'AppAuthPackageDelete', NULL, 3, NULL, 2, NULL, 'app_auth:package:delete', 1, 0, 1, NULL, '删除套餐权限', @package_menu_id, NOW());

-- 兑换码管理按钮权限
SET @redeem_menu_id = (SELECT id FROM sys_menu WHERE name = 'AppAuthRedeemCode');

INSERT INTO `sys_menu` (`title`, `name`, `path`, `sort`, `icon`, `type`, `component`, `perms`, `status`, `display`, `cache`, `link`, `remark`, `parent_id`, `created_time`) VALUES
('生成兑换码', 'AppAuthRedeemCodeGenerate', NULL, 1, NULL, 2, NULL, 'app_auth:redeem_code:generate', 1, 0, 1, NULL, '生成兑换码权限', @redeem_menu_id, NOW()),
('删除兑换码', 'AppAuthRedeemCodeDelete', NULL, 2, NULL, 2, NULL, 'app_auth:redeem_code:delete', 1, 0, 1, NULL, '删除兑换码权限', @redeem_menu_id, NOW());

-- 版本管理按钮权限
SET @version_menu_id = (SELECT id FROM sys_menu WHERE name = 'AppAuthVersion');

INSERT INTO `sys_menu` (`title`, `name`, `path`, `sort`, `icon`, `type`, `component`, `perms`, `status`, `display`, `cache`, `link`, `remark`, `parent_id`, `created_time`) VALUES
('新增版本', 'AppAuthVersionAdd', NULL, 1, NULL, 2, NULL, 'app_auth:version:add', 1, 0, 1, NULL, '新增版本权限', @version_menu_id, NOW()),
('编辑版本', 'AppAuthVersionEdit', NULL, 2, NULL, 2, NULL, 'app_auth:version:edit', 1, 0, 1, NULL, '编辑版本权限', @version_menu_id, NOW()),
('删除版本', 'AppAuthVersionDelete', NULL, 3, NULL, 2, NULL, 'app_auth:version:delete', 1, 0, 1, NULL, '删除版本权限', @version_menu_id, NOW());

-- 订单管理按钮权限
SET @order_menu_id = (SELECT id FROM sys_menu WHERE name = 'AppAuthOrder');

INSERT INTO `sys_menu` (`title`, `name`, `path`, `sort`, `icon`, `type`, `component`, `perms`, `status`, `display`, `cache`, `link`, `remark`, `parent_id`, `created_time`) VALUES
('新增订单', 'AppAuthOrderAdd', NULL, 1, NULL, 2, NULL, 'app_auth:order:add', 1, 0, 1, NULL, '新增订单权限', @order_menu_id, NOW()),
('编辑订单', 'AppAuthOrderEdit', NULL, 2, NULL, 2, NULL, 'app_auth:order:edit', 1, 0, 1, NULL, '编辑订单权限', @order_menu_id, NOW()),
('删除订单', 'AppAuthOrderDelete', NULL, 3, NULL, 2, NULL, 'app_auth:order:delete', 1, 0, 1, NULL, '删除订单权限', @order_menu_id, NOW());

-- 授权管理按钮权限
SET @auth_menu_id = (SELECT id FROM sys_menu WHERE name = 'AppAuthAuthorization');

INSERT INTO `sys_menu` (`title`, `name`, `path`, `sort`, `icon`, `type`, `component`, `perms`, `status`, `display`, `cache`, `link`, `remark`, `parent_id`, `created_time`) VALUES
('手动授权', 'AppAuthAuthorizationManual', NULL, 1, NULL, 2, NULL, 'app_auth:authorization:manual', 1, 0, 1, NULL, '手动授权权限', @auth_menu_id, NOW()),
('兑换码授权', 'AppAuthAuthorizationRedeem', NULL, 2, NULL, 2, NULL, 'app_auth:authorization:redeem', 1, 0, 1, NULL, '兑换码授权权限', @auth_menu_id, NOW()),
('删除授权', 'AppAuthAuthorizationDelete', NULL, 3, NULL, 2, NULL, 'app_auth:authorization:delete', 1, 0, 1, NULL, '删除授权权限', @auth_menu_id, NOW()); 