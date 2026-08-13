-- Learning 学习管理菜单与权限
-- 使用 800+ ID，执行前请确认目标环境未占用该区间。

insert into sys_menu (id, title, name, path, sort, icon, type, component, perms, status, display, cache, link, remark, parent_id, created_time, updated_time)
values
(800, '学习管理', 'Learning', '/learning', 11, 'mdi:book-clock-outline', 0, null, null, 1, 1, 1, '', '学习计划、任务与外部交付管理', null, now(), null)
on conflict (id) do nothing;

insert into sys_menu (id, title, name, path, sort, icon, type, component, perms, status, display, cache, link, remark, parent_id, created_time, updated_time)
values
(801, '计划管理', 'LearningPlan', '/learning/plans', 1, 'mdi:clipboard-text-clock-outline', 1, '/learning/plan/index', 'learning:plan:read', 1, 1, 1, '', null, 800, now(), null),
(802, '交付管理', 'LearningDelivery', '/learning/deliveries', 2, 'mdi:package-variant-closed-check', 1, '/learning/delivery/index', 'learning:delivery:read', 1, 1, 1, '', null, 800, now(), null)
on conflict (id) do nothing;

insert into sys_menu (id, title, name, path, sort, icon, type, component, perms, status, display, cache, link, remark, parent_id, created_time, updated_time)
values
(808, '计划模板', 'LearningTemplate', '/learning/templates', 1, 'mdi:clipboard-text-multiple-outline', 1, '/learning/template/index', 'learning:template:read', 1, 1, 1, '', '可复用的阶段、每日任务、知识点和完成指标模板', 800, now(), null)
on conflict (id) do nothing;

update sys_menu set sort = 2 where id = 801;
update sys_menu set sort = 3 where id = 802;

insert into sys_menu (id, title, name, path, sort, icon, type, component, perms, status, display, cache, link, remark, parent_id, created_time, updated_time)
values
(803, '查看计划', 'LearningPlanRead', null, 0, null, 2, null, 'learning:plan:read', 1, 0, 1, '', null, 801, now(), null),
(804, '维护计划', 'LearningPlanWrite', null, 0, null, 2, null, 'learning:plan:write', 1, 0, 1, '', null, 801, now(), null),
(805, '查看交付', 'LearningDeliveryRead', null, 0, null, 2, null, 'learning:delivery:read', 1, 0, 1, '', null, 802, now(), null),
(806, '维护交付', 'LearningDeliveryWrite', null, 0, null, 2, null, 'learning:delivery:write', 1, 0, 1, '', null, 802, now(), null),
(807, '发布交付', 'LearningDeliveryPublish', null, 0, null, 2, null, 'learning:delivery:publish', 1, 0, 1, '', null, 802, now(), null)
on conflict (id) do nothing;

insert into sys_menu (id, title, name, path, sort, icon, type, component, perms, status, display, cache, link, remark, parent_id, created_time, updated_time)
values
(809, '查看模板', 'LearningTemplateRead', null, 0, null, 2, null, 'learning:template:read', 1, 0, 1, '', null, 808, now(), null),
(810, '维护模板', 'LearningTemplateWrite', null, 0, null, 2, null, 'learning:template:write', 1, 0, 1, '', null, 808, now(), null)
on conflict (id) do nothing;

select setval(
    pg_get_serial_sequence('sys_menu', 'id'),
    greatest((select coalesce(max(id), 1) from sys_menu), 810),
    true
);
