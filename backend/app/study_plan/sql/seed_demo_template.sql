-- 国考 7 天试用模板（演示用 / 联调用）
-- 1 个 template + 14 个 template_item（每天 2 项）
-- 幂等：先按 name 删除老种子再插入；执行多次结果一致
--
-- 模块覆盖：
--   review × 5     → 引用 fba.sys_content（行程 643 / 两集合 642 / 工程 641 / 浓度 640 / 年龄 639）
--   practice × 7   → 引用 fba.study_question_bank（2487 / 2483 / 2482 / 2481 / 2477，循环复用）
--   wrong_review × 2  → ref_id NULL，启动时由 service 动态计算
--   ability × 0    → MVP 不实现（D8）
--
-- 执行：psql 或 dbeaver 直接跑；要求 fba.study_user_account 中存在 user_id=1 的 superuser

BEGIN;

-- 清掉老种子（用名称匹配，不影响其他模板）
DELETE FROM fba.study_plan_template
 WHERE name = '国考冲刺 · 数量关系 7 天试用';

-- 主模板
INSERT INTO fba.study_plan_template (
  name, duration_days, domain, description, is_active, created_by,
  created_time, updated_time
) VALUES (
  '国考冲刺 · 数量关系 7 天试用',
  7,
  'civil_service',
  '示范模板：每天 2 项，覆盖学习 / 刷题 / 错题复盘三类模块',
  TRUE,
  1,
  NOW(),
  NOW()
)
RETURNING id;

-- 取回刚插入的 template_id 用 CTE 一次性插入所有项
WITH t AS (
  SELECT id FROM fba.study_plan_template
   WHERE name = '国考冲刺 · 数量关系 7 天试用'
   ORDER BY id DESC LIMIT 1
)
INSERT INTO fba.study_plan_template_item (
  template_id, day_index, order_index, module_type, title,
  ref_type, ref_id, expected_minutes, extra,
  created_time, updated_time
)
SELECT t.id, day_index, order_index, module_type, title,
       ref_type, ref_id, expected_minutes, extra::jsonb,
       NOW(), NOW()
FROM t, (VALUES
  -- Day 1：行程问题
  (1, 0, 'review',       '数量关系·行程问题（看讲解）',     'content',       643,  15, '{"summary":"先看讲解掌握公式"}'),
  (1, 1, 'practice',     '数量关系·真题练习 20 题',         'question_set',  2487, 30, '{"question_count":20,"required_accuracy":0.6}'),

  -- Day 2：两集合容斥
  (2, 0, 'review',       '数量关系·两集合容斥（看讲解）',   'content',       642,  15, '{"summary":"重点理解容斥公式"}'),
  (2, 1, 'practice',     '数量关系·真题练习 20 题',         'question_set',  2483, 30, '{"question_count":20,"required_accuracy":0.6}'),

  -- Day 3：工程问题
  (3, 0, 'review',       '数量关系·工程问题（看讲解）',     'content',       641,  15, '{"summary":"工作量 = 效率 × 时间"}'),
  (3, 1, 'practice',     '数量关系·真题练习 20 题',         'question_set',  2482, 30, '{"question_count":20,"required_accuracy":0.6}'),

  -- Day 4：错题复盘 + 浓度问题
  (4, 0, 'wrong_review', '近 30 天错题复盘',               'wrong_dynamic', NULL, 20, '{"limit":10}'),
  (4, 1, 'review',       '数量关系·浓度问题（看讲解）',     'content',       640,  15, '{"summary":"浓度 = 溶质 / 溶液"}'),

  -- Day 5：年龄问题
  (5, 0, 'review',       '数量关系·年龄问题（看讲解）',     'content',       639,  15, '{"summary":"年龄差永恒不变"}'),
  (5, 1, 'practice',     '数量关系·真题练习 20 题',         'question_set',  2481, 30, '{"question_count":20,"required_accuracy":0.6}'),

  -- Day 6：综合刷题
  (6, 0, 'practice',     '数量关系·综合训练 25 题',         'question_set',  2477, 35, '{"question_count":25,"required_accuracy":0.6}'),
  (6, 1, 'practice',     '数量关系·进阶训练 15 题',         'question_set',  2487, 25, '{"question_count":15,"required_accuracy":0.7}'),

  -- Day 7：错题复盘 + 综合冲刺
  (7, 0, 'wrong_review', '本周错题复盘',                   'wrong_dynamic', NULL, 25, '{"limit":15}'),
  (7, 1, 'practice',     '数量关系·冲刺训练 30 题',         'question_set',  2483, 45, '{"question_count":30,"required_accuracy":0.65}')
) AS v(day_index, order_index, module_type, title, ref_type, ref_id, expected_minutes, extra);

-- 验证：应返回 1 个 template + 14 个 items
SELECT
  (SELECT COUNT(*) FROM fba.study_plan_template
    WHERE name = '国考冲刺 · 数量关系 7 天试用' AND deleted = 0) AS templates,
  (SELECT COUNT(*) FROM fba.study_plan_template_item ti
     JOIN fba.study_plan_template t ON t.id = ti.template_id
    WHERE t.name = '国考冲刺 · 数量关系 7 天试用' AND ti.deleted = 0) AS items;

COMMIT;
