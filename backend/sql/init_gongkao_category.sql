-- ============================================
-- 公考应用分类初始化数据
-- app_code: gongkao
-- ============================================

-- 清理旧数据（可选，谨慎使用）
-- DELETE FROM sys_category WHERE app_code = 'gongkao';

-- ============================================
-- 1. 科目分类 (type: subject)
-- ============================================
INSERT INTO sys_category (app_code, name, type, code, description, parent_id, level, path, sort_order, status, is_system, created_time)
VALUES
    ('gongkao', '行政职业能力测验', 'subject', 'xingce', '行测，包含言语理解、数量关系、判断推理、资料分析、常识判断', NULL, 1, NULL, 1, true, true, NOW()),
    ('gongkao', '申论', 'subject', 'shenlun', '申论写作，包含归纳概括、提出对策、综合分析、贯彻执行、申发论述', NULL, 1, NULL, 2, true, true, NOW()),
    ('gongkao', '面试', 'subject', 'mianshi', '结构化面试、无领导小组讨论等', NULL, 1, NULL, 3, true, true, NOW()),
    ('gongkao', '公共基础知识', 'subject', 'gonggong', '公基，事业单位常考', NULL, 1, NULL, 4, true, true, NOW()),
    ('gongkao', '专业知识', 'subject', 'zhuanye', '各岗位专业科目', NULL, 1, NULL, 5, true, true, NOW());

-- 行测子分类
INSERT INTO sys_category (app_code, name, type, code, description, parent_id, level, path, sort_order, status, is_system, created_time)
SELECT 'gongkao', name, 'subject', code, description, p.id, 2, CAST(p.id AS VARCHAR), sort_order, true, true, NOW()
FROM (VALUES
    ('言语理解与表达', 'yanyu', '选词填空、片段阅读、语句表达', 1),
    ('数量关系', 'shuliang', '数学运算、数字推理', 2),
    ('判断推理', 'panduan', '图形推理、定义判断、类比推理、逻辑判断', 3),
    ('资料分析', 'ziliao', '文字、表格、图形资料分析', 4),
    ('常识判断', 'changshi', '政治、法律、经济、科技、人文、地理', 5)
) AS sub(name, code, description, sort_order)
CROSS JOIN sys_category p
WHERE p.app_code = 'gongkao' AND p.type = 'subject' AND p.code = 'xingce';

-- 申论子分类
INSERT INTO sys_category (app_code, name, type, code, description, parent_id, level, path, sort_order, status, is_system, created_time)
SELECT 'gongkao', name, 'subject', code, description, p.id, 2, CAST(p.id AS VARCHAR), sort_order, true, true, NOW()
FROM (VALUES
    ('归纳概括', 'guina', '概括主要内容、问题、原因等', 1),
    ('提出对策', 'duice', '针对问题提出解决措施', 2),
    ('综合分析', 'fenxi', '评价、解释、比较分析', 3),
    ('贯彻执行', 'guanche', '公文写作、应用文', 4),
    ('申发论述', 'lunwen', '大作文写作', 5)
) AS sub(name, code, description, sort_order)
CROSS JOIN sys_category p
WHERE p.app_code = 'gongkao' AND p.type = 'subject' AND p.code = 'shenlun';

-- 面试子分类
INSERT INTO sys_category (app_code, name, type, code, description, parent_id, level, path, sort_order, status, is_system, created_time)
SELECT 'gongkao', name, 'subject', code, description, p.id, 2, CAST(p.id AS VARCHAR), sort_order, true, true, NOW()
FROM (VALUES
    ('综合分析', 'ms_fenxi', '社会现象、政策理解、名言警句、哲理故事', 1),
    ('组织管理', 'ms_zuzhi', '调研、宣传、活动策划', 2),
    ('人际沟通', 'ms_renji', '与领导、同事、群众的沟通协调', 3),
    ('应急应变', 'ms_yingji', '突发事件处理', 4),
    ('自我认知', 'ms_ziwo', '求职动机、岗位匹配', 5)
) AS sub(name, code, description, sort_order)
CROSS JOIN sys_category p
WHERE p.app_code = 'gongkao' AND p.type = 'subject' AND p.code = 'mianshi';

-- ============================================
-- 2. 考试类型分类 (type: exam)
-- ============================================
INSERT INTO sys_category (app_code, name, type, code, description, parent_id, level, path, sort_order, status, is_system, created_time)
VALUES
    ('gongkao', '国家公务员考试', 'exam', 'guokao', '国考，每年10-11月报名，11-12月笔试', NULL, 1, NULL, 1, true, true, NOW()),
    ('gongkao', '各省公务员考试', 'exam', 'shengkao', '省考，多省联考一般在3-4月', NULL, 1, NULL, 2, true, true, NOW()),
    ('gongkao', '事业单位考试', 'exam', 'shiye', '事业单位公开招聘', NULL, 1, NULL, 3, true, true, NOW()),
    ('gongkao', '选调生考试', 'exam', 'xuandiao', '定向选调、普通选调', NULL, 1, NULL, 4, true, true, NOW()),
    ('gongkao', '军队文职', 'exam', 'jundui', '军队文职人员招聘', NULL, 1, NULL, 5, true, true, NOW()),
    ('gongkao', '三支一扶', 'exam', 'sanzhiyifu', '支教、支农、支医、扶贫', NULL, 1, NULL, 6, true, true, NOW());

-- 省考子分类（部分省份）
INSERT INTO sys_category (app_code, name, type, code, description, parent_id, level, path, sort_order, status, is_system, created_time)
SELECT 'gongkao', name, 'exam', code, NULL, p.id, 2, CAST(p.id AS VARCHAR), sort_order, true, false, NOW()
FROM (VALUES
    ('北京', 'beijing', 1),
    ('上海', 'shanghai', 2),
    ('广东', 'guangdong', 3),
    ('江苏', 'jiangsu', 4),
    ('浙江', 'zhejiang', 5),
    ('山东', 'shandong', 6),
    ('四川', 'sichuan', 7),
    ('河南', 'henan', 8),
    ('湖北', 'hubei', 9),
    ('湖南', 'hunan', 10)
) AS sub(name, code, sort_order)
CROSS JOIN sys_category p
WHERE p.app_code = 'gongkao' AND p.type = 'exam' AND p.code = 'shengkao';

-- ============================================
-- 3. 资源分类 (type: resource)
-- ============================================
INSERT INTO sys_category (app_code, name, type, code, description, parent_id, level, path, sort_order, status, is_system, created_time)
VALUES
    ('gongkao', '视频课程', 'resource', 'video', '在线视频教程', NULL, 1, NULL, 1, true, true, NOW()),
    ('gongkao', '电子书籍', 'resource', 'ebook', 'PDF、电子教材', NULL, 1, NULL, 2, true, true, NOW()),
    ('gongkao', '题库资料', 'resource', 'question', '真题、模拟题', NULL, 1, NULL, 3, true, true, NOW()),
    ('gongkao', '讲义笔记', 'resource', 'note', '课程讲义、学习笔记', NULL, 1, NULL, 4, true, true, NOW()),
    ('gongkao', '时政热点', 'resource', 'news', '时事政治、热点分析', NULL, 1, NULL, 5, true, true, NOW()),
    ('gongkao', '上岸经验', 'resource', 'experience', '备考经验、心得分享', NULL, 1, NULL, 6, true, true, NOW());

-- ============================================
-- 4. 机构分类 (type: org) - 答案来源
-- ============================================
INSERT INTO sys_category (app_code, name, type, code, description, parent_id, level, path, sort_order, status, is_system, created_time)
VALUES
    ('gongkao', '官方', 'org', 'official', '官方公布的答案', NULL, 1, NULL, 1, true, true, NOW()),
    ('gongkao', '粉笔', 'org', 'fenbi', '粉笔教育', NULL, 1, NULL, 2, true, false, NOW()),
    ('gongkao', '华图', 'org', 'huatu', '华图教育', NULL, 1, NULL, 3, true, false, NOW()),
    ('gongkao', '中公', 'org', 'zhonggong', '中公教育', NULL, 1, NULL, 4, true, false, NOW()),
    ('gongkao', '其他', 'org', 'other', '其他来源', NULL, 1, NULL, 99, true, false, NOW());

-- ============================================
-- 更新 path 字段（针对有子分类的记录）
-- ============================================
UPDATE sys_category c
SET path = CAST(c.parent_id AS VARCHAR)
WHERE c.app_code = 'gongkao'
  AND c.parent_id IS NOT NULL
  AND c.level = 2;

-- ============================================
-- 验证数据
-- ============================================
-- SELECT type, COUNT(*) as count FROM sys_category WHERE app_code = 'gongkao' GROUP BY type;
-- SELECT * FROM sys_category WHERE app_code = 'gongkao' ORDER BY type, level, sort_order;
