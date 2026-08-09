INSERT INTO qbank_v2_knowledge_system (code, name, version, description, status, created_by, created_time)
VALUES ('xingce', '行测', 'fenbi', '粉笔行测知识点体系', 'active', 1, NOW());

-- 政治理论
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_832366', '政治理论', 0, NULL, '/fenbi_832366', 1, 1, NOW();
-- 常识判断
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_783916', '常识判断', 0, NULL, '/fenbi_783916', 2, 1, NOW();
-- 言语理解与表达
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_783917', '言语理解与表达', 0, NULL, '/fenbi_783917', 3, 1, NOW();
-- 数量关系
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_783918', '数量关系', 0, NULL, '/fenbi_783918', 4, 1, NOW();
-- 判断推理
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_783919', '判断推理', 0, NULL, '/fenbi_783919', 5, 1, NOW();
-- 资料分析
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_783920', '资料分析', 0, NULL, '/fenbi_783920', 6, 1, NOW();
-- 马克思主义
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_833701', '马克思主义', 1, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_832366' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_833701', 1, 1, NOW();
-- 新思想
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784172', '新思想', 1, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_832366' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784172', 2, 1, NOW();
-- 时事政治
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784173', '时事政治', 1, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_832366' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784173', 3, 1, NOW();
-- 毛中特
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_942938', '毛中特', 1, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_832366' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_942938', 4, 1, NOW();
-- 经济常识
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784167', '经济常识', 1, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_783916' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784167', 1, 1, NOW();
-- 法律常识
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784168', '法律常识', 1, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_783916' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784168', 2, 1, NOW();
-- 科技常识
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784169', '科技常识', 1, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_783916' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784169', 3, 1, NOW();
-- 人文常识
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784170', '人文常识', 1, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_783916' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784170', 4, 1, NOW();
-- 地理国情
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784171', '地理国情', 1, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_783916' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784171', 5, 1, NOW();
-- 逻辑填空
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784198', '逻辑填空', 1, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_783917' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784198', 1, 1, NOW();
-- 片段阅读
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784196', '片段阅读', 1, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_783917' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784196', 2, 1, NOW();
-- 语句表达
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784197', '语句表达', 1, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_783917' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784197', 3, 1, NOW();
-- 数学运算
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784242', '数学运算', 1, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_783918' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784242', 1, 1, NOW();
-- 图形推理
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784291', '图形推理', 1, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_783919' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784291', 1, 1, NOW();
-- 定义判断
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784292', '定义判断', 1, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_783919' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784292', 2, 1, NOW();
-- 类比推理
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784293', '类比推理', 1, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_783919' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784293', 3, 1, NOW();
-- 逻辑判断
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784294', '逻辑判断', 1, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_783919' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784294', 4, 1, NOW();
-- 文字资料
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784357', '文字资料', 1, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_783920' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784357', 1, 1, NOW();
-- 统计表
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784358', '统计表', 1, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_783920' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784358', 2, 1, NOW();
-- 统计图
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784359', '统计图', 1, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_783920' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784359', 3, 1, NOW();
-- 综合资料
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784360', '综合资料', 1, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_783920' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784360', 4, 1, NOW();
-- 简单计算
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784361', '简单计算', 1, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_783920' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784361', 5, 1, NOW();
-- 基期与现期
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784362', '基期与现期', 1, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_783920' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784362', 6, 1, NOW();
-- 增长率
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784363', '增长率', 1, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_783920' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784363', 7, 1, NOW();
-- 增长量
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784364', '增长量', 1, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_783920' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784364', 8, 1, NOW();
-- 比重问题
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784365', '比重问题', 1, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_783920' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784365', 9, 1, NOW();
-- 平均数问题
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784366', '平均数问题', 1, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_783920' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784366', 10, 1, NOW();
-- 倍数与比值相关
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784367', '倍数与比值相关', 1, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_783920' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784367', 11, 1, NOW();
-- 综合分析
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784368', '综合分析', 1, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_783920' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784368', 12, 1, NOW();
-- 马克思主义哲学
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_841835', '马克思主义哲学', 2, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_833701' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_841835', 1, 1, NOW();
-- 马克思主义政治经济学
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_841836', '马克思主义政治经济学', 2, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_833701' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_841836', 2, 1, NOW();
-- 科学社会主义
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_940968', '科学社会主义', 2, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_833701' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_940968', 3, 1, NOW();
-- 新思想总论
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_841840', '新思想总论', 2, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784172' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_841840', 1, 1, NOW();
-- 五位一体建设
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_941849', '五位一体建设', 2, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784172' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_941849', 2, 1, NOW();
-- 其他建设
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_941850', '其他建设', 2, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784172' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_941850', 3, 1, NOW();
-- 重要文件
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_841851', '重要文件', 2, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784173' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_841851', 1, 1, NOW();
-- 重要会议讲话
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_841852', '重要会议讲话', 2, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784173' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_841852', 2, 1, NOW();
-- 重要事件
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_841853', '重要事件', 2, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784173' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_841853', 3, 1, NOW();
-- 时事政治-其他
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_841854', '时事政治-其他', 2, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784173' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_841854', 4, 1, NOW();
-- 党的基本知识
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_942939', '党的基本知识', 2, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_942938' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_942939', 1, 1, NOW();
-- 宏观经济与调控政策
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784175', '宏观经济与调控政策', 2, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784167' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784175', 1, 1, NOW();
-- 市场经济
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_942652', '市场经济', 2, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784167' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_942652', 2, 1, NOW();
-- 国际经济及组织
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_942653', '国际经济及组织', 2, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784167' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_942653', 3, 1, NOW();
-- 微观经济
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_942654', '微观经济', 2, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784167' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_942654', 4, 1, NOW();
-- 法理学
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_942540', '法理学', 2, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784168' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_942540', 1, 1, NOW();
-- 宪法
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_942541', '宪法', 2, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784168' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_942541', 2, 1, NOW();
-- 行政法
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784178', '行政法', 2, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784168' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784178', 3, 1, NOW();
-- 民法典
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784180', '民法典', 2, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784168' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784180', 4, 1, NOW();
-- 刑法
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_942542', '刑法', 2, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784168' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_942542', 5, 1, NOW();
-- 诉讼法
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_942543', '诉讼法', 2, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784168' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_942543', 6, 1, NOW();
-- 劳动法和经济法
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_942544', '劳动法和经济法', 2, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784168' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_942544', 7, 1, NOW();
-- 其他法律法规
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784182', '其他法律法规', 2, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784168' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784182', 8, 1, NOW();
-- 物理常识
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784185', '物理常识', 2, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784169' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784185', 1, 1, NOW();
-- 化学常识
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784186', '化学常识', 2, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784169' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784186', 2, 1, NOW();
-- 生物常识
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784187', '生物常识', 2, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784169' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784187', 3, 1, NOW();
-- 生活常识
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784188', '生活常识', 2, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784169' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784188', 4, 1, NOW();
-- 科技理论与成就
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784189', '科技理论与成就', 2, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784169' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784189', 5, 1, NOW();
-- 科技常识-其他
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_824746', '科技常识-其他', 2, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784169' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_824746', 6, 1, NOW();
-- 中国历史
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784190', '中国历史', 2, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784170' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784190', 1, 1, NOW();
-- 文学常识
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784192', '文学常识', 2, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784170' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784192', 2, 1, NOW();
-- 文化常识
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784193', '文化常识', 2, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784170' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784193', 3, 1, NOW();
-- 自然地理
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784194', '自然地理', 2, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784171' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784194', 1, 1, NOW();
-- 中国地理
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784195', '中国地理', 2, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784171' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784195', 2, 1, NOW();
-- 世界地理
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_943088', '世界地理', 2, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784171' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_943088', 3, 1, NOW();
-- 其他
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_943089', '其他', 2, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784171' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_943089', 4, 1, NOW();
-- 实词填空
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784226', '实词填空', 2, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784198' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784226', 1, 1, NOW();
-- 成语填空
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784227', '成语填空', 2, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784198' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784227', 2, 1, NOW();
-- 混搭填空
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784228', '混搭填空', 2, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784198' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784228', 3, 1, NOW();
-- 词的辨析
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784229', '词的辨析', 2, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784198' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784229', 4, 1, NOW();
-- 语境分析
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784230', '语境分析', 2, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784198' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784230', 5, 1, NOW();
-- 中心理解题
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784199', '中心理解题', 2, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784196' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784199', 1, 1, NOW();
-- 细节判断题
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784200', '细节判断题', 2, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784196' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784200', 2, 1, NOW();
-- 词句理解题
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784201', '词句理解题', 2, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784196' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784201', 3, 1, NOW();
-- 标题填入题
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784202', '标题填入题', 2, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784196' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784202', 4, 1, NOW();
-- 语句排序题
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784215', '语句排序题', 2, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784197' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784215', 1, 1, NOW();
-- 语句填空题
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784216', '语句填空题', 2, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784197' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784216', 2, 1, NOW();
-- 接语选择题
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784217', '接语选择题', 2, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784197' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784217', 3, 1, NOW();
-- 语句排序题、语句填空题混合题型
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_843001', '语句排序题、语句填空题混合题型', 2, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784197' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_843001', 4, 1, NOW();
-- 工程问题
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784243', '工程问题', 2, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784242' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784243', 1, 1, NOW();
-- 最值问题
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784244', '最值问题', 2, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784242' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784244', 2, 1, NOW();
-- 年龄问题
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784245', '年龄问题', 2, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784242' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784245', 3, 1, NOW();
-- 周期问题
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784246', '周期问题', 2, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784242' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784246', 4, 1, NOW();
-- 和差倍比问题
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784247', '和差倍比问题', 2, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784242' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784247', 5, 1, NOW();
-- 数列问题
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784248', '数列问题', 2, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784242' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784248', 6, 1, NOW();
-- 行程问题
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784249', '行程问题', 2, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784242' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784249', 7, 1, NOW();
-- 几何问题
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784250', '几何问题', 2, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784242' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784250', 8, 1, NOW();
-- 容斥原理问题
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784251', '容斥原理问题', 2, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784242' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784251', 9, 1, NOW();
-- 排列组合问题
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784252', '排列组合问题', 2, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784242' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784252', 10, 1, NOW();
-- 概率问题
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784253', '概率问题', 2, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784242' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784253', 11, 1, NOW();
-- 经济利润问题
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784254', '经济利润问题', 2, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784242' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784254', 12, 1, NOW();
-- 统筹规划问题
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784256', '统筹规划问题', 2, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784242' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784256', 13, 1, NOW();
-- 星期日期问题
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_810831', '星期日期问题', 2, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784242' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_810831', 14, 1, NOW();
-- 分段计算问题
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_842968', '分段计算问题', 2, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784242' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_842968', 15, 1, NOW();
-- 函数最值问题
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_842969', '函数最值问题', 2, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784242' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_842969', 16, 1, NOW();
-- 平均数问题
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_941046', '平均数问题', 2, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784242' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_941046', 17, 1, NOW();
-- 位置规律
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784295', '位置规律', 2, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784291' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784295', 1, 1, NOW();
-- 样式规律
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784296', '样式规律', 2, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784291' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784296', 2, 1, NOW();
-- 属性规律
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784297', '属性规律', 2, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784291' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784297', 3, 1, NOW();
-- 数量规律
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784298', '数量规律', 2, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784291' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784298', 4, 1, NOW();
-- 特殊规律
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784299', '特殊规律', 2, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784291' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784299', 5, 1, NOW();
-- 空间类
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784300', '空间类', 2, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784291' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784300', 6, 1, NOW();
-- 文字/字母/数字类
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784302', '文字/字母/数字类', 2, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784291' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784302', 7, 1, NOW();
-- 黑白块类
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784301', '黑白块类', 2, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784291' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784301', 8, 1, NOW();
-- 单定义
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784322', '单定义', 2, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784292' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784322', 1, 1, NOW();
-- 多定义
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784323', '多定义', 2, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784292' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784323', 2, 1, NOW();
-- 语义关系
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784331', '语义关系', 2, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784293' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784331', 1, 1, NOW();
-- 逻辑关系
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784332', '逻辑关系', 2, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784293' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784332', 2, 1, NOW();
-- 语法关系
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_838304', '语法关系', 2, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784293' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_838304', 3, 1, NOW();
-- 拆分思维
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784333', '拆分思维', 2, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784293' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784333', 4, 1, NOW();
-- 加强题型
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784342', '加强题型', 2, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784294' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784342', 1, 1, NOW();
-- 削弱题型
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784343', '削弱题型', 2, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784294' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784343', 2, 1, NOW();
-- 翻译推理
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784346', '翻译推理', 2, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784294' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784346', 3, 1, NOW();
-- 组合排列-材料
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784344', '组合排列-材料', 2, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784294' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784344', 4, 1, NOW();
-- 组合排列-单题
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_842995', '组合排列-单题', 2, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784294' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_842995', 5, 1, NOW();
-- 原因解释
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784345', '原因解释', 2, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784294' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784345', 6, 1, NOW();
-- 真假推理
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_837343', '真假推理', 2, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784294' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_837343', 7, 1, NOW();
-- 日常结论
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_842996', '日常结论', 2, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784294' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_842996', 8, 1, NOW();
-- 论证结构
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_842997', '论证结构', 2, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784294' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_842997', 9, 1, NOW();
-- 直接找数
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784369', '直接找数', 2, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784361' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784369', 1, 1, NOW();
-- 简单加减计算
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784370', '简单加减计算', 2, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784361' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784370', 2, 1, NOW();
-- 排序类
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_792390', '排序类', 2, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784361' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_792390', 3, 1, NOW();
-- 基期计算
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784371', '基期计算', 2, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784362' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784371', 1, 1, NOW();
-- 现期计算
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784372', '现期计算', 2, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784362' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784372', 2, 1, NOW();
-- 基期比较
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_792391', '基期比较', 2, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784362' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_792391', 3, 1, NOW();
-- 间隔基期
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_792392', '间隔基期', 2, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784362' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_792392', 4, 1, NOW();
-- 基期和差
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_792393', '基期和差', 2, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784362' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_792393', 5, 1, NOW();
-- 一般增长率
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784373', '一般增长率', 2, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784363' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784373', 1, 1, NOW();
-- 混合增长率
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784374', '混合增长率', 2, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784363' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784374', 2, 1, NOW();
-- 间隔增长率
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_792395', '间隔增长率', 2, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784363' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_792395', 3, 1, NOW();
-- 年均增长率
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_792396', '年均增长率', 2, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784363' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_792396', 4, 1, NOW();
-- 增长量计算
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784375', '增长量计算', 2, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784364' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784375', 1, 1, NOW();
-- 增长量比较
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784376', '增长量比较', 2, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784364' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784376', 2, 1, NOW();
-- 间隔增长量
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_792397', '间隔增长量', 2, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784364' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_792397', 3, 1, NOW();
-- 年均增长量
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_792398', '年均增长量', 2, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784364' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_792398', 4, 1, NOW();
-- 现期比重
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784377', '现期比重', 2, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784365' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784377', 1, 1, NOW();
-- 基期比重
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784378', '基期比重', 2, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784365' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784378', 2, 1, NOW();
-- 两期比重
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784379', '两期比重', 2, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784365' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784379', 3, 1, NOW();
-- 混合比重
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_792399', '混合比重', 2, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784365' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_792399', 4, 1, NOW();
-- 基期平均数
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784380', '基期平均数', 2, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784366' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784380', 1, 1, NOW();
-- 现期平均数
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784381', '现期平均数', 2, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784366' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784381', 2, 1, NOW();
-- 平均数的增长率
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784382', '平均数的增长率', 2, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784366' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784382', 3, 1, NOW();
-- 平均数的增长量
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784383', '平均数的增长量', 2, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784366' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784383', 4, 1, NOW();
-- 两期平均数比较
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784384', '两期平均数比较', 2, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784366' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784384', 5, 1, NOW();
-- 基期倍数
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784385', '基期倍数', 2, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784367' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784385', 1, 1, NOW();
-- 现期倍数
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784386', '现期倍数', 2, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784367' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784386', 2, 1, NOW();
-- 比值计算
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_792400', '比值计算', 2, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784367' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_792400', 3, 1, NOW();
-- 比值比较
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_792401', '比值比较', 2, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784367' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_792401', 4, 1, NOW();
-- 倍数比较
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_792402', '倍数比较', 2, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784367' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_792402', 5, 1, NOW();
-- 总论
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_940962', '总论', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_841835' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_940962', 1, 1, NOW();
-- 唯物论
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_841837', '唯物论', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_841835' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_841837', 2, 1, NOW();
-- 唯物辩证法
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_841838', '唯物辩证法', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_841835' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_841838', 3, 1, NOW();
-- 认识论
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_940963', '认识论', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_841835' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_940963', 4, 1, NOW();
-- 唯物史观
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_940964', '唯物史观', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_841835' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_940964', 5, 1, NOW();
-- 哲学-其他
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_940965', '哲学-其他', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_841835' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_940965', 6, 1, NOW();
-- 商品经济
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_841839', '商品经济', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_841836' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_841839', 1, 1, NOW();
-- 资本主义制度
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_940966', '资本主义制度', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_841836' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_940966', 2, 1, NOW();
-- 政治经济学-其他
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_940967', '政治经济学-其他', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_841836' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_940967', 3, 1, NOW();
-- 经济建设
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_841841', '经济建设', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_941849' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_841841', 1, 1, NOW();
-- 政治建设
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_841842', '政治建设', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_941849' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_841842', 2, 1, NOW();
-- 文化建设
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_841843', '文化建设', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_941849' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_841843', 3, 1, NOW();
-- 社会建设
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_841844', '社会建设', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_941849' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_841844', 4, 1, NOW();
-- 生态文明建设
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_841845', '生态文明建设', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_941849' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_841845', 5, 1, NOW();
-- 党的历史
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_942940', '党的历史', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_942939' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_942940', 1, 1, NOW();
-- 党章党纪
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_942941', '党章党纪', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_942939' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_942941', 2, 1, NOW();
-- 词的辨析-词义侧重
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784231', '词的辨析-词义侧重', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784229' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784231', 1, 1, NOW();
-- 词的辨析-搭配对象
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784232', '词的辨析-搭配对象', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784229' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784232', 2, 1, NOW();
-- 词的辨析-感情色彩
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784233', '词的辨析-感情色彩', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784229' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784233', 3, 1, NOW();
-- 词的辨析-程度轻重
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784234', '词的辨析-程度轻重', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784229' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784234', 4, 1, NOW();
-- 关联关系-转折关系
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784235', '关联关系-转折关系', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784230' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784235', 1, 1, NOW();
-- 关联关系-因果关系
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784236', '关联关系-因果关系', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784230' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784236', 2, 1, NOW();
-- 关联关系-并列关系
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784237', '关联关系-并列关系', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784230' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784237', 3, 1, NOW();
-- 对应关系-解释说明
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784238', '对应关系-解释说明', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784230' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784238', 4, 1, NOW();
-- 对应关系-形象表达
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784239', '对应关系-形象表达', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784230' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784239', 5, 1, NOW();
-- 对应关系-主题词
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_827859', '对应关系-主题词', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784230' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_827859', 6, 1, NOW();
-- 对应关系-前后呼应
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_827860', '对应关系-前后呼应', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784230' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_827860', 7, 1, NOW();
-- 关联词-转折
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784203', '关联词-转折', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784199' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784203', 1, 1, NOW();
-- 关联词-因果
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784204', '关联词-因果', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784199' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784204', 2, 1, NOW();
-- 关联词-对策
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784205', '关联词-对策', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784199' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784205', 3, 1, NOW();
-- 关联词-并列
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784206', '关联词-并列', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784199' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784206', 4, 1, NOW();
-- 主题词
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784207', '主题词', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784199' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784207', 5, 1, NOW();
-- 分述句特征-举例子
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784209', '分述句特征-举例子', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784199' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784209', 6, 1, NOW();
-- 分述句特征-数据资料
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784210', '分述句特征-数据资料', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784199' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784210', 7, 1, NOW();
-- 分述句特征-多角度论述
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784211', '分述句特征-多角度论述', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784199' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784211', 8, 1, NOW();
-- 分述句特征-引入铺垫
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_840743', '分述句特征-引入铺垫', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784199' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_840743', 9, 1, NOW();
-- 分述句特征-其他
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_840744', '分述句特征-其他', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784199' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_840744', 10, 1, NOW();
-- 特殊问法
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784212', '特殊问法', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784199' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784212', 11, 1, NOW();
-- 实词
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784213', '实词', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784201' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784213', 1, 1, NOW();
-- 代词
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_842998', '代词', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784201' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_842998', 2, 1, NOW();
-- 句子
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_842999', '句子', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784201' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_842999', 3, 1, NOW();
-- 确定首句-首句特征
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784218', '确定首句-首句特征', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784215' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784218', 1, 1, NOW();
-- 确定首句-非首句特征
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_833707', '确定首句-非首句特征', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784215' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_833707', 2, 1, NOW();
-- 确定捆绑
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784220', '确定捆绑', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784215' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784220', 3, 1, NOW();
-- 确定顺序
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784221', '确定顺序', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784215' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784221', 4, 1, NOW();
-- 确定尾句
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784222', '确定尾句', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784215' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784222', 5, 1, NOW();
-- 横线在开头
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784223', '横线在开头', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784216' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784223', 1, 1, NOW();
-- 横线在中间
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784224', '横线在中间', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784216' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784224', 2, 1, NOW();
-- 横线在结尾
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784225', '横线在结尾', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784216' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784225', 3, 1, NOW();
-- 特殊题型-问语句在文中的位置
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_843000', '特殊题型-问语句在文中的位置', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784216' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_843000', 4, 1, NOW();
-- 给完工时间型
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784258', '给完工时间型', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784243' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784258', 1, 1, NOW();
-- 给效率比例型
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784259', '给效率比例型', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784243' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784259', 2, 1, NOW();
-- 给具体单位型
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784260', '给具体单位型', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784243' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784260', 3, 1, NOW();
-- 工程问题-其他
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784261', '工程问题-其他', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784243' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784261', 4, 1, NOW();
-- 非典型最值问题
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784262', '非典型最值问题', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784244' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784262', 1, 1, NOW();
-- 构造数列
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784263', '构造数列', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784244' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784263', 2, 1, NOW();
-- 最不利构造
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784264', '最不利构造', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784244' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784264', 3, 1, NOW();
-- 多集合反向构造
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784265', '多集合反向构造', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784244' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784265', 4, 1, NOW();
-- 周期相遇问题
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784266', '周期相遇问题', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784246' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784266', 1, 1, NOW();
-- 周期余数问题
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784267', '周期余数问题', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784246' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784267', 2, 1, NOW();
-- 周期问题-其他
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784268', '周期问题-其他', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784246' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784268', 3, 1, NOW();
-- 火车过桥
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784269', '火车过桥', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784249' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784269', 1, 1, NOW();
-- 平均速度
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784270', '平均速度', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784249' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784270', 2, 1, NOW();
-- 普通行程
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784271', '普通行程', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784249' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784271', 3, 1, NOW();
-- 相遇追及
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784272', '相遇追及', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784249' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784272', 4, 1, NOW();
-- 流水行船
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784273', '流水行船', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784249' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784273', 5, 1, NOW();
-- 行程问题-其他
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784274', '行程问题-其他', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784249' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784274', 6, 1, NOW();
-- 几何公式类-平面图形
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784275', '几何公式类-平面图形', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784250' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784275', 1, 1, NOW();
-- 几何公式类-立体图形
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784276', '几何公式类-立体图形', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784250' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784276', 2, 1, NOW();
-- 几何结论类-相似图形
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_849716', '几何结论类-相似图形', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784250' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_849716', 3, 1, NOW();
-- 几何结论类-三角形相关
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_849717', '几何结论类-三角形相关', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784250' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_849717', 4, 1, NOW();
-- 几何结论类-几何小题型
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_849718', '几何结论类-几何小题型', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784250' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_849718', 5, 1, NOW();
-- 几何其他题型
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_849719', '几何其他题型', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784250' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_849719', 6, 1, NOW();
-- 两集合
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784277', '两集合', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784251' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784277', 1, 1, NOW();
-- 三集合
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784278', '三集合', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784251' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784278', 2, 1, NOW();
-- 基础排列组合
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784279', '基础排列组合', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784252' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784279', 1, 1, NOW();
-- 相邻问题
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784280', '相邻问题', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784252' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784280', 2, 1, NOW();
-- 不相邻问题
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784281', '不相邻问题', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784252' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784281', 3, 1, NOW();
-- 同素分堆问题
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784282', '同素分堆问题', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784252' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784282', 4, 1, NOW();
-- 环形排列问题
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784283', '环形排列问题', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784252' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784283', 5, 1, NOW();
-- 错位排列
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784284', '错位排列', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784252' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784284', 6, 1, NOW();
-- 排列组合问题-其他
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784285', '排列组合问题-其他', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784252' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784285', 7, 1, NOW();
-- 给情况求概率
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784286', '给情况求概率', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784253' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784286', 1, 1, NOW();
-- 给概率求概率
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784287', '给概率求概率', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784253' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784287', 2, 1, NOW();
-- 概率问题-其他
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784288', '概率问题-其他', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784253' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784288', 3, 1, NOW();
-- 位置规律-平移
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784303', '位置规律-平移', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784295' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784303', 1, 1, NOW();
-- 位置规律-旋转
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784304', '位置规律-旋转', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784295' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784304', 2, 1, NOW();
-- 位置规律-综合
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784305', '位置规律-综合', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784295' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784305', 3, 1, NOW();
-- 位置规律-翻转
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_842988', '位置规律-翻转', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784295' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_842988', 4, 1, NOW();
-- 样式规律-加减同异
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784306', '样式规律-加减同异', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784296' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784306', 1, 1, NOW();
-- 样式规律-黑白运算
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784307', '样式规律-黑白运算', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784296' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784307', 2, 1, NOW();
-- 样式规律-遍历
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_842989', '样式规律-遍历', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784296' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_842989', 3, 1, NOW();
-- 属性规律-对称性
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784308', '属性规律-对称性', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784297' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784308', 1, 1, NOW();
-- 属性规律-开闭性
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_842990', '属性规律-开闭性', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784297' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_842990', 2, 1, NOW();
-- 属性规律-曲直性
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_842991', '属性规律-曲直性', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784297' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_842991', 3, 1, NOW();
-- 属性规律-复合
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_842992', '属性规律-复合', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784297' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_842992', 4, 1, NOW();
-- 数量规律-点
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784309', '数量规律-点', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784298' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784309', 1, 1, NOW();
-- 数量规律-线
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784310', '数量规律-线', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784298' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784310', 2, 1, NOW();
-- 数量规律-面
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784311', '数量规律-面', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784298' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784311', 3, 1, NOW();
-- 数量规律-角
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784312', '数量规律-角', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784298' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784312', 4, 1, NOW();
-- 数量规律-素
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784313', '数量规律-素', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784298' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784313', 5, 1, NOW();
-- 数量规律-复合
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784314', '数量规律-复合', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784298' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784314', 6, 1, NOW();
-- 特殊规律-图形间关系
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784315', '特殊规律-图形间关系', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784299' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784315', 1, 1, NOW();
-- 特殊规律-功能元素
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_842993', '特殊规律-功能元素', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784299' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_842993', 2, 1, NOW();
-- 空间类-立体拼合
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784317', '空间类-立体拼合', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784300' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784317', 1, 1, NOW();
-- 空间类-三视图
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784318', '空间类-三视图', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784300' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784318', 2, 1, NOW();
-- 空间类-截面图
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784319', '空间类-截面图', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784300' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784319', 3, 1, NOW();
-- 空间类-空间重构-六面体
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784320', '空间类-空间重构-六面体', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784300' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784320', 4, 1, NOW();
-- 主客体
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784324', '主客体', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784322' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784324', 1, 1, NOW();
-- 大前提
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784325', '大前提', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784322' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784325', 2, 1, NOW();
-- 方式目的
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784326', '方式目的', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784322' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784326', 3, 1, NOW();
-- 原因结果
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784327', '原因结果', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784322' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784327', 4, 1, NOW();
-- 单定义-其他句式
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784328', '单定义-其他句式', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784322' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784328', 5, 1, NOW();
-- 故事类
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_792382', '故事类', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784322' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_792382', 6, 1, NOW();
-- 拆词
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_792383', '拆词', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784322' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_792383', 7, 1, NOW();
-- 常规问法
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784329', '常规问法', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784323' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784329', 1, 1, NOW();
-- 特殊问法
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784330', '特殊问法', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784323' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784330', 2, 1, NOW();
-- 语义关系-近义关系
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784334', '语义关系-近义关系', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784331' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784334', 1, 1, NOW();
-- 语义关系-反义关系
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784335', '语义关系-反义关系', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784331' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784335', 2, 1, NOW();
-- 语义关系-比喻象征义
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_817348', '语义关系-比喻象征义', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784331' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_817348', 3, 1, NOW();
-- 语义-其他
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784336', '语义-其他', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784331' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784336', 4, 1, NOW();
-- 逻辑关系-并列关系
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784338', '逻辑关系-并列关系', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784332' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784338', 1, 1, NOW();
-- 逻辑关系-交叉关系
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784339', '逻辑关系-交叉关系', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784332' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784339', 2, 1, NOW();
-- 逻辑关系-包容关系
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784340', '逻辑关系-包容关系', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784332' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784340', 3, 1, NOW();
-- 逻辑关系-对应关系
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784341', '逻辑关系-对应关系', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784332' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784341', 4, 1, NOW();
-- 逻辑关系-全同关系
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_842994', '逻辑关系-全同关系', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784332' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_842994', 5, 1, NOW();
-- 搭桥
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784347', '搭桥', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784342' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784347', 1, 1, NOW();
-- 必要条件
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784348', '必要条件', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784342' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784348', 2, 1, NOW();
-- 补充论据
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784349', '补充论据', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784342' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784349', 3, 1, NOW();
-- 加强选非题
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784350', '加强选非题', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784342' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784350', 4, 1, NOW();
-- 加强-实验类
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784351', '加强-实验类', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784342' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784351', 5, 1, NOW();
-- 削弱论点
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784352', '削弱论点', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784343' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784352', 1, 1, NOW();
-- 拆桥
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784353', '拆桥', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784343' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784353', 2, 1, NOW();
-- 他因削弱
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784354', '他因削弱', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784343' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784354', 3, 1, NOW();
-- 削弱选非题
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784355', '削弱选非题', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784343' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784355', 4, 1, NOW();
-- 削弱论据
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_792384', '削弱论据', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784343' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_792384', 5, 1, NOW();
-- 因果倒置
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_792385', '因果倒置', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784343' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_792385', 6, 1, NOW();
-- 削弱-实验类
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_792386', '削弱-实验类', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784343' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_792386', 7, 1, NOW();
-- 常规翻译
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_784356', '常规翻译', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784346' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_784356', 1, 1, NOW();
-- 集合推理
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_792387', '集合推理', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784346' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_792387', 2, 1, NOW();
-- 推理形式
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_792388', '推理形式', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_784346' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_792388', 3, 1, NOW();
-- 排除法
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_851140', '排除法', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_842995' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_851140', 1, 1, NOW();
-- 代入法
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_851141', '代入法', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_842995' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_851141', 2, 1, NOW();
-- 从最大信息开始推
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_851142', '从最大信息开始推', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_842995' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_851142', 3, 1, NOW();
-- 假设
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_851143', '假设', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_842995' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_851143', 4, 1, NOW();
-- 框架题
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_851144', '框架题', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_842995' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_851144', 5, 1, NOW();
-- 从确定信息开始推
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_851145', '从确定信息开始推', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_842995' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_851145', 6, 1, NOW();
-- 组合排列-单题-其他
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_943529', '组合排列-单题-其他', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_842995' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_943529', 7, 1, NOW();
-- 只有一真/一假
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_851146', '只有一真/一假', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_837343' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_851146', 1, 1, NOW();
-- 两真两假
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_851147', '两真两假', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_837343' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_851147', 2, 1, NOW();
-- 真假推理-其他
INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_851148', '真假推理-其他', 3, (SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_837343' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), '/fenbi_851148', 3, 1, NOW();
