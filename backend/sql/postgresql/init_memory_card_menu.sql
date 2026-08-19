-- MemoryCard 记忆卡管理菜单与权限
-- 使用 900+ ID，执行前请确认目标环境未占用该区间。

insert into sys_menu (id, title, name, path, sort, icon, type, component, perms, status, display, cache, link, remark, parent_id, created_time, updated_time)
values
(900, '记忆卡管理', 'MemoryCard', '/memory-card', 15, 'lucide:brain', 0, null, null, 1, 1, 1, '', '挖空背诵、纠错与记忆曲线卡组', null, now(), null)
on conflict (id) do nothing;

insert into sys_menu (id, title, name, path, sort, icon, type, component, perms, status, display, cache, link, remark, parent_id, created_time, updated_time)
values
(901, '卡组管理', 'MemoryCardDeck', '/memory-card/deck', 1, 'lucide:layers', 1, '/memory-card/deck/index', 'memory:deck:read', 1, 1, 1, '', null, 900, now(), null),
(902, '卡片管理', 'MemoryCardCard', '/memory-card/card', 2, 'lucide:square-stack', 1, '/memory-card/card/index', 'memory:card:read', 1, 1, 1, '', null, 900, now(), null)
on conflict (id) do nothing;

insert into sys_menu (id, title, name, path, sort, icon, type, component, perms, status, display, cache, link, remark, parent_id, created_time, updated_time)
values
(903, '查看卡组', 'MemoryCardDeckRead', null, 0, null, 2, null, 'memory:deck:read', 1, 0, 1, '', null, 901, now(), null),
(904, '维护卡组', 'MemoryCardDeckWrite', null, 0, null, 2, null, 'memory:deck:write', 1, 0, 1, '', null, 901, now(), null),
(905, '查看卡片', 'MemoryCardCardRead', null, 0, null, 2, null, 'memory:card:read', 1, 0, 1, '', null, 902, now(), null),
(906, '维护卡片', 'MemoryCardCardWrite', null, 0, null, 2, null, 'memory:card:write', 1, 0, 1, '', null, 902, now(), null)
on conflict (id) do nothing;

select setval(
    pg_get_serial_sequence('sys_menu', 'id'),
    greatest((select coalesce(max(id), 1) from sys_menu), 906),
    true
);
