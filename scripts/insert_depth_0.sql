INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_832366', '政治理论', 0, NULL, '/fenbi_832366', 1, 1, NOW();
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_783916', '常识判断', 0, NULL, '/fenbi_783916', 2, 1, NOW();
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_783917', '言语理解与表达', 0, NULL, '/fenbi_783917', 3, 1, NOW();
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_783918', '数量关系', 0, NULL, '/fenbi_783918', 4, 1, NOW();
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_783919', '判断推理', 0, NULL, '/fenbi_783919', 5, 1, NOW();
SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), 'fenbi_783920', '资料分析', 0, NULL, '/fenbi_783920', 6, 1, NOW();