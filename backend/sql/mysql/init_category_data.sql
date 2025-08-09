-- 分类数据初始化 SQL
-- 用于初始化系统分类数据，包括资源类型、领域和科目分类
-- 注意：如果需要清空现有数据，请取消注释下面一行
-- DELETE FROM yp_category;

-- 插入资源领域分类（一级分类，排序在前）
INSERT IGNORE INTO yp_category (name, code, description, category_type, parent_id, level, path, sort, status, is_system, created_by, created_time) VALUES
('教育', 'education', '教育领域', 'domain', NULL, 1, '/education', 1, 1, 1, 1, NOW()),
('科技', 'technology', '科技领域', 'domain', NULL, 1, '/technology', 2, 1, 1, 1, NOW()),
('影视', 'entertainment', '影视领域', 'domain', NULL, 1, '/entertainment', 3, 1, 1, 1, NOW());

-- 插入资源类型分类（一级分类，排序在后）
INSERT IGNORE INTO yp_category (name, code, description, category_type, parent_id, level, path, sort, status, is_system, created_by, created_time) VALUES
('课程', 'course', '课程资源类型', 'resource_type', NULL, 1, '/course', 10, 1, 1, 1, NOW()),
('电子书', 'ebook', '电子书资源类型', 'resource_type', NULL, 1, '/ebook', 11, 1, 1, 1, NOW()),
('笔记', 'note', '笔记资源类型', 'resource_type', NULL, 1, '/note', 12, 1, 1, 1, NOW()),
('软件', 'software', '软件资源类型', 'resource_type', NULL, 1, '/software', 13, 1, 1, 1, NOW()),
('真题', 'exam_paper', '真题资源类型', 'resource_type', NULL, 1, '/exam_paper', 14, 1, 1, 1, NOW());

-- 获取领域分类的 ID（用于插入子分类）
SET @education_id = (SELECT id FROM yp_category WHERE code = 'education');
SET @technology_id = (SELECT id FROM yp_category WHERE code = 'technology');
SET @entertainment_id = (SELECT id FROM yp_category WHERE code = 'entertainment');

-- 插入教育领域科目分类（二级分类）
INSERT IGNORE INTO yp_category (name, code, description, category_type, parent_id, level, path, sort, status, is_system, created_by, created_time) VALUES
('26考研英语', 'postgraduate_english', '26考研英语科目', 'subject', @education_id, 2, '/education/postgraduate_english', 1, 1, 1, 1, NOW()),
('26考研数学', 'postgraduate_math', '26考研数学科目', 'subject', @education_id, 2, '/education/postgraduate_math', 2, 1, 1, 1, NOW()),
('26考研政治', 'postgraduate_politics', '26考研政治科目', 'subject', @education_id, 2, '/education/postgraduate_politics', 3, 1, 1, 1, NOW()),
('26考研统考', 'postgraduate_unified', '26考研统考科目', 'subject', @education_id, 2, '/education/postgraduate_unified', 4, 1, 1, 1, NOW()),
('26考研非统考', 'postgraduate_non_unified', '26考研非统考科目', 'subject', @education_id, 2, '/education/postgraduate_non_unified', 5, 1, 1, 1, NOW());

-- 插入科技领域科目分类（二级分类）
INSERT IGNORE INTO yp_category (name, code, description, category_type, parent_id, level, path, sort, status, is_system, created_by, created_time) VALUES
('编程开发', 'programming', '编程开发科目', 'subject', @technology_id, 2, '/technology/programming', 1, 1, 1, 1, NOW()),
('人工智能', 'artificial_intelligence', '人工智能科目', 'subject', @technology_id, 2, '/technology/artificial_intelligence', 2, 1, 1, 1, NOW()),
('数据科学', 'data_science', '数据科学科目', 'subject', @technology_id, 2, '/technology/data_science', 3, 1, 1, 1, NOW()),
('网络安全', 'cybersecurity', '网络安全科目', 'subject', @technology_id, 2, '/technology/cybersecurity', 4, 1, 1, 1, NOW()),
('云计算', 'cloud_computing', '云计算科目', 'subject', @technology_id, 2, '/technology/cloud_computing', 5, 1, 1, 1, NOW());

-- 插入影视领域科目分类（二级分类）
INSERT IGNORE INTO yp_category (name, code, description, category_type, parent_id, level, path, sort, status, is_system, created_by, created_time) VALUES
('电影', 'movie', '电影科目', 'subject', @entertainment_id, 2, '/entertainment/movie', 1, 1, 1, 1, NOW()),
('短剧', 'short_drama', '短剧科目', 'subject', @entertainment_id, 2, '/entertainment/short_drama', 2, 1, 1, 1, NOW()),
('电视剧', 'tv_series', '电视剧科目', 'subject', @entertainment_id, 2, '/entertainment/tv_series', 3, 1, 1, 1, NOW()),
('综艺', 'variety_show', '综艺科目', 'subject', @entertainment_id, 2, '/entertainment/variety_show', 4, 1, 1, 1, NOW());

-- 执行完成说明
-- 此脚本已完成以下分类数据的初始化：
-- 1. 资源类型分类：课程、电子书、笔记、软件、真题
-- 2. 领域分类：教育、科技、影视
-- 3. 科目分类：各领域下的具体科目
-- 
-- 注意事项：
-- - 使用 INSERT IGNORE 避免重复插入
-- - 所有分类都标记为系统分类（is_system=1）
-- - created_by 设置为 1（假设为系统管理员ID）
-- - 可根据实际需求调整分类内容和层级关系 