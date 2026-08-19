-- SensitiveWord 内容安全 / 敏感词管理菜单与权限
-- 使用 910+ ID，执行前请确认目标环境未占用该区间。

insert into sys_menu (id, title, name, path, sort, icon, type, component, perms, status, display, cache, link, remark, parent_id, created_time, updated_time)
values
(910, '内容安全', 'SensitiveWord', '/sensitive-word', 16, 'lucide:shield-alert', 0, null, null, 1, 1, 1, '', '敏感词替换 / 屏蔽 / 拦截', null, now(), null)
on conflict (id) do nothing;

insert into sys_menu (id, title, name, path, sort, icon, type, component, perms, status, display, cache, link, remark, parent_id, created_time, updated_time)
values
(911, '敏感词管理', 'SensitiveWordIndex', '/sensitive-word/index', 1, 'lucide:list-checks', 1, '/sensitive-word/index', 'sensitive:word:read', 1, 1, 1, '', null, 910, now(), null),
(914, '命中日志', 'SensitiveWordLog', '/sensitive-word/log', 2, 'lucide:scroll-text', 1, '/sensitive-word/log/index', 'sensitive:hit:read', 1, 1, 1, '', null, 910, now(), null)
on conflict (id) do nothing;

insert into sys_menu (id, title, name, path, sort, icon, type, component, perms, status, display, cache, link, remark, parent_id, created_time, updated_time)
values
(912, '查看敏感词', 'SensitiveWordRead', null, 0, null, 2, null, 'sensitive:word:read', 1, 0, 1, '', null, 911, now(), null),
(913, '维护敏感词', 'SensitiveWordWrite', null, 0, null, 2, null, 'sensitive:word:write', 1, 0, 1, '', null, 911, now(), null),
(915, '查看命中日志', 'SensitiveHitRead', null, 0, null, 2, null, 'sensitive:hit:read', 1, 0, 1, '', null, 914, now(), null)
on conflict (id) do nothing;

select setval(
    pg_get_serial_sequence('sys_menu', 'id'),
    greatest((select coalesce(max(id), 1) from sys_menu), 915),
    true
);
