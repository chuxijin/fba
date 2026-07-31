-- 题库 V2 管理端菜单
-- 注意：避免与现有菜单 ID 冲突（现有最大 232），使用 300+ 范围

-- 1. 顶级目录
insert into sys_menu (id, title, name, path, sort, icon, type, component, perms, status, display, cache, link, remark, parent_id, created_time, updated_time)
values
(300, '题库 V2', 'QbankV2', '/qbank-v2', 5, 'mdi:book-open-page-variant', 0, null, null, 1, 1, 1, '', null, null, now(), null);

-- 2. 题库管理
insert into sys_menu (id, title, name, path, sort, icon, type, component, perms, status, display, cache, link, remark, parent_id, created_time, updated_time)
values
(301, '题库管理', 'QbankV2Bank', '/qbank-v2/bank', 1, 'mdi:bookshelf', 1, '/qbank-v2/bank/index', null, 1, 1, 1, '', null, 300, now(), null),
(302, '题库详情', 'QbankV2BankDetail', '/qbank-v2/bank/:id', 0, null, 1, '/qbank-v2/bank/detail', null, 1, 0, 1, '', null, 300, now(), null);

insert into sys_menu (id, title, name, path, sort, icon, type, component, perms, status, display, cache, link, remark, parent_id, created_time, updated_time)
values
(303, '新增', 'QbankV2BankCreate', null, 0, null, 2, null, 'question_bank:bank:create', 1, 0, 1, '', null, 301, now(), null),
(304, '修改', 'QbankV2BankUpdate', null, 0, null, 2, null, 'question_bank:bank:update', 1, 0, 1, '', null, 301, now(), null),
(305, '删除', 'QbankV2BankDelete', null, 0, null, 2, null, 'question_bank:bank:delete', 1, 0, 1, '', null, 301, now(), null),
(306, '发布', 'QbankV2BankPublish', null, 0, null, 2, null, 'question_bank:bank:publish', 1, 0, 1, '', null, 301, now(), null);

-- 3. 题目管理
insert into sys_menu (id, title, name, path, sort, icon, type, component, perms, status, display, cache, link, remark, parent_id, created_time, updated_time)
values
(307, '题目管理', 'QbankV2Question', '/qbank-v2/question', 2, 'mdi:order-bool-ascending-variant', 1, '/qbank-v2/question/index', null, 1, 1, 1, '', null, 300, now(), null),
(308, '题目详情', 'QbankV2QuestionDetail', '/qbank-v2/question/:id', 0, null, 1, '/qbank-v2/question/detail', null, 1, 0, 1, '', null, 300, now(), null);

insert into sys_menu (id, title, name, path, sort, icon, type, component, perms, status, display, cache, link, remark, parent_id, created_time, updated_time)
values
(309, '新增', 'QbankV2QuestionCreate', null, 0, null, 2, null, 'question_bank:bank:create', 1, 0, 1, '', null, 307, now(), null),
(310, '修改', 'QbankV2QuestionUpdate', null, 0, null, 2, null, 'question_bank:bank:update', 1, 0, 1, '', null, 307, now(), null);

-- 4. 知识体系
insert into sys_menu (id, title, name, path, sort, icon, type, component, perms, status, display, cache, link, remark, parent_id, created_time, updated_time)
values
(311, '知识体系', 'QbankV2Knowledge', '/qbank-v2/knowledge', 3, 'mdi:family-tree', 1, '/qbank-v2/knowledge/index', null, 1, 1, 1, '', null, 300, now(), null);

insert into sys_menu (id, title, name, path, sort, icon, type, component, perms, status, display, cache, link, remark, parent_id, created_time, updated_time)
values
(312, '新增', 'QbankV2KnowledgeCreate', null, 0, null, 2, null, 'question_bank:bank:create', 1, 0, 1, '', null, 311, now(), null),
(313, '修改', 'QbankV2KnowledgeUpdate', null, 0, null, 2, null, 'question_bank:bank:update', 1, 0, 1, '', null, 311, now(), null);

-- 5. 合集管理
insert into sys_menu (id, title, name, path, sort, icon, type, component, perms, status, display, cache, link, remark, parent_id, created_time, updated_time)
values
(314, '合集管理', 'QbankV2Catalog', '/qbank-v2/catalog', 4, 'mdi:folder-multiple-outline', 1, '/qbank-v2/catalog/index', null, 1, 1, 1, '', null, 300, now(), null);

insert into sys_menu (id, title, name, path, sort, icon, type, component, perms, status, display, cache, link, remark, parent_id, created_time, updated_time)
values
(315, '新增', 'QbankV2CatalogCreate', null, 0, null, 2, null, 'question_bank:bank:create', 1, 0, 1, '', null, 314, now(), null),
(316, '修改', 'QbankV2CatalogUpdate', null, 0, null, 2, null, 'question_bank:bank:update', 1, 0, 1, '', null, 314, now(), null);

-- 6. 材料管理
insert into sys_menu (id, title, name, path, sort, icon, type, component, perms, status, display, cache, link, remark, parent_id, created_time, updated_time)
values
(317, '材料管理', 'QbankV2Material', '/qbank-v2/material', 5, 'mdi:file-document-multiple', 1, '/qbank-v2/material/index', null, 1, 1, 1, '', null, 300, now(), null);

insert into sys_menu (id, title, name, path, sort, icon, type, component, perms, status, display, cache, link, remark, parent_id, created_time, updated_time)
values
(318, '新增', 'QbankV2MaterialCreate', null, 0, null, 2, null, 'question_bank:bank:create', 1, 0, 1, '', null, 317, now(), null),
(319, '修改', 'QbankV2MaterialUpdate', null, 0, null, 2, null, 'question_bank:bank:update', 1, 0, 1, '', null, 317, now(), null);

-- 7. 标注管理
insert into sys_menu (id, title, name, path, sort, icon, type, component, perms, status, display, cache, link, remark, parent_id, created_time, updated_time)
values
(320, '标注管理', 'QbankV2Annotation', '/qbank-v2/annotation', 6, 'mdi:label-multiple', 1, null, null, 1, 1, 1, '', null, 300, now(), null);

insert into sys_menu (id, title, name, path, sort, icon, type, component, perms, status, display, cache, link, remark, parent_id, created_time, updated_time)
values
(321, '知识点标注', 'QbankV2KnowledgeLabel', '/qbank-v2/annotation/knowledge-label', 1, 'mdi:tag-multiple', 1, '/qbank-v2/annotation/knowledge-label/index', null, 1, 1, 1, '', null, 320, now(), null),
(322, '交互标注', 'QbankV2Interaction', '/qbank-v2/annotation/question-interaction', 2, 'mdi:crosshairs-gps', 1, '/qbank-v2/annotation/question-interaction/index', null, 1, 1, 1, '', null, 320, now(), null);