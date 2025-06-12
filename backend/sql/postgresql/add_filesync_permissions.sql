-- 添加文件同步任务相关权限 (PostgreSQL版本)

-- 首先添加主菜单（如果不存在）
INSERT INTO sys_menu (id, title, name, path, sort, icon, type, component, perms, status, display, cache, link, remark, parent_id, created_time, updated_time)
VALUES  (81, '文件同步', 'FileSyncTask', 'filesync-task', 3, 'mdi:sync', 1, '/automation/filesync-task/index', null, 1, 1, 1, '', '文件同步任务管理', 3, NOW(), null)
ON CONFLICT (id) DO UPDATE SET title = EXCLUDED.title;

-- 添加文件同步任务权限
INSERT INTO sys_menu (id, title, name, path, sort, icon, type, component, perms, status, display, cache, link, remark, parent_id, created_time, updated_time)
VALUES  
    (82, '检查定时任务', 'CheckFileSyncCronTask', null, 1, null, 2, null, 'sys:task:filesync:check', 1, 0, 1, '', '检查并执行文件同步定时任务', 81, NOW(), null),
    (83, '执行同步任务', 'ExecuteFileSyncTask', null, 2, null, 2, null, 'sys:task:filesync:execute', 1, 0, 1, '', '执行指定配置的文件同步任务', 81, NOW(), null),
    (84, '查看配置', 'ViewFileSyncConfig', null, 3, null, 2, null, 'sys:task:filesync:view', 1, 0, 1, '', '查看文件同步配置', 81, NOW(), null),
    (85, '管理配置', 'ManageFileSyncConfig', null, 4, null, 2, null, 'sys:task:filesync:manage', 1, 0, 1, '', '管理文件同步配置', 81, NOW(), null)
ON CONFLICT (id) DO UPDATE SET perms = EXCLUDED.perms;

-- 为超级管理员角色添加权限（假设角色ID为1）
INSERT INTO sys_role_menu (role_id, menu_id)
SELECT 1, id FROM sys_menu WHERE id IN (81, 82, 83, 84, 85)
AND NOT EXISTS (
    SELECT 1 FROM sys_role_menu 
    WHERE role_id = 1 AND menu_id = sys_menu.id
); 