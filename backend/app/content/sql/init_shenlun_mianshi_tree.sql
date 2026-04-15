
WITH parent_node AS (
    SELECT id, level FROM sys_category WHERE app_code = 'youanshang' AND type = 'knowledge_point' AND code = 'kp_shenlun'
)
INSERT INTO sys_category (app_code, parent_id, name, code, type, sort_order, level, status, is_system, created_by, created_time)
SELECT 'youanshang', parent_node.id, '阅读理解能力', 'kp_sl_reading', 'knowledge_point', 1, parent_node.level + 1, TRUE, FALSE, 1, NOW()
FROM parent_node
WHERE NOT EXISTS (SELECT 1 FROM sys_category WHERE code = 'kp_sl_reading');

WITH parent_node AS (
    SELECT id, level FROM sys_category WHERE app_code = 'youanshang' AND type = 'knowledge_point' AND code = 'kp_sl_reading'
)
INSERT INTO sys_category (app_code, parent_id, name, code, type, sort_order, level, status, is_system, created_by, created_time)
SELECT 'youanshang', parent_node.id, '词汇理解', 'kp_sl_reading_vocab', 'knowledge_point', 1, parent_node.level + 1, TRUE, FALSE, 1, NOW()
FROM parent_node
WHERE NOT EXISTS (SELECT 1 FROM sys_category WHERE code = 'kp_sl_reading_vocab');

WITH parent_node AS (
    SELECT id, level FROM sys_category WHERE app_code = 'youanshang' AND type = 'knowledge_point' AND code = 'kp_sl_reading'
)
INSERT INTO sys_category (app_code, parent_id, name, code, type, sort_order, level, status, is_system, created_by, created_time)
SELECT 'youanshang', parent_node.id, '句子理解', 'kp_sl_reading_sentence', 'knowledge_point', 2, parent_node.level + 1, TRUE, FALSE, 1, NOW()
FROM parent_node
WHERE NOT EXISTS (SELECT 1 FROM sys_category WHERE code = 'kp_sl_reading_sentence');

WITH parent_node AS (
    SELECT id, level FROM sys_category WHERE app_code = 'youanshang' AND type = 'knowledge_point' AND code = 'kp_sl_reading'
)
INSERT INTO sys_category (app_code, parent_id, name, code, type, sort_order, level, status, is_system, created_by, created_time)
SELECT 'youanshang', parent_node.id, '段落概括', 'kp_sl_reading_paragraph', 'knowledge_point', 3, parent_node.level + 1, TRUE, FALSE, 1, NOW()
FROM parent_node
WHERE NOT EXISTS (SELECT 1 FROM sys_category WHERE code = 'kp_sl_reading_paragraph');

WITH parent_node AS (
    SELECT id, level FROM sys_category WHERE app_code = 'youanshang' AND type = 'knowledge_point' AND code = 'kp_sl_reading'
)
INSERT INTO sys_category (app_code, parent_id, name, code, type, sort_order, level, status, is_system, created_by, created_time)
SELECT 'youanshang', parent_node.id, '逻辑梳理', 'kp_sl_reading_logic', 'knowledge_point', 4, parent_node.level + 1, TRUE, FALSE, 1, NOW()
FROM parent_node
WHERE NOT EXISTS (SELECT 1 FROM sys_category WHERE code = 'kp_sl_reading_logic');

WITH parent_node AS (
    SELECT id, level FROM sys_category WHERE app_code = 'youanshang' AND type = 'knowledge_point' AND code = 'kp_shenlun'
)
INSERT INTO sys_category (app_code, parent_id, name, code, type, sort_order, level, status, is_system, created_by, created_time)
SELECT 'youanshang', parent_node.id, '归纳概括题', 'kp_sl_summarize', 'knowledge_point', 2, parent_node.level + 1, TRUE, FALSE, 1, NOW()
FROM parent_node
WHERE NOT EXISTS (SELECT 1 FROM sys_category WHERE code = 'kp_sl_summarize');

WITH parent_node AS (
    SELECT id, level FROM sys_category WHERE app_code = 'youanshang' AND type = 'knowledge_point' AND code = 'kp_sl_summarize'
)
INSERT INTO sys_category (app_code, parent_id, name, code, type, sort_order, level, status, is_system, created_by, created_time)
SELECT 'youanshang', parent_node.id, '概括问题', 'kp_sl_summarize_problem', 'knowledge_point', 1, parent_node.level + 1, TRUE, FALSE, 1, NOW()
FROM parent_node
WHERE NOT EXISTS (SELECT 1 FROM sys_category WHERE code = 'kp_sl_summarize_problem');

WITH parent_node AS (
    SELECT id, level FROM sys_category WHERE app_code = 'youanshang' AND type = 'knowledge_point' AND code = 'kp_sl_summarize'
)
INSERT INTO sys_category (app_code, parent_id, name, code, type, sort_order, level, status, is_system, created_by, created_time)
SELECT 'youanshang', parent_node.id, '概括原因', 'kp_sl_summarize_reason', 'knowledge_point', 2, parent_node.level + 1, TRUE, FALSE, 1, NOW()
FROM parent_node
WHERE NOT EXISTS (SELECT 1 FROM sys_category WHERE code = 'kp_sl_summarize_reason');

WITH parent_node AS (
    SELECT id, level FROM sys_category WHERE app_code = 'youanshang' AND type = 'knowledge_point' AND code = 'kp_sl_summarize'
)
INSERT INTO sys_category (app_code, parent_id, name, code, type, sort_order, level, status, is_system, created_by, created_time)
SELECT 'youanshang', parent_node.id, '概括影响', 'kp_sl_summarize_impact', 'knowledge_point', 3, parent_node.level + 1, TRUE, FALSE, 1, NOW()
FROM parent_node
WHERE NOT EXISTS (SELECT 1 FROM sys_category WHERE code = 'kp_sl_summarize_impact');

WITH parent_node AS (
    SELECT id, level FROM sys_category WHERE app_code = 'youanshang' AND type = 'knowledge_point' AND code = 'kp_sl_summarize'
)
INSERT INTO sys_category (app_code, parent_id, name, code, type, sort_order, level, status, is_system, created_by, created_time)
SELECT 'youanshang', parent_node.id, '概括对策', 'kp_sl_summarize_measure', 'knowledge_point', 4, parent_node.level + 1, TRUE, FALSE, 1, NOW()
FROM parent_node
WHERE NOT EXISTS (SELECT 1 FROM sys_category WHERE code = 'kp_sl_summarize_measure');

WITH parent_node AS (
    SELECT id, level FROM sys_category WHERE app_code = 'youanshang' AND type = 'knowledge_point' AND code = 'kp_sl_summarize'
)
INSERT INTO sys_category (app_code, parent_id, name, code, type, sort_order, level, status, is_system, created_by, created_time)
SELECT 'youanshang', parent_node.id, '概括特征/现状', 'kp_sl_summarize_feature', 'knowledge_point', 5, parent_node.level + 1, TRUE, FALSE, 1, NOW()
FROM parent_node
WHERE NOT EXISTS (SELECT 1 FROM sys_category WHERE code = 'kp_sl_summarize_feature');

WITH parent_node AS (
    SELECT id, level FROM sys_category WHERE app_code = 'youanshang' AND type = 'knowledge_point' AND code = 'kp_shenlun'
)
INSERT INTO sys_category (app_code, parent_id, name, code, type, sort_order, level, status, is_system, created_by, created_time)
SELECT 'youanshang', parent_node.id, '综合分析题', 'kp_sl_analysis', 'knowledge_point', 3, parent_node.level + 1, TRUE, FALSE, 1, NOW()
FROM parent_node
WHERE NOT EXISTS (SELECT 1 FROM sys_category WHERE code = 'kp_sl_analysis');

WITH parent_node AS (
    SELECT id, level FROM sys_category WHERE app_code = 'youanshang' AND type = 'knowledge_point' AND code = 'kp_sl_analysis'
)
INSERT INTO sys_category (app_code, parent_id, name, code, type, sort_order, level, status, is_system, created_by, created_time)
SELECT 'youanshang', parent_node.id, '词句阐释', 'kp_sl_analysis_word', 'knowledge_point', 1, parent_node.level + 1, TRUE, FALSE, 1, NOW()
FROM parent_node
WHERE NOT EXISTS (SELECT 1 FROM sys_category WHERE code = 'kp_sl_analysis_word');

WITH parent_node AS (
    SELECT id, level FROM sys_category WHERE app_code = 'youanshang' AND type = 'knowledge_point' AND code = 'kp_sl_analysis'
)
INSERT INTO sys_category (app_code, parent_id, name, code, type, sort_order, level, status, is_system, created_by, created_time)
SELECT 'youanshang', parent_node.id, '评价分析', 'kp_sl_analysis_evaluate', 'knowledge_point', 2, parent_node.level + 1, TRUE, FALSE, 1, NOW()
FROM parent_node
WHERE NOT EXISTS (SELECT 1 FROM sys_category WHERE code = 'kp_sl_analysis_evaluate');

WITH parent_node AS (
    SELECT id, level FROM sys_category WHERE app_code = 'youanshang' AND type = 'knowledge_point' AND code = 'kp_sl_analysis'
)
INSERT INTO sys_category (app_code, parent_id, name, code, type, sort_order, level, status, is_system, created_by, created_time)
SELECT 'youanshang', parent_node.id, '比较分析', 'kp_sl_analysis_compare', 'knowledge_point', 3, parent_node.level + 1, TRUE, FALSE, 1, NOW()
FROM parent_node
WHERE NOT EXISTS (SELECT 1 FROM sys_category WHERE code = 'kp_sl_analysis_compare');

WITH parent_node AS (
    SELECT id, level FROM sys_category WHERE app_code = 'youanshang' AND type = 'knowledge_point' AND code = 'kp_sl_analysis'
)
INSERT INTO sys_category (app_code, parent_id, name, code, type, sort_order, level, status, is_system, created_by, created_time)
SELECT 'youanshang', parent_node.id, '原因分析', 'kp_sl_analysis_reason', 'knowledge_point', 4, parent_node.level + 1, TRUE, FALSE, 1, NOW()
FROM parent_node
WHERE NOT EXISTS (SELECT 1 FROM sys_category WHERE code = 'kp_sl_analysis_reason');

WITH parent_node AS (
    SELECT id, level FROM sys_category WHERE app_code = 'youanshang' AND type = 'knowledge_point' AND code = 'kp_sl_analysis'
)
INSERT INTO sys_category (app_code, parent_id, name, code, type, sort_order, level, status, is_system, created_by, created_time)
SELECT 'youanshang', parent_node.id, '启示分析', 'kp_sl_analysis_enlighten', 'knowledge_point', 5, parent_node.level + 1, TRUE, FALSE, 1, NOW()
FROM parent_node
WHERE NOT EXISTS (SELECT 1 FROM sys_category WHERE code = 'kp_sl_analysis_enlighten');

WITH parent_node AS (
    SELECT id, level FROM sys_category WHERE app_code = 'youanshang' AND type = 'knowledge_point' AND code = 'kp_shenlun'
)
INSERT INTO sys_category (app_code, parent_id, name, code, type, sort_order, level, status, is_system, created_by, created_time)
SELECT 'youanshang', parent_node.id, '提出对策题', 'kp_sl_solution', 'knowledge_point', 4, parent_node.level + 1, TRUE, FALSE, 1, NOW()
FROM parent_node
WHERE NOT EXISTS (SELECT 1 FROM sys_category WHERE code = 'kp_sl_solution');

WITH parent_node AS (
    SELECT id, level FROM sys_category WHERE app_code = 'youanshang' AND type = 'knowledge_point' AND code = 'kp_sl_solution'
)
INSERT INTO sys_category (app_code, parent_id, name, code, type, sort_order, level, status, is_system, created_by, created_time)
SELECT 'youanshang', parent_node.id, '单一对策题', 'kp_sl_solution_single', 'knowledge_point', 1, parent_node.level + 1, TRUE, FALSE, 1, NOW()
FROM parent_node
WHERE NOT EXISTS (SELECT 1 FROM sys_category WHERE code = 'kp_sl_solution_single');

WITH parent_node AS (
    SELECT id, level FROM sys_category WHERE app_code = 'youanshang' AND type = 'knowledge_point' AND code = 'kp_sl_solution'
)
INSERT INTO sys_category (app_code, parent_id, name, code, type, sort_order, level, status, is_system, created_by, created_time)
SELECT 'youanshang', parent_node.id, '复合对策题', 'kp_sl_solution_complex', 'knowledge_point', 2, parent_node.level + 1, TRUE, FALSE, 1, NOW()
FROM parent_node
WHERE NOT EXISTS (SELECT 1 FROM sys_category WHERE code = 'kp_sl_solution_complex');

WITH parent_node AS (
    SELECT id, level FROM sys_category WHERE app_code = 'youanshang' AND type = 'knowledge_point' AND code = 'kp_sl_solution'
)
INSERT INTO sys_category (app_code, parent_id, name, code, type, sort_order, level, status, is_system, created_by, created_time)
SELECT 'youanshang', parent_node.id, '对策来源提取', 'kp_sl_solution_source', 'knowledge_point', 3, parent_node.level + 1, TRUE, FALSE, 1, NOW()
FROM parent_node
WHERE NOT EXISTS (SELECT 1 FROM sys_category WHERE code = 'kp_sl_solution_source');

WITH parent_node AS (
    SELECT id, level FROM sys_category WHERE app_code = 'youanshang' AND type = 'knowledge_point' AND code = 'kp_sl_solution'
)
INSERT INTO sys_category (app_code, parent_id, name, code, type, sort_order, level, status, is_system, created_by, created_time)
SELECT 'youanshang', parent_node.id, '对策扩充与可行性', 'kp_sl_solution_expand', 'knowledge_point', 4, parent_node.level + 1, TRUE, FALSE, 1, NOW()
FROM parent_node
WHERE NOT EXISTS (SELECT 1 FROM sys_category WHERE code = 'kp_sl_solution_expand');

WITH parent_node AS (
    SELECT id, level FROM sys_category WHERE app_code = 'youanshang' AND type = 'knowledge_point' AND code = 'kp_shenlun'
)
INSERT INTO sys_category (app_code, parent_id, name, code, type, sort_order, level, status, is_system, created_by, created_time)
SELECT 'youanshang', parent_node.id, '贯彻执行题(公文)', 'kp_sl_document', 'knowledge_point', 5, parent_node.level + 1, TRUE, FALSE, 1, NOW()
FROM parent_node
WHERE NOT EXISTS (SELECT 1 FROM sys_category WHERE code = 'kp_sl_document');

WITH parent_node AS (
    SELECT id, level FROM sys_category WHERE app_code = 'youanshang' AND type = 'knowledge_point' AND code = 'kp_sl_document'
)
INSERT INTO sys_category (app_code, parent_id, name, code, type, sort_order, level, status, is_system, created_by, created_time)
SELECT 'youanshang', parent_node.id, '公文格式规范', 'kp_sl_doc_format', 'knowledge_point', 1, parent_node.level + 1, TRUE, FALSE, 1, NOW()
FROM parent_node
WHERE NOT EXISTS (SELECT 1 FROM sys_category WHERE code = 'kp_sl_doc_format');

WITH parent_node AS (
    SELECT id, level FROM sys_category WHERE app_code = 'youanshang' AND type = 'knowledge_point' AND code = 'kp_sl_document'
)
INSERT INTO sys_category (app_code, parent_id, name, code, type, sort_order, level, status, is_system, created_by, created_time)
SELECT 'youanshang', parent_node.id, '宣传演讲类', 'kp_sl_doc_speech', 'knowledge_point', 2, parent_node.level + 1, TRUE, FALSE, 1, NOW()
FROM parent_node
WHERE NOT EXISTS (SELECT 1 FROM sys_category WHERE code = 'kp_sl_doc_speech');

WITH parent_node AS (
    SELECT id, level FROM sys_category WHERE app_code = 'youanshang' AND type = 'knowledge_point' AND code = 'kp_sl_document'
)
INSERT INTO sys_category (app_code, parent_id, name, code, type, sort_order, level, status, is_system, created_by, created_time)
SELECT 'youanshang', parent_node.id, '总结汇报类', 'kp_sl_doc_summary', 'knowledge_point', 3, parent_node.level + 1, TRUE, FALSE, 1, NOW()
FROM parent_node
WHERE NOT EXISTS (SELECT 1 FROM sys_category WHERE code = 'kp_sl_doc_summary');

WITH parent_node AS (
    SELECT id, level FROM sys_category WHERE app_code = 'youanshang' AND type = 'knowledge_point' AND code = 'kp_sl_document'
)
INSERT INTO sys_category (app_code, parent_id, name, code, type, sort_order, level, status, is_system, created_by, created_time)
SELECT 'youanshang', parent_node.id, '方案指导类', 'kp_sl_doc_plan', 'knowledge_point', 4, parent_node.level + 1, TRUE, FALSE, 1, NOW()
FROM parent_node
WHERE NOT EXISTS (SELECT 1 FROM sys_category WHERE code = 'kp_sl_doc_plan');

WITH parent_node AS (
    SELECT id, level FROM sys_category WHERE app_code = 'youanshang' AND type = 'knowledge_point' AND code = 'kp_sl_document'
)
INSERT INTO sys_category (app_code, parent_id, name, code, type, sort_order, level, status, is_system, created_by, created_time)
SELECT 'youanshang', parent_node.id, '评论短评类', 'kp_sl_doc_comment', 'knowledge_point', 5, parent_node.level + 1, TRUE, FALSE, 1, NOW()
FROM parent_node
WHERE NOT EXISTS (SELECT 1 FROM sys_category WHERE code = 'kp_sl_doc_comment');

WITH parent_node AS (
    SELECT id, level FROM sys_category WHERE app_code = 'youanshang' AND type = 'knowledge_point' AND code = 'kp_shenlun'
)
INSERT INTO sys_category (app_code, parent_id, name, code, type, sort_order, level, status, is_system, created_by, created_time)
SELECT 'youanshang', parent_node.id, '文章写作题', 'kp_sl_essay', 'knowledge_point', 6, parent_node.level + 1, TRUE, FALSE, 1, NOW()
FROM parent_node
WHERE NOT EXISTS (SELECT 1 FROM sys_category WHERE code = 'kp_sl_essay');

WITH parent_node AS (
    SELECT id, level FROM sys_category WHERE app_code = 'youanshang' AND type = 'knowledge_point' AND code = 'kp_sl_essay'
)
INSERT INTO sys_category (app_code, parent_id, name, code, type, sort_order, level, status, is_system, created_by, created_time)
SELECT 'youanshang', parent_node.id, '立意与破题', 'kp_sl_essay_topic', 'knowledge_point', 1, parent_node.level + 1, TRUE, FALSE, 1, NOW()
FROM parent_node
WHERE NOT EXISTS (SELECT 1 FROM sys_category WHERE code = 'kp_sl_essay_topic');

WITH parent_node AS (
    SELECT id, level FROM sys_category WHERE app_code = 'youanshang' AND type = 'knowledge_point' AND code = 'kp_sl_essay'
)
INSERT INTO sys_category (app_code, parent_id, name, code, type, sort_order, level, status, is_system, created_by, created_time)
SELECT 'youanshang', parent_node.id, '拟定标题', 'kp_sl_essay_title', 'knowledge_point', 2, parent_node.level + 1, TRUE, FALSE, 1, NOW()
FROM parent_node
WHERE NOT EXISTS (SELECT 1 FROM sys_category WHERE code = 'kp_sl_essay_title');

WITH parent_node AS (
    SELECT id, level FROM sys_category WHERE app_code = 'youanshang' AND type = 'knowledge_point' AND code = 'kp_sl_essay'
)
INSERT INTO sys_category (app_code, parent_id, name, code, type, sort_order, level, status, is_system, created_by, created_time)
SELECT 'youanshang', parent_node.id, '行文结构框架', 'kp_sl_essay_structure', 'knowledge_point', 3, parent_node.level + 1, TRUE, FALSE, 1, NOW()
FROM parent_node
WHERE NOT EXISTS (SELECT 1 FROM sys_category WHERE code = 'kp_sl_essay_structure');

WITH parent_node AS (
    SELECT id, level FROM sys_category WHERE app_code = 'youanshang' AND type = 'knowledge_point' AND code = 'kp_sl_essay'
)
INSERT INTO sys_category (app_code, parent_id, name, code, type, sort_order, level, status, is_system, created_by, created_time)
SELECT 'youanshang', parent_node.id, '凤头起笔', 'kp_sl_essay_opening', 'knowledge_point', 4, parent_node.level + 1, TRUE, FALSE, 1, NOW()
FROM parent_node
WHERE NOT EXISTS (SELECT 1 FROM sys_category WHERE code = 'kp_sl_essay_opening');

WITH parent_node AS (
    SELECT id, level FROM sys_category WHERE app_code = 'youanshang' AND type = 'knowledge_point' AND code = 'kp_sl_essay'
)
INSERT INTO sys_category (app_code, parent_id, name, code, type, sort_order, level, status, is_system, created_by, created_time)
SELECT 'youanshang', parent_node.id, '论证与素材运用', 'kp_sl_essay_argument', 'knowledge_point', 5, parent_node.level + 1, TRUE, FALSE, 1, NOW()
FROM parent_node
WHERE NOT EXISTS (SELECT 1 FROM sys_category WHERE code = 'kp_sl_essay_argument');

WITH parent_node AS (
    SELECT id, level FROM sys_category WHERE app_code = 'youanshang' AND type = 'knowledge_point' AND code = 'kp_sl_essay'
)
INSERT INTO sys_category (app_code, parent_id, name, code, type, sort_order, level, status, is_system, created_by, created_time)
SELECT 'youanshang', parent_node.id, '豹尾收篇', 'kp_sl_essay_ending', 'knowledge_point', 6, parent_node.level + 1, TRUE, FALSE, 1, NOW()
FROM parent_node
WHERE NOT EXISTS (SELECT 1 FROM sys_category WHERE code = 'kp_sl_essay_ending');

WITH parent_node AS (
    SELECT id, level FROM sys_category WHERE app_code = 'youanshang' AND type = 'knowledge_point' AND code = 'kp_mianshi'
)
INSERT INTO sys_category (app_code, parent_id, name, code, type, sort_order, level, status, is_system, created_by, created_time)
SELECT 'youanshang', parent_node.id, '面试基础素养', 'kp_ms_basic', 'knowledge_point', 1, parent_node.level + 1, TRUE, FALSE, 1, NOW()
FROM parent_node
WHERE NOT EXISTS (SELECT 1 FROM sys_category WHERE code = 'kp_ms_basic');

WITH parent_node AS (
    SELECT id, level FROM sys_category WHERE app_code = 'youanshang' AND type = 'knowledge_point' AND code = 'kp_ms_basic'
)
INSERT INTO sys_category (app_code, parent_id, name, code, type, sort_order, level, status, is_system, created_by, created_time)
SELECT 'youanshang', parent_node.id, '礼仪与气场', 'kp_ms_basic_etiquette', 'knowledge_point', 1, parent_node.level + 1, TRUE, FALSE, 1, NOW()
FROM parent_node
WHERE NOT EXISTS (SELECT 1 FROM sys_category WHERE code = 'kp_ms_basic_etiquette');

WITH parent_node AS (
    SELECT id, level FROM sys_category WHERE app_code = 'youanshang' AND type = 'knowledge_point' AND code = 'kp_ms_basic'
)
INSERT INTO sys_category (app_code, parent_id, name, code, type, sort_order, level, status, is_system, created_by, created_time)
SELECT 'youanshang', parent_node.id, '语言表达与流畅度', 'kp_ms_basic_expression', 'knowledge_point', 2, parent_node.level + 1, TRUE, FALSE, 1, NOW()
FROM parent_node
WHERE NOT EXISTS (SELECT 1 FROM sys_category WHERE code = 'kp_ms_basic_expression');

WITH parent_node AS (
    SELECT id, level FROM sys_category WHERE app_code = 'youanshang' AND type = 'knowledge_point' AND code = 'kp_ms_basic'
)
INSERT INTO sys_category (app_code, parent_id, name, code, type, sort_order, level, status, is_system, created_by, created_time)
SELECT 'youanshang', parent_node.id, '逻辑思维框架', 'kp_ms_basic_logic', 'knowledge_point', 3, parent_node.level + 1, TRUE, FALSE, 1, NOW()
FROM parent_node
WHERE NOT EXISTS (SELECT 1 FROM sys_category WHERE code = 'kp_ms_basic_logic');

WITH parent_node AS (
    SELECT id, level FROM sys_category WHERE app_code = 'youanshang' AND type = 'knowledge_point' AND code = 'kp_mianshi'
)
INSERT INTO sys_category (app_code, parent_id, name, code, type, sort_order, level, status, is_system, created_by, created_time)
SELECT 'youanshang', parent_node.id, '综合分析类', 'kp_ms_analysis', 'knowledge_point', 2, parent_node.level + 1, TRUE, FALSE, 1, NOW()
FROM parent_node
WHERE NOT EXISTS (SELECT 1 FROM sys_category WHERE code = 'kp_ms_analysis');

WITH parent_node AS (
    SELECT id, level FROM sys_category WHERE app_code = 'youanshang' AND type = 'knowledge_point' AND code = 'kp_ms_analysis'
)
INSERT INTO sys_category (app_code, parent_id, name, code, type, sort_order, level, status, is_system, created_by, created_time)
SELECT 'youanshang', parent_node.id, '社会现象类', 'kp_ms_ana_phenomenon', 'knowledge_point', 1, parent_node.level + 1, TRUE, FALSE, 1, NOW()
FROM parent_node
WHERE NOT EXISTS (SELECT 1 FROM sys_category WHERE code = 'kp_ms_ana_phenomenon');

WITH parent_node AS (
    SELECT id, level FROM sys_category WHERE app_code = 'youanshang' AND type = 'knowledge_point' AND code = 'kp_ms_analysis'
)
INSERT INTO sys_category (app_code, parent_id, name, code, type, sort_order, level, status, is_system, created_by, created_time)
SELECT 'youanshang', parent_node.id, '政策理解类', 'kp_ms_ana_policy', 'knowledge_point', 2, parent_node.level + 1, TRUE, FALSE, 1, NOW()
FROM parent_node
WHERE NOT EXISTS (SELECT 1 FROM sys_category WHERE code = 'kp_ms_ana_policy');

WITH parent_node AS (
    SELECT id, level FROM sys_category WHERE app_code = 'youanshang' AND type = 'knowledge_point' AND code = 'kp_ms_analysis'
)
INSERT INTO sys_category (app_code, parent_id, name, code, type, sort_order, level, status, is_system, created_by, created_time)
SELECT 'youanshang', parent_node.id, '名言警句类', 'kp_ms_ana_quote', 'knowledge_point', 3, parent_node.level + 1, TRUE, FALSE, 1, NOW()
FROM parent_node
WHERE NOT EXISTS (SELECT 1 FROM sys_category WHERE code = 'kp_ms_ana_quote');

WITH parent_node AS (
    SELECT id, level FROM sys_category WHERE app_code = 'youanshang' AND type = 'knowledge_point' AND code = 'kp_ms_analysis'
)
INSERT INTO sys_category (app_code, parent_id, name, code, type, sort_order, level, status, is_system, created_by, created_time)
SELECT 'youanshang', parent_node.id, '哲理故事类', 'kp_ms_ana_story', 'knowledge_point', 4, parent_node.level + 1, TRUE, FALSE, 1, NOW()
FROM parent_node
WHERE NOT EXISTS (SELECT 1 FROM sys_category WHERE code = 'kp_ms_ana_story');

WITH parent_node AS (
    SELECT id, level FROM sys_category WHERE app_code = 'youanshang' AND type = 'knowledge_point' AND code = 'kp_ms_analysis'
)
INSERT INTO sys_category (app_code, parent_id, name, code, type, sort_order, level, status, is_system, created_by, created_time)
SELECT 'youanshang', parent_node.id, '漫画类', 'kp_ms_ana_comic', 'knowledge_point', 5, parent_node.level + 1, TRUE, FALSE, 1, NOW()
FROM parent_node
WHERE NOT EXISTS (SELECT 1 FROM sys_category WHERE code = 'kp_ms_ana_comic');

WITH parent_node AS (
    SELECT id, level FROM sys_category WHERE app_code = 'youanshang' AND type = 'knowledge_point' AND code = 'kp_mianshi'
)
INSERT INTO sys_category (app_code, parent_id, name, code, type, sort_order, level, status, is_system, created_by, created_time)
SELECT 'youanshang', parent_node.id, '计划组织类', 'kp_ms_organize', 'knowledge_point', 3, parent_node.level + 1, TRUE, FALSE, 1, NOW()
FROM parent_node
WHERE NOT EXISTS (SELECT 1 FROM sys_category WHERE code = 'kp_ms_organize');

WITH parent_node AS (
    SELECT id, level FROM sys_category WHERE app_code = 'youanshang' AND type = 'knowledge_point' AND code = 'kp_ms_organize'
)
INSERT INTO sys_category (app_code, parent_id, name, code, type, sort_order, level, status, is_system, created_by, created_time)
SELECT 'youanshang', parent_node.id, '调研考察类', 'kp_ms_org_research', 'knowledge_point', 1, parent_node.level + 1, TRUE, FALSE, 1, NOW()
FROM parent_node
WHERE NOT EXISTS (SELECT 1 FROM sys_category WHERE code = 'kp_ms_org_research');

WITH parent_node AS (
    SELECT id, level FROM sys_category WHERE app_code = 'youanshang' AND type = 'knowledge_point' AND code = 'kp_ms_organize'
)
INSERT INTO sys_category (app_code, parent_id, name, code, type, sort_order, level, status, is_system, created_by, created_time)
SELECT 'youanshang', parent_node.id, '会议活动类', 'kp_ms_org_meeting', 'knowledge_point', 2, parent_node.level + 1, TRUE, FALSE, 1, NOW()
FROM parent_node
WHERE NOT EXISTS (SELECT 1 FROM sys_category WHERE code = 'kp_ms_org_meeting');

WITH parent_node AS (
    SELECT id, level FROM sys_category WHERE app_code = 'youanshang' AND type = 'knowledge_point' AND code = 'kp_ms_organize'
)
INSERT INTO sys_category (app_code, parent_id, name, code, type, sort_order, level, status, is_system, created_by, created_time)
SELECT 'youanshang', parent_node.id, '宣传培训类', 'kp_ms_org_promo', 'knowledge_point', 3, parent_node.level + 1, TRUE, FALSE, 1, NOW()
FROM parent_node
WHERE NOT EXISTS (SELECT 1 FROM sys_category WHERE code = 'kp_ms_org_promo');

WITH parent_node AS (
    SELECT id, level FROM sys_category WHERE app_code = 'youanshang' AND type = 'knowledge_point' AND code = 'kp_ms_organize'
)
INSERT INTO sys_category (app_code, parent_id, name, code, type, sort_order, level, status, is_system, created_by, created_time)
SELECT 'youanshang', parent_node.id, '接待安排类', 'kp_ms_org_reception', 'knowledge_point', 4, parent_node.level + 1, TRUE, FALSE, 1, NOW()
FROM parent_node
WHERE NOT EXISTS (SELECT 1 FROM sys_category WHERE code = 'kp_ms_org_reception');

WITH parent_node AS (
    SELECT id, level FROM sys_category WHERE app_code = 'youanshang' AND type = 'knowledge_point' AND code = 'kp_mianshi'
)
INSERT INTO sys_category (app_code, parent_id, name, code, type, sort_order, level, status, is_system, created_by, created_time)
SELECT 'youanshang', parent_node.id, '应急应变类', 'kp_ms_emergency', 'knowledge_point', 4, parent_node.level + 1, TRUE, FALSE, 1, NOW()
FROM parent_node
WHERE NOT EXISTS (SELECT 1 FROM sys_category WHERE code = 'kp_ms_emergency');

WITH parent_node AS (
    SELECT id, level FROM sys_category WHERE app_code = 'youanshang' AND type = 'knowledge_point' AND code = 'kp_ms_emergency'
)
INSERT INTO sys_category (app_code, parent_id, name, code, type, sort_order, level, status, is_system, created_by, created_time)
SELECT 'youanshang', parent_node.id, '公共突发事件', 'kp_ms_emg_public', 'knowledge_point', 1, parent_node.level + 1, TRUE, FALSE, 1, NOW()
FROM parent_node
WHERE NOT EXISTS (SELECT 1 FROM sys_category WHERE code = 'kp_ms_emg_public');

WITH parent_node AS (
    SELECT id, level FROM sys_category WHERE app_code = 'youanshang' AND type = 'knowledge_point' AND code = 'kp_ms_emergency'
)
INSERT INTO sys_category (app_code, parent_id, name, code, type, sort_order, level, status, is_system, created_by, created_time)
SELECT 'youanshang', parent_node.id, '日常工作失误', 'kp_ms_emg_work', 'knowledge_point', 2, parent_node.level + 1, TRUE, FALSE, 1, NOW()
FROM parent_node
WHERE NOT EXISTS (SELECT 1 FROM sys_category WHERE code = 'kp_ms_emg_work');

WITH parent_node AS (
    SELECT id, level FROM sys_category WHERE app_code = 'youanshang' AND type = 'knowledge_point' AND code = 'kp_ms_emergency'
)
INSERT INTO sys_category (app_code, parent_id, name, code, type, sort_order, level, status, is_system, created_by, created_time)
SELECT 'youanshang', parent_node.id, '舆情危机处理', 'kp_ms_emg_media', 'knowledge_point', 3, parent_node.level + 1, TRUE, FALSE, 1, NOW()
FROM parent_node
WHERE NOT EXISTS (SELECT 1 FROM sys_category WHERE code = 'kp_ms_emg_media');

WITH parent_node AS (
    SELECT id, level FROM sys_category WHERE app_code = 'youanshang' AND type = 'knowledge_point' AND code = 'kp_ms_emergency'
)
INSERT INTO sys_category (app_code, parent_id, name, code, type, sort_order, level, status, is_system, created_by, created_time)
SELECT 'youanshang', parent_node.id, '群众上访/投诉', 'kp_ms_emg_complain', 'knowledge_point', 4, parent_node.level + 1, TRUE, FALSE, 1, NOW()
FROM parent_node
WHERE NOT EXISTS (SELECT 1 FROM sys_category WHERE code = 'kp_ms_emg_complain');

WITH parent_node AS (
    SELECT id, level FROM sys_category WHERE app_code = 'youanshang' AND type = 'knowledge_point' AND code = 'kp_mianshi'
)
INSERT INTO sys_category (app_code, parent_id, name, code, type, sort_order, level, status, is_system, created_by, created_time)
SELECT 'youanshang', parent_node.id, '人际交往意识与技巧', 'kp_ms_interpersonal', 'knowledge_point', 5, parent_node.level + 1, TRUE, FALSE, 1, NOW()
FROM parent_node
WHERE NOT EXISTS (SELECT 1 FROM sys_category WHERE code = 'kp_ms_interpersonal');

WITH parent_node AS (
    SELECT id, level FROM sys_category WHERE app_code = 'youanshang' AND type = 'knowledge_point' AND code = 'kp_ms_interpersonal'
)
INSERT INTO sys_category (app_code, parent_id, name, code, type, sort_order, level, status, is_system, created_by, created_time)
SELECT 'youanshang', parent_node.id, '与领导相处', 'kp_ms_ip_leader', 'knowledge_point', 1, parent_node.level + 1, TRUE, FALSE, 1, NOW()
FROM parent_node
WHERE NOT EXISTS (SELECT 1 FROM sys_category WHERE code = 'kp_ms_ip_leader');

WITH parent_node AS (
    SELECT id, level FROM sys_category WHERE app_code = 'youanshang' AND type = 'knowledge_point' AND code = 'kp_ms_interpersonal'
)
INSERT INTO sys_category (app_code, parent_id, name, code, type, sort_order, level, status, is_system, created_by, created_time)
SELECT 'youanshang', parent_node.id, '与同事相处', 'kp_ms_ip_colleague', 'knowledge_point', 2, parent_node.level + 1, TRUE, FALSE, 1, NOW()
FROM parent_node
WHERE NOT EXISTS (SELECT 1 FROM sys_category WHERE code = 'kp_ms_ip_colleague');

WITH parent_node AS (
    SELECT id, level FROM sys_category WHERE app_code = 'youanshang' AND type = 'knowledge_point' AND code = 'kp_ms_interpersonal'
)
INSERT INTO sys_category (app_code, parent_id, name, code, type, sort_order, level, status, is_system, created_by, created_time)
SELECT 'youanshang', parent_node.id, '与群众/服务对象', 'kp_ms_ip_masses', 'knowledge_point', 3, parent_node.level + 1, TRUE, FALSE, 1, NOW()
FROM parent_node
WHERE NOT EXISTS (SELECT 1 FROM sys_category WHERE code = 'kp_ms_ip_masses');

WITH parent_node AS (
    SELECT id, level FROM sys_category WHERE app_code = 'youanshang' AND type = 'knowledge_point' AND code = 'kp_ms_interpersonal'
)
INSERT INTO sys_category (app_code, parent_id, name, code, type, sort_order, level, status, is_system, created_by, created_time)
SELECT 'youanshang', parent_node.id, '与亲友', 'kp_ms_ip_family', 'knowledge_point', 4, parent_node.level + 1, TRUE, FALSE, 1, NOW()
FROM parent_node
WHERE NOT EXISTS (SELECT 1 FROM sys_category WHERE code = 'kp_ms_ip_family');

WITH parent_node AS (
    SELECT id, level FROM sys_category WHERE app_code = 'youanshang' AND type = 'knowledge_point' AND code = 'kp_mianshi'
)
INSERT INTO sys_category (app_code, parent_id, name, code, type, sort_order, level, status, is_system, created_by, created_time)
SELECT 'youanshang', parent_node.id, '自我认知与职位匹配', 'kp_ms_match', 'knowledge_point', 6, parent_node.level + 1, TRUE, FALSE, 1, NOW()
FROM parent_node
WHERE NOT EXISTS (SELECT 1 FROM sys_category WHERE code = 'kp_ms_match');

WITH parent_node AS (
    SELECT id, level FROM sys_category WHERE app_code = 'youanshang' AND type = 'knowledge_point' AND code = 'kp_ms_match'
)
INSERT INTO sys_category (app_code, parent_id, name, code, type, sort_order, level, status, is_system, created_by, created_time)
SELECT 'youanshang', parent_node.id, '自我介绍/求职动机', 'kp_ms_match_self', 'knowledge_point', 1, parent_node.level + 1, TRUE, FALSE, 1, NOW()
FROM parent_node
WHERE NOT EXISTS (SELECT 1 FROM sys_category WHERE code = 'kp_ms_match_self');

WITH parent_node AS (
    SELECT id, level FROM sys_category WHERE app_code = 'youanshang' AND type = 'knowledge_point' AND code = 'kp_ms_match'
)
INSERT INTO sys_category (app_code, parent_id, name, code, type, sort_order, level, status, is_system, created_by, created_time)
SELECT 'youanshang', parent_node.id, '职业规划', 'kp_ms_match_career', 'knowledge_point', 2, parent_node.level + 1, TRUE, FALSE, 1, NOW()
FROM parent_node
WHERE NOT EXISTS (SELECT 1 FROM sys_category WHERE code = 'kp_ms_match_career');

WITH parent_node AS (
    SELECT id, level FROM sys_category WHERE app_code = 'youanshang' AND type = 'knowledge_point' AND code = 'kp_ms_match'
)
INSERT INTO sys_category (app_code, parent_id, name, code, type, sort_order, level, status, is_system, created_by, created_time)
SELECT 'youanshang', parent_node.id, '压力抗挫测试', 'kp_ms_match_pressure', 'knowledge_point', 3, parent_node.level + 1, TRUE, FALSE, 1, NOW()
FROM parent_node
WHERE NOT EXISTS (SELECT 1 FROM sys_category WHERE code = 'kp_ms_match_pressure');

WITH parent_node AS (
    SELECT id, level FROM sys_category WHERE app_code = 'youanshang' AND type = 'knowledge_point' AND code = 'kp_mianshi'
)
INSERT INTO sys_category (app_code, parent_id, name, code, type, sort_order, level, status, is_system, created_by, created_time)
SELECT 'youanshang', parent_node.id, '特色新颖题型', 'kp_ms_novel', 'knowledge_point', 7, parent_node.level + 1, TRUE, FALSE, 1, NOW()
FROM parent_node
WHERE NOT EXISTS (SELECT 1 FROM sys_category WHERE code = 'kp_ms_novel');

WITH parent_node AS (
    SELECT id, level FROM sys_category WHERE app_code = 'youanshang' AND type = 'knowledge_point' AND code = 'kp_ms_novel'
)
INSERT INTO sys_category (app_code, parent_id, name, code, type, sort_order, level, status, is_system, created_by, created_time)
SELECT 'youanshang', parent_node.id, '情景模拟演讲', 'kp_ms_nov_speech', 'knowledge_point', 1, parent_node.level + 1, TRUE, FALSE, 1, NOW()
FROM parent_node
WHERE NOT EXISTS (SELECT 1 FROM sys_category WHERE code = 'kp_ms_nov_speech');

WITH parent_node AS (
    SELECT id, level FROM sys_category WHERE app_code = 'youanshang' AND type = 'knowledge_point' AND code = 'kp_ms_novel'
)
INSERT INTO sys_category (app_code, parent_id, name, code, type, sort_order, level, status, is_system, created_by, created_time)
SELECT 'youanshang', parent_node.id, '反驳/辩论题', 'kp_ms_nov_debate', 'knowledge_point', 2, parent_node.level + 1, TRUE, FALSE, 1, NOW()
FROM parent_node
WHERE NOT EXISTS (SELECT 1 FROM sys_category WHERE code = 'kp_ms_nov_debate');

WITH parent_node AS (
    SELECT id, level FROM sys_category WHERE app_code = 'youanshang' AND type = 'knowledge_point' AND code = 'kp_ms_novel'
)
INSERT INTO sys_category (app_code, parent_id, name, code, type, sort_order, level, status, is_system, created_by, created_time)
SELECT 'youanshang', parent_node.id, '微材料统筹排序', 'kp_ms_nov_sort', 'knowledge_point', 3, parent_node.level + 1, TRUE, FALSE, 1, NOW()
FROM parent_node
WHERE NOT EXISTS (SELECT 1 FROM sys_category WHERE code = 'kp_ms_nov_sort');
