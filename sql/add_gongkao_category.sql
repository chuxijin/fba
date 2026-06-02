-- ============================================================
-- 新增"公考"顶层分类 + 修正所有后代 level/path
-- ============================================================

-- ---------- product_catalog ----------

-- 1. 新增顶层"公考"
INSERT INTO fba.sys_category (id, app_code, name, type, code, parent_id, level, sort_order, status, is_system, created_by, created_time)
VALUES (500, 'youanshang', '公考', 'product_catalog', 'pc_gongkao', NULL, 1, 15, true, true, 1, NOW());

-- 2. 挂到公考下面
UPDATE fba.sys_category SET parent_id = 500 WHERE id IN (20, 30, 1365);

-- 3. 递归修正所有后代 level+1
WITH RECURSIVE subtree AS (
    SELECT id FROM fba.sys_category WHERE parent_id = 500
    UNION ALL
    SELECT c.id FROM fba.sys_category c JOIN subtree s ON c.parent_id = s.id
)
UPDATE fba.sys_category SET level = level + 1
WHERE id IN (SELECT id FROM subtree);

-- 4. 递归重建所有后代 path（从根往下拼）
WITH RECURSIVE tree AS (
    -- 起点：公考的直接子节点
    SELECT id, parent_id, '500/' || id::text AS full_path
    FROM fba.sys_category WHERE parent_id = 500
    UNION ALL
    -- 递归：子节点继承父的 full_path 再拼自己
    SELECT c.id, c.parent_id, t.full_path || '/' || c.id::text
    FROM fba.sys_category c JOIN tree t ON c.parent_id = t.id
)
UPDATE fba.sys_category c
SET path = t.full_path
FROM tree t
WHERE c.id = t.id;

-- ---------- knowledge_point ----------

-- 5. 新增顶层"公考"
INSERT INTO fba.sys_category (id, app_code, name, type, code, parent_id, level, sort_order, status, is_system, created_by, created_time)
VALUES (501, 'youanshang', '公考', 'knowledge_point', 'kp_gongkao', NULL, 1, 15, true, true, 1, NOW());

-- 6. 挂到公考下面
UPDATE fba.sys_category SET parent_id = 501 WHERE id IN (109, 110, 111);

-- 7. 递归修正所有后代 level+1
WITH RECURSIVE subtree AS (
    SELECT id FROM fba.sys_category WHERE parent_id = 501
    UNION ALL
    SELECT c.id FROM fba.sys_category c JOIN subtree s ON c.parent_id = s.id
)
UPDATE fba.sys_category SET level = level + 1
WHERE id IN (SELECT id FROM subtree);

-- 8. 递归重建所有后代 path
WITH RECURSIVE tree AS (
    SELECT id, parent_id, '501/' || id::text AS full_path
    FROM fba.sys_category WHERE parent_id = 501
    UNION ALL
    SELECT c.id, c.parent_id, t.full_path || '/' || c.id::text
    FROM fba.sys_category c JOIN tree t ON c.parent_id = t.id
)
UPDATE fba.sys_category c
SET path = t.full_path
FROM tree t
WHERE c.id = t.id;

-- ============================================================
-- 验证：检查公考两棵树的结构
-- ============================================================
SELECT id, name, code, parent_id, level, path, type
FROM fba.sys_category
WHERE path LIKE '500/%' OR path LIKE '501/%' OR id IN (500, 501)
ORDER BY type, path;
