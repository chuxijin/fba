-- phpMyAdmin SQL Dump
-- version 5.1.1
-- https://www.phpmyadmin.net/
--
-- 主机： localhost
-- 生成日期： 2025-06-27 11:33:03
-- 服务器版本： 5.7.44-log
-- PHP 版本： 7.4.33

SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
START TRANSACTION;
SET time_zone = "+00:00";


/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8mb4 */;

--
-- 数据库： `fba`
--

-- --------------------------------------------------------

--
-- 表的结构 `sys_menu`
--

CREATE TABLE `sys_menu` (
  `id` int(11) NOT NULL COMMENT '主键 ID',
  `title` varchar(50) NOT NULL COMMENT '菜单标题',
  `name` varchar(50) NOT NULL COMMENT '菜单名称',
  `path` varchar(200) DEFAULT NULL COMMENT '路由地址',
  `sort` int(11) NOT NULL COMMENT '排序',
  `icon` varchar(100) DEFAULT NULL COMMENT '菜单图标',
  `type` int(11) NOT NULL COMMENT '菜单类型（0目录 1菜单 2按钮 3内嵌 4外链）',
  `component` varchar(255) DEFAULT NULL COMMENT '组件路径',
  `perms` varchar(100) DEFAULT NULL COMMENT '权限标识',
  `status` int(11) NOT NULL COMMENT '菜单状态（0停用 1正常）',
  `display` int(11) NOT NULL COMMENT '是否显示（0否 1是）',
  `cache` int(11) NOT NULL COMMENT '是否缓存（0否 1是）',
  `link` longtext COMMENT '外链地址',
  `remark` longtext COMMENT '备注',
  `parent_id` int(11) DEFAULT NULL COMMENT '父菜单ID',
  `created_time` datetime NOT NULL COMMENT '创建时间',
  `updated_time` datetime DEFAULT NULL COMMENT '更新时间'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='菜单表';

--
-- 转存表中的数据 `sys_menu`
--

INSERT INTO `sys_menu` (`id`, `title`, `name`, `path`, `sort`, `icon`, `type`, `component`, `perms`, `status`, `display`, `cache`, `link`, `remark`, `parent_id`, `created_time`, `updated_time`) VALUES
(1, '概览', 'Dashboard', 'dashboard', 0, 'ant-design:dashboard-outlined', 0, NULL, NULL, 1, 1, 1, '', NULL, NULL, '2025-06-09 17:26:18', NULL),
(2, '系统管理', 'System', 'system', 1, 'eos-icons:admin', 0, NULL, NULL, 1, 1, 1, '', NULL, NULL, '2025-06-09 17:30:01', NULL),
(3, '系统自动化', 'Automation', 'automation', 3, 'material-symbols:automation', 0, NULL, NULL, 1, 1, 1, '', NULL, NULL, '2025-06-09 17:31:41', '2025-06-13 10:02:50'),
(4, '日志管理', 'Log', 'log', 3, 'carbon:cloud-logging', 0, NULL, NULL, 1, 1, 1, '', NULL, NULL, '2025-06-09 17:32:34', NULL),
(5, '系统监控', 'Monitor', 'monitor', 4, 'mdi:monitor-eye', 0, NULL, NULL, 1, 1, 1, '', NULL, NULL, '2025-06-09 17:33:29', NULL),
(6, '项目', 'Project', 'fba', 5, 'https://wu-clan.github.io/picx-images-hosting/logo/fba.png', 0, NULL, NULL, 1, 1, 1, '', NULL, NULL, '2025-06-09 17:35:41', NULL),
(7, '分析页', 'Analytics', 'analytics', 0, 'lucide:area-chart', 1, '/dashboard/analytics/index', NULL, 1, 1, 1, '', NULL, 1, '2025-06-09 17:54:29', NULL),
(8, '工作台', 'Workspace', 'workspace', 1, 'carbon:workspace', 1, '/dashboard/workspace/index', NULL, 1, 1, 1, '', NULL, 1, '2025-06-09 17:57:09', NULL),
(9, '文档', 'Document', NULL, 1, 'lucide:book-open-text', 4, NULL, NULL, 1, 1, 1, 'https://fastapi-practices.github.io/fastapi_best_architecture_docs', NULL, 6, '2025-06-09 17:59:44', NULL),
(10, 'Github', 'Github', NULL, 2, 'ant-design:github-filled', 4, NULL, NULL, 1, 1, 1, 'https://github.com/fastapi-practices/fastapi_best_architecture', NULL, 6, '2025-06-09 18:00:50', NULL),
(11, 'Apifox', 'Apifox', 'apifox', 3, 'simple-icons:apifox', 3, NULL, NULL, 1, 1, 1, 'https://apifox.com/apidoc/shared-28a93f02-730b-4f33-bb5e-4dad92058cc0', NULL, 6, '2025-06-09 18:01:39', NULL),
(12, '部门管理', 'SysDept', 'sys-dept', 1, 'mingcute:department-line', 1, '/system/dept/index', NULL, 1, 1, 1, '', NULL, 2, '2025-06-09 18:03:17', NULL),
(13, '用户管理', 'SysUser', 'sys-user', 2, 'ant-design:user-outlined', 1, '/system/user/index', NULL, 1, 1, 1, '', NULL, 2, '2025-06-09 18:03:54', NULL),
(14, '角色管理', 'SysRole', 'sys-role', 3, 'carbon:user-role', 1, '/system/role/index', NULL, 1, 1, 1, '', NULL, 2, '2025-06-09 18:04:47', NULL),
(15, '菜单管理', 'SysMenu', 'sys-menu', 4, 'ant-design:menu-outlined', 1, '/system/menu/index', NULL, 1, 1, 1, '', NULL, 2, '2025-06-09 18:05:31', NULL),
(16, '数据权限', 'SysDataPermission', 'sys-data-permission', 5, 'icon-park-outline:permissions', 0, NULL, NULL, 1, 1, 1, '', NULL, 2, '2025-06-09 18:07:04', NULL),
(17, '数据范围', 'SysDataScope', 'sys-data-scope', 6, 'cuida:scope-outline', 1, '/system/data-permission/scope/index', NULL, 1, 1, 1, '', NULL, 16, '2025-06-09 18:07:46', NULL),
(18, '数据规则', 'SysDataRule', 'sys-data-rule', 7, 'material-symbols:rule', 1, '/system/data-permission/rule/index', NULL, 1, 1, 1, '', NULL, 16, '2025-06-09 18:08:22', NULL),
(19, '插件管理', 'SysPlugin', 'sys-plugin', 8, 'clarity:plugin-line', 1, '/system/plugin/index', NULL, 1, 1, 1, '', NULL, 2, '2025-06-09 18:09:12', NULL),
(20, '参数管理', 'SysConfig', 'sys-config', 9, 'codicon:symbol-parameter', 1, '/system/config/index', NULL, 1, 1, 1, '', NULL, 2, '2025-06-09 18:10:20', NULL),
(21, '字典管理', 'SysDict', 'sys-dict', 10, 'fluent-mdl2:dictionary', 1, '/system/dict/index', NULL, 1, 1, 1, '', NULL, 2, '2025-06-09 18:11:10', NULL),
(22, '通知公告', 'SysNotice', 'sys-notice', 11, 'fe:notice-push', 1, '/system/notice/index', NULL, 1, 1, 1, '', NULL, 2, '2025-06-09 18:11:38', NULL),
(23, '代码生成', 'CodeGenerator', 'code-generator', 1, 'tabler:code', 1, '/automation/code-generator/index', NULL, 1, 1, 1, '', NULL, 3, '2025-06-09 18:12:38', NULL),
(24, '任务调度', 'Scheduler', 'scheduler', 2, 'ix:scheduler', 1, '/automation/scheduler/index', NULL, 1, 1, 1, '', NULL, 3, '2025-06-09 18:13:19', NULL),
(25, '登录日志', 'LoginLog', 'login', 1, 'mdi:login', 1, '/log/login/index', NULL, 1, 1, 1, '', NULL, 4, '2025-06-09 18:14:35', NULL),
(26, '操作日志', 'OperaLog', 'opera', 2, 'carbon:operations-record', 1, '/log/opera/index', NULL, 1, 1, 1, '', NULL, 4, '2025-06-09 18:15:26', NULL),
(27, '在线用户', 'Online', 'online', 1, 'wpf:online', 1, '/monitor/online/index', NULL, 1, 1, 1, '', NULL, 5, '2025-06-09 18:17:12', NULL),
(28, 'Redis', 'Redis', 'redis', 2, 'devicon:redis', 1, '/monitor/redis/index', NULL, 1, 1, 1, '', NULL, 5, '2025-06-09 18:17:42', NULL),
(29, 'Server', 'Server', 'server', 3, 'mdi:server-outline', 1, '/monitor/server/index', NULL, 1, 1, 1, '', NULL, 5, '2025-06-09 18:18:12', NULL),
(30, '新增', 'AddSysDept', NULL, 0, NULL, 2, NULL, 'sys:dept:add', 1, 0, 1, '', NULL, 12, '2025-06-09 18:21:17', NULL),
(31, '修改', 'EditSysDept', NULL, 0, NULL, 2, NULL, 'sys:dept:edit', 1, 0, 1, '', NULL, 12, '2025-06-09 18:22:01', NULL),
(32, '删除', 'DeleteSysDept', NULL, 0, NULL, 2, NULL, 'sys:dept:del', 1, 0, 1, '', NULL, 12, '2025-06-09 18:22:39', NULL),
(33, '删除', 'DeleteSysUser', NULL, 0, NULL, 2, NULL, 'sys:user:del', 1, 0, 1, '', NULL, 13, '2025-06-09 18:24:09', NULL),
(34, '新增', 'AddSysRole', NULL, 0, NULL, 2, NULL, 'sys:role:add', 1, 0, 1, '', NULL, 14, '2025-06-09 18:25:08', NULL),
(35, '修改', 'EditSysRole', NULL, 0, NULL, 2, NULL, 'sys:role:edit', 1, 0, 1, '', NULL, 14, '2025-06-09 18:26:30', NULL),
(36, '修改角色菜单', 'EditSysRoleMenu', NULL, 0, NULL, 2, NULL, 'sys:role:menu:edit', 1, 0, 1, '', NULL, 14, '2025-06-09 18:27:24', NULL),
(37, '修改角色数据范围', 'EditSysRoleScope', NULL, 0, NULL, 2, NULL, 'sys:role:scope:edit', 1, 0, 1, '', NULL, 14, '2025-06-09 18:28:25', NULL),
(38, '删除', 'DeleteSysRole', NULL, 0, NULL, 2, NULL, 'sys:role:del', 1, 0, 1, '', NULL, 14, '2025-06-09 18:28:55', NULL),
(39, '新增', 'AddSysMenu', NULL, 0, NULL, 2, NULL, 'sys:menu:add', 1, 0, 1, '', NULL, 15, '2025-06-09 18:29:51', NULL),
(40, '修改', 'EditSysMenu', NULL, 0, NULL, 2, NULL, 'sys:menu:edit', 1, 0, 1, '', NULL, 15, '2025-06-09 18:30:13', NULL),
(41, '删除', 'DeleteSysMenu', NULL, 0, NULL, 2, NULL, 'sys:menu:del', 1, 0, 1, '', NULL, 15, '2025-06-09 18:30:37', NULL),
(42, '新增', 'AddSysDataScope', NULL, 0, NULL, 2, NULL, 'data:scope:add', 1, 0, 1, '', NULL, 17, '2025-06-09 18:31:11', NULL),
(43, '修改', 'EditSysDataScope', NULL, 0, NULL, 2, NULL, 'data:scope:edit', 1, 0, 1, '', NULL, 17, '2025-06-09 18:31:42', NULL),
(44, '修改数据范围规则', 'EditDataScopeRule', NULL, 0, NULL, 2, NULL, 'data:scope:rule:edit', 1, 0, 1, '', NULL, 17, '2025-06-09 18:32:36', NULL),
(45, '删除', 'DeleteSysDataScope', NULL, 0, NULL, 2, NULL, 'data:scope:del', 1, 0, 1, '', NULL, 17, '2025-06-09 18:33:09', NULL),
(46, '新增', 'AddSysDataRule', NULL, 0, NULL, 2, NULL, 'data:rule:add', 1, 0, 1, '', NULL, 18, '2025-06-09 18:35:54', NULL),
(47, '修改', 'EditSysDataRule', NULL, 0, NULL, 2, NULL, 'data:rule:edit', 1, 0, 1, '', NULL, 18, '2025-06-09 18:36:19', NULL),
(48, '删除', 'DeleteSysDataRule', NULL, 0, NULL, 2, NULL, 'data:rule:del', 1, 0, 1, '', NULL, 18, '2025-06-09 18:36:44', NULL),
(49, '安装zip插件', 'InstallZipSysPlugin', NULL, 0, NULL, 2, NULL, 'sys:plugin:zip', 1, 0, 1, '', NULL, 19, '2025-06-09 18:38:14', NULL),
(50, '安装git插件', 'InstallGitSysPlugin', NULL, 0, NULL, 2, NULL, 'sys:plugin:git', 1, 0, 1, '', NULL, 19, '2025-06-09 18:38:43', NULL),
(51, '卸载', 'UninstallSysPlugin', NULL, 0, NULL, 2, NULL, 'sys:plugin:del', 1, 0, 1, '', NULL, 19, '2025-06-09 18:39:08', NULL),
(52, '修改', 'EditSysPlugin', NULL, 0, NULL, 2, NULL, 'sys:plugin:status', 1, 0, 1, '', NULL, 19, '2025-06-09 18:39:47', NULL),
(53, '新增网站参数', 'AddWebsiteSysConfig', NULL, 0, NULL, 2, NULL, 'sys:config:website:add', 1, 0, 1, '', NULL, 20, '2025-06-09 18:43:30', NULL),
(54, '新增用户协议', 'AddProtocolSysConfig', NULL, 0, NULL, 2, NULL, 'sys:config:protocol:add', 1, 0, 1, '', NULL, 20, '2025-06-09 18:44:13', NULL),
(55, '新增用户政策', 'AddPolicySysConfig', NULL, 0, NULL, 2, NULL, 'sys:config:policy:add', 1, 0, 1, '', NULL, 20, '2025-06-09 18:45:28', NULL),
(56, '新增', 'AddSysConfig', NULL, 0, NULL, 2, NULL, 'sys:config:add', 1, 0, 1, '', NULL, 20, '2025-06-09 18:45:52', NULL),
(57, '修改', 'EditSysConfig', NULL, 0, NULL, 2, NULL, 'sys:config:edit', 1, 0, 1, '', NULL, 20, '2025-06-09 18:46:13', NULL),
(58, '删除', 'DeleteSysConfig', NULL, 0, NULL, 2, NULL, 'sys:config:del', 1, 0, 1, '', NULL, 20, '2025-06-09 18:46:36', NULL),
(59, '新增类型', 'AddSysDictType', NULL, 0, NULL, 2, NULL, 'sys:dict:type:add', 1, 0, 1, '', NULL, 21, '2025-06-09 18:48:17', NULL),
(60, '修改类型', 'EditSysDictType', NULL, 0, NULL, 2, NULL, 'sys:dict:type:edit', 1, 0, 1, '', NULL, 21, '2025-06-09 18:48:49', NULL),
(61, '删除类型', 'DeleteSysDictType', NULL, 0, NULL, 2, NULL, 'sys:dict:type:del', 1, 0, 1, '', NULL, 21, '2025-06-09 18:49:23', NULL),
(62, '新增', 'AddSysDictData', NULL, 0, NULL, 2, NULL, 'sys:dict:data:add', 1, 0, 1, '', NULL, 21, '2025-06-09 18:50:01', NULL),
(63, '修改', 'EditSysDictData', NULL, 0, NULL, 2, NULL, 'sys:dict:data:edit', 1, 0, 1, '', NULL, 21, '2025-06-09 18:50:26', NULL),
(64, '删除', 'DeleteSysDictData', NULL, 0, NULL, 2, NULL, 'sys:dict:data:del', 1, 0, 1, '', NULL, 21, '2025-06-09 18:50:48', NULL),
(65, '新增', 'AddSysNotice', NULL, 0, NULL, 2, NULL, 'sys:notice:add', 1, 0, 1, '', NULL, 22, '2025-06-09 18:51:22', NULL),
(66, '修改', 'EditSysNotice', NULL, 0, NULL, 2, NULL, 'sys:notice:edit', 1, 0, 1, '', NULL, 22, '2025-06-09 18:51:45', NULL),
(67, '删除', 'DeleteSysNotice', NULL, 0, NULL, 2, NULL, 'sys:notice:del', 1, 0, 1, '', NULL, 22, '2025-06-09 18:52:10', NULL),
(68, '新增业务', 'AddSysGenCodeBusiness', NULL, 0, NULL, 2, NULL, 'gen:code:business:add', 1, 0, 1, '', NULL, 23, '2025-06-09 18:53:07', NULL),
(69, '修改业务', 'EditGenCodeBusiness', NULL, 0, NULL, 2, NULL, 'gen:code:business:edit', 1, 0, 1, '', NULL, 23, '2025-06-09 18:53:45', NULL),
(70, '删除业务', 'DeleteGenCodeBusiness', NULL, 0, NULL, 2, NULL, 'gen:code:business:del', 1, 0, 1, '', NULL, 23, '2025-06-09 18:54:11', NULL),
(71, '新增模型', 'AddGenCodeModel', NULL, 0, NULL, 2, NULL, 'gen:code:model:add', 1, 0, 1, '', NULL, 23, '2025-06-09 18:54:45', NULL),
(72, '修改模型', 'EditGenCodeModel', NULL, 0, NULL, 2, NULL, 'gen:code:model:edit', 1, 0, 1, '', NULL, 23, '2025-06-09 18:55:08', NULL),
(73, '删除模型', 'DeleteGenCodeModel', NULL, 0, NULL, 2, NULL, 'gen:code:model:del', 1, 0, 1, '', NULL, 23, '2025-06-09 18:55:35', NULL),
(74, '导入', 'ImportGenCode', NULL, 0, NULL, 2, NULL, 'gen:code:import', 1, 0, 1, '', NULL, 23, '2025-06-09 18:58:16', NULL),
(75, '写入', 'WriteGenCode', NULL, 0, NULL, 2, NULL, 'gen:code:write', 1, 0, 1, '', NULL, 23, '2025-06-09 19:01:22', NULL),
(76, '删除', 'DeleteSysLoginLog', NULL, 0, NULL, 2, NULL, 'log:login:del', 1, 0, 1, '', NULL, 25, '2025-06-09 19:02:21', NULL),
(77, '清空', 'EmptyLoginLog', NULL, 0, NULL, 2, NULL, 'log:login:empty', 1, 0, 1, '', NULL, 25, '2025-06-09 19:02:50', NULL),
(78, '删除', 'DeleteOperaLog', NULL, 0, NULL, 2, NULL, 'log:opera:del', 1, 0, 1, '', NULL, 26, '2025-06-09 19:03:13', NULL),
(79, '清空', 'EmptyOperaLog', NULL, 0, NULL, 2, NULL, 'log:opera:empty', 1, 0, 1, '', NULL, 26, '2025-06-09 19:03:40', NULL),
(80, '下线', 'KickSysToken', NULL, 0, NULL, 2, NULL, 'sys:token:kick', 1, 0, 1, '', NULL, 27, '2025-06-09 19:04:52', NULL),
(81, '云盘管理', 'Coulddrive', 'coulddrive', 2, 'mdi:cloud-sync', 0, NULL, NULL, 1, 1, 1, '', '云盘管理主菜单', NULL, '2025-06-13 09:58:03', '2025-06-13 10:02:37'),
(82, '概览', 'CoulddriveOverview', 'overview', 0, 'mdi:view-dashboard', 1, '/coulddrive/overview/index', NULL, 1, 1, 1, NULL, '云盘概览', 81, '2025-06-13 09:58:03', NULL),
(83, '文件管理', 'CoulddriveFileManager', 'file-manager', 1, 'mdi:folder-multiple', 1, '/coulddrive/file-manager/index', NULL, 1, 1, 1, NULL, '云盘文件管理', 81, '2025-06-13 09:58:03', NULL),
(84, '用户管理', 'CoulddriveUserManager', 'user-manager', 2, 'mdi:account-group', 1, '/coulddrive/user-manager/index', NULL, 1, 1, 1, NULL, '云盘用户管理', 81, '2025-06-13 09:58:03', NULL),
(85, '同步任务', 'CoulddriveSyncManager', 'sync-manager', 3, 'mdi:sync', 1, '/coulddrive/sync-manager/index', NULL, 1, 1, 1, NULL, '云盘同步任务', 81, '2025-06-13 09:58:03', NULL),
(86, '规则模板', 'CoulddriveTemplateManager', 'template-manager', 4, 'mdi:file-document-multiple', 1, '/coulddrive/template-manager/index', NULL, 1, 1, 1, NULL, '云盘规则模板', 81, '2025-06-13 09:58:03', NULL),
(87, '资源管理', 'CoulddriveResourceManager', 'resource-manager', 5, 'mdi:database', 1, '/coulddrive/resource-manager/index', NULL, 1, 1, 1, NULL, '云盘资源管理', 81, '2025-06-13 09:58:03', NULL),
(88, '应用授权管理', 'AppAuth', '/app-auth', 100, 'lucide:shield-check', 0, NULL, NULL, 1, 1, 1, NULL, '应用授权管理模块', NULL, '2025-06-13 13:32:16', NULL),
(89, '应用管理', 'AppAuthApplication', '/app-auth/application', 1, 'lucide:app-window', 1, '/app-auth/application/index', 'app_auth:application:list', 1, 1, 1, NULL, '应用信息管理', 88, '2025-06-13 13:32:16', NULL),
(90, '设备管理', 'AppAuthDevice', '/app-auth/device', 2, 'lucide:smartphone', 1, '/app-auth/device/index', 'app_auth:device:list', 1, 1, 1, NULL, '设备信息管理', 88, '2025-06-13 13:32:16', NULL),
(91, '套餐管理', 'AppAuthPackage', '/app-auth/package', 3, 'lucide:package', 1, '/app-auth/package/index', 'app_auth:package:list', 1, 1, 1, NULL, '套餐信息管理', 88, '2025-06-13 13:32:16', NULL),
(92, '兑换码管理', 'AppAuthRedeemCode', '/app-auth/redeem-code', 4, 'lucide:ticket', 1, '/app-auth/redeem-code/index', 'app_auth:redeem_code:list', 1, 1, 1, NULL, '兑换码管理', 88, '2025-06-13 13:32:16', NULL),
(93, '版本管理', 'AppAuthVersion', '/app-auth/version', 5, 'lucide:git-branch', 1, '/app-auth/version/index', 'app_auth:version:list', 1, 1, 1, NULL, '应用版本管理', 88, '2025-06-13 13:32:16', NULL),
(94, '订单管理', 'AppAuthOrder', '/app-auth/order', 6, 'lucide:shopping-cart', 1, '/app-auth/order/index', 'app_auth:order:list', 1, 1, 1, NULL, '订单信息管理', 88, '2025-06-13 13:32:16', NULL),
(95, '授权概览', 'AppAuthAuthorization', '/app-auth/authorization', 0, 'lucide:key', 1, '/app-auth/authorization/index', 'app_auth:authorization:list', 1, 1, 1, '', '概览', 88, '2025-06-13 13:32:16', '2025-06-13 16:37:25'),
(96, '新增应用', 'AppAuthApplicationAdd', NULL, 1, NULL, 2, NULL, 'app_auth:application:add', 1, 0, 1, NULL, '新增应用权限', 89, '2025-06-13 13:32:16', NULL),
(97, '编辑应用', 'AppAuthApplicationEdit', NULL, 2, NULL, 2, NULL, 'app_auth:application:edit', 1, 0, 1, NULL, '编辑应用权限', 89, '2025-06-13 13:32:16', NULL),
(98, '删除应用', 'AppAuthApplicationDelete', NULL, 3, NULL, 2, NULL, 'app_auth:application:delete', 1, 0, 1, NULL, '删除应用权限', 89, '2025-06-13 13:32:16', NULL),
(99, '新增设备', 'AppAuthDeviceAdd', NULL, 1, NULL, 2, NULL, 'app_auth:device:add', 1, 0, 1, NULL, '新增设备权限', 90, '2025-06-13 13:32:16', NULL),
(100, '编辑设备', 'AppAuthDeviceEdit', NULL, 2, NULL, 2, NULL, 'app_auth:device:edit', 1, 0, 1, NULL, '编辑设备权限', 90, '2025-06-13 13:32:16', NULL),
(101, '删除设备', 'AppAuthDeviceDelete', NULL, 3, NULL, 2, NULL, 'app_auth:device:delete', 1, 0, 1, NULL, '删除设备权限', 90, '2025-06-13 13:32:16', NULL),
(102, '新增套餐', 'AppAuthPackageAdd', NULL, 1, NULL, 2, NULL, 'app_auth:package:add', 1, 0, 1, NULL, '新增套餐权限', 91, '2025-06-13 13:32:16', NULL),
(103, '编辑套餐', 'AppAuthPackageEdit', NULL, 2, NULL, 2, NULL, 'app_auth:package:edit', 1, 0, 1, NULL, '编辑套餐权限', 91, '2025-06-13 13:32:16', NULL),
(104, '删除套餐', 'AppAuthPackageDelete', NULL, 3, NULL, 2, NULL, 'app_auth:package:delete', 1, 0, 1, NULL, '删除套餐权限', 91, '2025-06-13 13:32:16', NULL),
(105, '生成兑换码', 'AppAuthRedeemCodeGenerate', NULL, 1, NULL, 2, NULL, 'app_auth:redeem_code:generate', 1, 0, 1, NULL, '生成兑换码权限', 92, '2025-06-13 13:32:16', NULL),
(106, '删除兑换码', 'AppAuthRedeemCodeDelete', NULL, 2, NULL, 2, NULL, 'app_auth:redeem_code:delete', 1, 0, 1, NULL, '删除兑换码权限', 92, '2025-06-13 13:32:16', NULL),
(107, '新增版本', 'AppAuthVersionAdd', NULL, 1, NULL, 2, NULL, 'app_auth:version:add', 1, 0, 1, NULL, '新增版本权限', 93, '2025-06-13 13:32:16', NULL),
(108, '编辑版本', 'AppAuthVersionEdit', NULL, 2, NULL, 2, NULL, 'app_auth:version:edit', 1, 0, 1, NULL, '编辑版本权限', 93, '2025-06-13 13:32:16', NULL),
(109, '删除版本', 'AppAuthVersionDelete', NULL, 3, NULL, 2, NULL, 'app_auth:version:delete', 1, 0, 1, NULL, '删除版本权限', 93, '2025-06-13 13:32:16', NULL),
(110, '新增订单', 'AppAuthOrderAdd', NULL, 1, NULL, 2, NULL, 'app_auth:order:add', 1, 0, 1, NULL, '新增订单权限', 94, '2025-06-13 13:32:16', NULL),
(111, '编辑订单', 'AppAuthOrderEdit', NULL, 2, NULL, 2, NULL, 'app_auth:order:edit', 1, 0, 1, NULL, '编辑订单权限', 94, '2025-06-13 13:32:16', NULL),
(112, '删除订单', 'AppAuthOrderDelete', NULL, 3, NULL, 2, NULL, 'app_auth:order:delete', 1, 0, 1, NULL, '删除订单权限', 94, '2025-06-13 13:32:16', NULL),
(113, '手动授权', 'AppAuthAuthorizationManual', NULL, 1, NULL, 2, NULL, 'app_auth:authorization:manual', 1, 0, 1, NULL, '手动授权权限', 95, '2025-06-13 13:32:16', NULL),
(114, '兑换码授权', 'AppAuthAuthorizationRedeem', NULL, 2, NULL, 2, NULL, 'app_auth:authorization:redeem', 1, 0, 1, NULL, '兑换码授权权限', 95, '2025-06-13 13:32:16', NULL),
(115, '删除授权', 'AppAuthAuthorizationDelete', NULL, 3, NULL, 2, NULL, 'app_auth:authorization:delete', 1, 0, 1, NULL, '删除授权权限', 95, '2025-06-13 13:32:16', NULL);

--
-- 转储表的索引
--

--
-- 表的索引 `sys_menu`
--
ALTER TABLE `sys_menu`
  ADD PRIMARY KEY (`id`),
  ADD KEY `ix_sys_menu_parent_id` (`parent_id`),
  ADD KEY `ix_sys_menu_id` (`id`);

--
-- 在导出的表使用AUTO_INCREMENT
--

--
-- 使用表AUTO_INCREMENT `sys_menu`
--
ALTER TABLE `sys_menu`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT COMMENT '主键 ID', AUTO_INCREMENT=122;

-- 添加 Webhook 管理菜单
INSERT INTO `sys_menu` (`id`, `title`, `name`, `path`, `sort`, `icon`, `type`, `component`, `perms`, `status`, `display`, `cache`, `link`, `remark`, `parent_id`, `created_time`, `updated_time`) VALUES
(116, 'Webhook管理', 'SysWebhook', 'sys-webhook', 12, 'mdi:webhook', 1, '/system/webhook/index', NULL, 1, 1, 1, '', 'Webhook事件管理', 2, '2025-07-04 13:15:00', NULL),
(117, '新增', 'AddSysWebhook', NULL, 1, NULL, 2, NULL, 'sys:webhook:add', 1, 0, 1, '', '新增Webhook配置', 116, '2025-07-04 13:15:00', NULL),
(118, '编辑', 'EditSysWebhook', NULL, 2, NULL, 2, NULL, 'sys:webhook:edit', 1, 0, 1, '', '编辑Webhook配置', 116, '2025-07-04 13:15:00', NULL),
(119, '删除', 'DeleteSysWebhook', NULL, 3, NULL, 2, NULL, 'sys:webhook:del', 1, 0, 1, '', '删除Webhook事件', 116, '2025-07-04 13:15:00', NULL),
(120, '重试', 'RetrySysWebhook', NULL, 4, NULL, 2, NULL, 'sys:webhook:retry', 1, 0, 1, '', '重试失败的Webhook事件', 116, '2025-07-04 13:15:00', NULL),
(121, '测试', 'TestSysWebhook', NULL, 5, NULL, 2, NULL, 'sys:webhook:test', 1, 0, 1, '', '测试Webhook配置', 116, '2025-07-04 13:15:00', NULL);

--
-- 限制导出的表
--

--
-- 限制表 `sys_menu`
--
ALTER TABLE `sys_menu`
  ADD CONSTRAINT `sys_menu_ibfk_1` FOREIGN KEY (`parent_id`) REFERENCES `sys_menu` (`id`) ON DELETE SET NULL;
COMMIT;

/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
