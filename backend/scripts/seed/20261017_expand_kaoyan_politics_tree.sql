-- ==========================================================================
-- 考研政治 52 个二级章节与 153 个三级小节增量迁移脚本
-- 架构: 科目(depth=1) -> 章节(depth=2) -> 小节(depth=3)
-- ==========================================================================
DO $$
DECLARE
    v_system_id BIGINT;
BEGIN
    SELECT id INTO v_system_id FROM fba.qbank_v2_knowledge_system WHERE code = 'kaoyan_politics' AND version = 'kaoyan' AND deleted = 0 LIMIT 1;
    IF v_system_id IS NULL THEN
        RAISE EXCEPTION '未找到 code=% version=% 的知识体系，请先初始化考研政治根体系', 'kaoyan_politics', 'kaoyan';
    END IF;

    -- 1. 批量插入二级节点（章节，52 个）
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_my_ch00', '导论 马克思主义是关于无产阶级和人类解放的科学', p.id, NULL, 2, 0, '马克思主义的定义、创立发展、鲜明特征与当代价值', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kaoyan_politics_mayuan' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_my_ch00' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_my_ch01', '第一章 世界的物质性及发展规律', p.id, NULL, 2, 1, '辩证唯物论与唯物辩证法核心内容，对立统一规律等', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kaoyan_politics_mayuan' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_my_ch01' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_my_ch02', '第二章 实践与认识及其发展规律', p.id, NULL, 2, 2, '认识论核心，实践与认识的辩证运动、真理与价值', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kaoyan_politics_mayuan' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_my_ch02' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_my_ch03', '第三章 人类社会及其发展规律', p.id, NULL, 2, 3, '唯物史观，社会基本矛盾、历史发展动力、人民群众历史作用', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kaoyan_politics_mayuan' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_my_ch03' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_my_ch04', '第四章 资本主义的本质及规律', p.id, NULL, 2, 4, '政治经济学基础，商品经济、劳动价值论与剩余价值理论', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kaoyan_politics_mayuan' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_my_ch04' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_my_ch05', '第五章 资本主义的发展及其趋势', p.id, NULL, 2, 5, '垄断资本主义、经济全球化与当代资本主义新变化', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kaoyan_politics_mayuan' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_my_ch05' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_my_ch06', '第六章 社会主义的发展及其规律', p.id, NULL, 2, 6, '科学社会主义，五百年历程、基本原则与中国实践', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kaoyan_politics_mayuan' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_my_ch06' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_my_ch07', '第七章 共产主义崇高理想及其最终实现', p.id, NULL, 2, 7, '共产主义社会基本特征、历史必然性与崇高理想', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kaoyan_politics_mayuan' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_my_ch07' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_mzt_ch00', '导论 马克思主义中国化时代化的历史进程与理论成果', p.id, NULL, 2, 0, '马克思主义中国化时代化的提出、内涵、进程与理论成果', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kaoyan_politics_maozhongte' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_mzt_ch00' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_mzt_ch01', '第一章 毛泽东思想及其历史地位', p.id, NULL, 2, 1, '毛泽东思想形成发展、主要内容、活的灵魂与历史地位', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kaoyan_politics_maozhongte' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_mzt_ch01' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_mzt_ch02', '第二章 新民主主义革命理论', p.id, NULL, 2, 2, '总路线、基本纲领、革命道路、三大法宝', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kaoyan_politics_maozhongte' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_mzt_ch02' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_mzt_ch03', '第三章 社会主义改造理论', p.id, NULL, 2, 3, '过渡时期总路线、三大改造与社会主义基本制度确立', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kaoyan_politics_maozhongte' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_mzt_ch03' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_mzt_ch04', '第四章 社会主义建设道路初步探索的理论成果', p.id, NULL, 2, 4, '《论十大关系》、正确处理人民内部矛盾、中国工业化道路', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kaoyan_politics_maozhongte' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_mzt_ch04' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_mzt_ch05', '第五章 中国特色社会主义理论体系的形成发展', p.id, NULL, 2, 5, '中国特色社会主义理论体系形成发展的历史条件与历程', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kaoyan_politics_maozhongte' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_mzt_ch05' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_mzt_ch06', '第六章 邓小平理论', p.id, NULL, 2, 6, '首要基本问题与精髓、社会主义初级阶段、改革开放、市场经济理论', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kaoyan_politics_maozhongte' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_mzt_ch06' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_mzt_ch07', '第七章 “三个代表”重要思想', p.id, NULL, 2, 7, '三个代表核心观点、先进生产力/文化/人民根本利益、历史地位', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kaoyan_politics_maozhongte' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_mzt_ch07' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_mzt_ch08', '第八章 科学发展观', p.id, NULL, 2, 8, '科学发展观的科学内涵、精神实质与主要内容', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kaoyan_politics_maozhongte' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_mzt_ch08' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_xsx_ch00', '导论 习近平新时代中国特色社会主义思想概论', p.id, NULL, 2, 0, '新思想的创立背景、时代之问、系统科学体系与重大飞跃', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kaoyan_politics_xinshixiang' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_xsx_ch00' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_xsx_ch01', '第一章 新时代坚持和发展中国特色社会主义', p.id, NULL, 2, 1, '社会主要矛盾变化、总任务与四个自信', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kaoyan_politics_xinshixiang' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_xsx_ch01' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_xsx_ch02', '第二章 以中国式现代化全面推进中华民族伟大复兴', p.id, NULL, 2, 2, '中国式现代化的中国特色、本质要求与重大原则', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kaoyan_politics_xinshixiang' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_xsx_ch02' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_xsx_ch03', '第三章 坚持党的全面领导', p.id, NULL, 2, 3, '党的领导是最本质特征和最大优势，坚持党对一切工作的领导', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kaoyan_politics_xinshixiang' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_xsx_ch03' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_xsx_ch04', '第四章 坚持以人民为中心', p.id, NULL, 2, 4, '江山就是人民，人民就是江山，扎实推进共同富裕', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kaoyan_politics_xinshixiang' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_xsx_ch04' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_xsx_ch05', '第五章 全面深化改革开放', p.id, NULL, 2, 5, '改革开放关键一招、全面深化改革总目标、更高水平对外开放', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kaoyan_politics_xinshixiang' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_xsx_ch05' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_xsx_ch06', '第六章 推动高质量发展', p.id, NULL, 2, 6, '新发展理念、新发展格局、发展新质生产力与现代化经济体系', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kaoyan_politics_xinshixiang' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_xsx_ch06' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_xsx_ch07', '第七章 社会主义现代化建设的教育、科技、人才战略', p.id, NULL, 2, 7, '教育优先、高水平科技自立自强、人才强国战略', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kaoyan_politics_xinshixiang' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_xsx_ch07' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_xsx_ch08', '第八章 发展全过程人民民主', p.id, NULL, 2, 8, '全过程人民民主本质属性、当家作主制度体系与爱国统一战线', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kaoyan_politics_xinshixiang' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_xsx_ch08' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_xsx_ch09', '第九章 全面依法治国', p.id, NULL, 2, 9, '习近平法治思想、中国特色社会主义法治道路与法治中国建设', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kaoyan_politics_xinshixiang' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_xsx_ch09' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_xsx_ch10', '第十章 建设社会主义文化强国', p.id, NULL, 2, 10, '意识形态领导权、社会主义核心价值观、繁荣文化事业文化产业', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kaoyan_politics_xinshixiang' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_xsx_ch10' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_xsx_ch11', '第十一章 以保障和改善民生为重点加强社会建设', p.id, NULL, 2, 11, '提高人民生活品质、社会保障、共建共治共享社会治理', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kaoyan_politics_xinshixiang' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_xsx_ch11' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_xsx_ch12', '第十二章 建设社会主义生态文明', p.id, NULL, 2, 12, '绿水青山就是金山银山、人与自然和谐共生、美丽中国建设', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kaoyan_politics_xinshixiang' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_xsx_ch12' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_xsx_ch13', '第十三章 维护和塑造国家安全', p.id, NULL, 2, 13, '贯彻总体国家安全观、国家安全体系与能力现代化', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kaoyan_politics_xinshixiang' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_xsx_ch13' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_xsx_ch14', '第十四章 建设巩固国防和强大人民军队', p.id, NULL, 2, 14, '强军目标、政治建军/改革强军/科技强军/人才强军/依法治军', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kaoyan_politics_xinshixiang' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_xsx_ch14' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_xsx_ch15', '第十五章 坚持“一国两制”和推进祖国完全统一', p.id, NULL, 2, 15, '一国两制方针、港澳长期繁荣稳定与解决台湾问题实现祖国完全统一', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kaoyan_politics_xinshixiang' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_xsx_ch15' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_xsx_ch16', '第十六章 中国特色大国外交和推动构建人类命运共同体', p.id, NULL, 2, 16, '和平发展道路、人类命运共同体、三大全球倡议与全球治理', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kaoyan_politics_xinshixiang' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_xsx_ch16' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_xsx_ch17', '第十七章 全面从严治党', p.id, NULL, 2, 17, '勇于自我革命、健全全面从严治党体系、反腐败斗争', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kaoyan_politics_xinshixiang' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_xsx_ch17' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_sg_ch00', '导言 中国近现代史纲要', p.id, NULL, 2, 0, '中国近现代史综述、历史发展主线与三个选择', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kaoyan_politics_shigang' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_sg_ch00' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_sg_ch01', '第一章 进入近代后中华民族的磨难与抗争', p.id, NULL, 2, 1, '鸦片战争、半殖民地半封建社会、列强侵略与反侵略斗争', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kaoyan_politics_shigang' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_sg_ch01' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_sg_ch02', '第二章 不同社会力量对国家出路的早期探索', p.id, NULL, 2, 2, '太平天国农民起义、洋务运动、戊戌维新运动', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kaoyan_politics_shigang' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_sg_ch02' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_sg_ch03', '第三章 辛亥革命与君主专制制度的终结', p.id, NULL, 2, 3, '孙中山与同盟会、三民主义、中华民国建立与北洋军阀统治', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kaoyan_politics_shigang' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_sg_ch03' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_sg_ch04', '第四章 中国共产党成立和中国革命新局面', p.id, NULL, 2, 4, '新文化运动、五四运动、中国共产党诞生、大革命', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kaoyan_politics_shigang' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_sg_ch04' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_sg_ch05', '第五章 中国革命的新道路', p.id, NULL, 2, 5, '井冈山革命根据地、农村包围城市道路、遵义会议与长征胜利', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kaoyan_politics_shigang' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_sg_ch05' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_sg_ch06', '第六章 中华民族的抗日战争', p.id, NULL, 2, 6, '抗日民族统一战线、正面战场与敌后战场、中流砥柱与抗战胜利', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kaoyan_politics_shigang' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_sg_ch06' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_sg_ch07', '第七章 为建立新中国而奋斗', p.id, NULL, 2, 7, '解放战争、战略进攻、第二条战线、新中国筹备建立', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kaoyan_politics_shigang' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_sg_ch07' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_sg_ch08', '第八章 中华人民共和国的成立与中国社会主义建设道路的探索', p.id, NULL, 2, 8, '新中国成立意义、政权巩固、三大改造、八大良好开局与探索曲折', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kaoyan_politics_shigang' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_sg_ch08' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_sg_ch09', '第九章 改革开放与中国特色社会主义的开创和发展', p.id, NULL, 2, 9, '十一届三中全会、农村改革、特区建立、南方谈话、入世与小康社会', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kaoyan_politics_shigang' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_sg_ch09' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_sg_ch10', '第十章 中国特色社会主义进入新时代', p.id, NULL, 2, 10, '新时代的历史性成就与历史性变革、开启现代化强国建设新征程', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kaoyan_politics_shigang' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_sg_ch10' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_sx_ch00', '绪论 担当复兴大任 成就时代新人', p.id, NULL, 2, 0, '新时代的时代新人使命、提升思想道德素质与法治素养', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kaoyan_politics_sixiu' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_sx_ch00' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_sx_ch01', '第一章 领悟人生真谛 把握人生方向', p.id, NULL, 2, 1, '人生观、人生价值评价与实现、对待人生矛盾与反对错误人生观', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kaoyan_politics_sixiu' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_sx_ch01' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_sx_ch02', '第二章 追求远大理想 坚定崇高信念', p.id, NULL, 2, 2, '理想信念内涵、马克思主义信仰、中国梦与青春梦想', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kaoyan_politics_sixiu' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_sx_ch02' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_sx_ch03', '第三章 继承优良传统 弘扬中国精神', p.id, NULL, 2, 3, '中国精神内涵、爱国主义与新时代爱国者、改革创新生力军', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kaoyan_politics_sixiu' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_sx_ch03' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_sx_ch04', '第四章 明确价值要求 践行价值准则', p.id, NULL, 2, 4, '社会主义核心价值观内涵、显著特征与积极践行', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kaoyan_politics_sixiu' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_sx_ch04' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_sx_ch05', '第五章 遵守道德规范 锤炼道德品格', p.id, NULL, 2, 5, '社会主义道德核心原则、优秀道德成果、四大领域道德实践', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kaoyan_politics_sixiu' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_sx_ch05' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_sx_ch06', '第六章 学习法治思想 提升法治素养', p.id, NULL, 2, 6, '法律特征运行、依法治国、宪法权威、尊法学法守法用法', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kaoyan_politics_sixiu' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_sx_ch06' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_sz_ch01', '第一部分 形势与政策（年度重大时事）', p.id, NULL, 2, 1, '年度国内外重大时事政策选择题考点', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kaoyan_politics_shizheng' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_sz_ch01' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_sz_ch02', '第二部分 当代世界经济与政治（分析题专用）', p.id, NULL, 2, 2, '考研政治分析题第38题专用考点与国际格局', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kaoyan_politics_shizheng' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_sz_ch02' AND e.deleted = 0
          );

    -- 2. 批量插入三级节点（小节/考点，153 个）
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_my_ch00_sec01', '第一节 什么是马克思主义', p.id, NULL, 3, 1, '马克思主义的内涵、三个组成部分与基本立场', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_my_ch00' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_my_ch00_sec01' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_my_ch00_sec02', '第二节 马克思主义的创立与发展', p.id, NULL, 3, 2, '历史条件、社会阶级基础与直接理论来源', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_my_ch00' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_my_ch00_sec02' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_my_ch00_sec03', '第三节 马克思主义的鲜明特征与当代价值', p.id, NULL, 3, 3, '科学性、革命性、实践性、人民性、发展性', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_my_ch00' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_my_ch00_sec03' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_my_ch01_sec01', '第一节 世界的多样性与物质统一性', p.id, NULL, 3, 1, '物质范畴、物质与意识辩证关系、意识能动作用、物质统一性', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_my_ch01' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_my_ch01_sec01' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_my_ch01_sec02', '第二节 事物的普遍联系和变化发展', p.id, NULL, 3, 2, '联系与发展的普遍性、对立统一规律、质量互变规律、否定之否定规律、五对基本范畴', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_my_ch01' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_my_ch01_sec02' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_my_ch01_sec03', '第三节 唯物辩证法是认识世界和改造世界的根本方法', p.id, NULL, 3, 3, '辩证思维方法与现代科学思维能力', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_my_ch01' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_my_ch01_sec03' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_my_ch02_sec01', '第一节 实践与认识', p.id, NULL, 3, 1, '科学实践观、认识的本质、感性认识与理性认识的辩证关系', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_my_ch02' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_my_ch02_sec01' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_my_ch02_sec02', '第二节 真理与价值', p.id, NULL, 3, 2, '真理的客观性、绝对性与相对性、实践是检验真理的唯一标准、真理与价值统一', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_my_ch02' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_my_ch02_sec02' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_my_ch02_sec03', '第三节 认识世界和改造世界', p.id, NULL, 3, 3, '一切从实际出发、守正创新、认识世界与改造世界的良性互动', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_my_ch02' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_my_ch02_sec03' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_my_ch03_sec01', '第一节 人类社会的存在与发展', p.id, NULL, 3, 1, '社会存在与社会意识、生产力与生产关系矛盾、经济基础与上层建筑矛盾、社会形态更替', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_my_ch03' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_my_ch03_sec01' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_my_ch03_sec02', '第二节 社会历史发展的动力', p.id, NULL, 3, 2, '社会基本矛盾在历史中的作用、阶级斗争、革命与改革、科技与文化的作用', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_my_ch03' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_my_ch03_sec02' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_my_ch03_sec03', '第三节 人民群众在历史发展中的作用', p.id, NULL, 3, 3, '人民群众是历史创造者、个人在历史中的作用、无产阶级政党的群众观点和路线', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_my_ch03' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_my_ch03_sec03' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_my_ch04_sec01', '第一节 商品经济和价值规律', p.id, NULL, 3, 1, '商品二因素与劳动二重性、商品的价值量、价值规律及其作用、私有制商品经济基本矛盾', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_my_ch04' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_my_ch04_sec01' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_my_ch04_sec02', '第二节 资本主义经济制度的本质', p.id, NULL, 3, 2, '劳动力成为商品与货币转化为资本、剩余价值生产与积累、资本循环周转、资本主义基本矛盾与危机', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_my_ch04' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_my_ch04_sec02' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_my_ch04_sec03', '第三节 资本主义上层建筑', p.id, NULL, 3, 3, '资本主义政治制度与意识形态的本质及其历史进步性与阶级局限性', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_my_ch04' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_my_ch04_sec03' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_my_ch05_sec01', '第一节 资本主义的形成与发展', p.id, NULL, 3, 1, '自由竞争到垄断、国家垄断资本主义的形成与实质、经济全球化及其影响', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_my_ch05' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_my_ch05_sec01' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_my_ch05_sec02', '第二节 正确认识当代资本主义的新变化', p.id, NULL, 3, 2, '二战后资本主义变化的新特征、原因与实质、大变局下资本主义的矛盾', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_my_ch05' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_my_ch05_sec02' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_my_ch05_sec03', '第三节 资本主义的历史地位和发展趋势', p.id, NULL, 3, 3, '资本主义的历史局限性、向社会主义转变的历史必然性与长期性', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_my_ch05' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_my_ch05_sec03' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_my_ch06_sec01', '第一节 社会主义五百年的历史进程', p.id, NULL, 3, 1, '空想到科学、理想到现实、一国到多国、社会主义在中国的生机', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_my_ch06' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_my_ch06_sec01' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_my_ch06_sec02', '第二节 科学社会主义一般原则', p.id, NULL, 3, 2, '科学社会主义一般原则的主要内容及其正确把握', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_my_ch06' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_my_ch06_sec02' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_my_ch06_sec03', '第三节 在实践中开拓中国特色社会主义道路', p.id, NULL, 3, 3, '经济文化落后国家建设社会主义的长期性、发展道路的多样性与创新发展', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_my_ch06' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_my_ch06_sec03' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_my_ch07_sec01', '第一节 展望未来共产主义新社会', p.id, NULL, 3, 1, '预见未来社会的方法论原则、共产主义社会的基本特征', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_my_ch07' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_my_ch07_sec01' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_my_ch07_sec02', '第二节 实现共产主义是历史发展的必然趋势', p.id, NULL, 3, 2, '历史发展的必然规律、实现共产主义是长期的历史过程', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_my_ch07' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_my_ch07_sec02' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_my_ch07_sec03', '第三节 共产主义远大理想与中国特色社会主义共同理想', p.id, NULL, 3, 3, '远大理想与共同理想的辩证统一、坚定理想信念投身新时代伟业', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_my_ch07' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_my_ch07_sec03' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_mzt_ch00_sec01', '第一节 马克思主义中国化时代化的提出与内涵', p.id, NULL, 3, 1, '中国化时代化的科学内涵与核心要义', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_mzt_ch00' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_mzt_ch00_sec01' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_mzt_ch00_sec02', '第二节 马克思主义中国化时代化的历史进程与理论成果', p.id, NULL, 3, 2, '四大理论成果及其相承相续关系', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_mzt_ch00' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_mzt_ch00_sec02' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_mzt_ch01_sec01', '第一节 毛泽东思想的形成和发展', p.id, NULL, 3, 1, '形成发展的时代背景、实践基础与发展阶段', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_mzt_ch01' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_mzt_ch01_sec01' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_mzt_ch01_sec02', '第二节 毛泽东思想的主要内容和活的灵魂', p.id, NULL, 3, 2, '主要内容各方面、活的灵魂（实事求是、群众路线、独立自主）', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_mzt_ch01' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_mzt_ch01_sec02' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_mzt_ch01_sec03', '第三节 毛泽东思想的历史地位', p.id, NULL, 3, 3, '第一个重大理论成果、中国革命和建设的科学指南、宝贵精神财富', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_mzt_ch01' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_mzt_ch01_sec03' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_mzt_ch02_sec01', '第一节 新民主主义革命理论形成的依据', p.id, NULL, 3, 1, '近代中国国情、主要矛盾与时代特征', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_mzt_ch02' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_mzt_ch02_sec01' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_mzt_ch02_sec02', '第二节 新民主主义革命的总路线和基本纲领', p.id, NULL, 3, 2, '总路线（对象、动力、领导权、前途）、政治/经济/文化基本纲领', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_mzt_ch02' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_mzt_ch02_sec02' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_mzt_ch02_sec03', '第三节 新民主主义革命的道路和基本经验', p.id, NULL, 3, 3, '农村包围城市武装夺取政权道路、统一战线/武装斗争/党的建设三大法宝', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_mzt_ch02' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_mzt_ch02_sec03' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_mzt_ch03_sec01', '第一节 从新民主主义到社会主义的转变', p.id, NULL, 3, 1, '新民主主义社会的过渡性质、党在过渡时期的总路线（一化三改）', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_mzt_ch03' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_mzt_ch03_sec01' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_mzt_ch03_sec02', '第二节 社会主义改造道路和历史经验', p.id, NULL, 3, 2, '农业/手工业/资本主义工商业改造道路、和平赎买政策与历史经验', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_mzt_ch03' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_mzt_ch03_sec02' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_mzt_ch03_sec03', '第三节 社会主义基本制度在中国的确立', p.id, NULL, 3, 3, '社会主义基本制度确立的标志、理论根据与重大深远意义', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_mzt_ch03' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_mzt_ch03_sec03' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_mzt_ch04_sec01', '第一节 初步探索的重要理论成果', p.id, NULL, 3, 1, '调动一切积极因素、正确处理人民内部矛盾思想、走中国工业化道路思想', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_mzt_ch04' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_mzt_ch04_sec01' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_mzt_ch04_sec02', '第二节 初步探索的意义和经验教训', p.id, NULL, 3, 2, '初步探索的重大历史意义与根本经验教训', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_mzt_ch04' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_mzt_ch04_sec02' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_mzt_ch05_sec01', '第一节 中国特色社会主义理论体系形成发展的社会历史条件', p.id, NULL, 3, 1, '国际背景、历史根据与实践基础', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_mzt_ch05' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_mzt_ch05_sec01' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_mzt_ch05_sec02', '第二节 中国特色社会主义理论体系形成发展过程', p.id, NULL, 3, 2, '开创、跨世纪发展、新阶段发展与新时代新篇章', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_mzt_ch05' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_mzt_ch05_sec02' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_mzt_ch06_sec01', '第一节 邓小平理论的形成和历史地位', p.id, NULL, 3, 1, '形成条件、形成过程与伟大历史地位', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_mzt_ch06' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_mzt_ch06_sec01' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_mzt_ch06_sec02', '第二节 邓小平理论的首要基本问题和精髓', p.id, NULL, 3, 2, '什么是社会主义、怎样建设社会主义，解放思想、实事求是', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_mzt_ch06' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_mzt_ch06_sec02' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_mzt_ch06_sec03', '第三节 邓小平理论的主要内容', p.id, NULL, 3, 3, '社会主义本质、初级阶段、改革开放、市场经济、“一国两制”、外交战略', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_mzt_ch06' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_mzt_ch06_sec03' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_mzt_ch07_sec01', '第一节 “三个代表”重要思想的形成和历史地位', p.id, NULL, 3, 1, '形成条件、发展过程与历史地位', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_mzt_ch07' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_mzt_ch07_sec01' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_mzt_ch07_sec02', '第二节 “三个代表”重要思想的核心观点与主要内容', p.id, NULL, 3, 2, '始终代表先进生产力发展要求、先进文化前进方向、最广大人民根本利益', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_mzt_ch07' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_mzt_ch07_sec02' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_mzt_ch08_sec01', '第一节 科学发展观的形成和历史地位', p.id, NULL, 3, 1, '立足社会主义初级阶段基本国情的形成过程与历史地位', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_mzt_ch08' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_mzt_ch08_sec01' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_mzt_ch08_sec02', '第二节 科学发展观的科学内涵和主要内容', p.id, NULL, 3, 2, '第一要义是发展、核心立场是以人为本、基本要求是全面协调可持续、根本方法是统筹兼顾', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_mzt_ch08' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_mzt_ch08_sec02' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_xsx_ch00_sec01', '第一节 创立的时代背景与立足时代之基', p.id, NULL, 3, 1, '世界百年未有之大变局、中华民族伟大复兴战略全局', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_xsx_ch00' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_xsx_ch00_sec01' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_xsx_ch00_sec02', '第二节 系统科学的理论体系', p.id, NULL, 3, 2, '十个明确、十四个坚持、十三个方面成就的核心内涵', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_xsx_ch00' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_xsx_ch00_sec02' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_xsx_ch00_sec03', '第三节 马克思主义中国化时代化新的飞跃', p.id, NULL, 3, 3, '开辟马克思主义中国化时代化新境界、历史地位', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_xsx_ch00' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_xsx_ch00_sec03' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_xsx_ch01_sec01', '第一节 中国特色社会主义进入新时代', p.id, NULL, 3, 1, '我国社会主要矛盾转化为人民日益增长的美好生活需要和不平衡不充分的发展之间的矛盾', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_xsx_ch01' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_xsx_ch01_sec01' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_xsx_ch01_sec02', '第二节 新时代中国特色社会主义事业的战略审视', p.id, NULL, 3, 2, '新时代坚持和发展中国特色社会主义的总任务', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_xsx_ch01' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_xsx_ch01_sec02' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_xsx_ch01_sec03', '第三节 坚定中国特色社会主义四个自信', p.id, NULL, 3, 3, '道路自信、理论自信、制度自信、文化自信', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_xsx_ch01' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_xsx_ch01_sec03' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_xsx_ch02_sec01', '第一节 中华民族近代以来最伟大的梦想', p.id, NULL, 3, 1, '实现中华民族伟大复兴的中国梦', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_xsx_ch02' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_xsx_ch02_sec01' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_xsx_ch02_sec02', '第二节 中国式现代化是强国建设、民族复兴的康庄大道', p.id, NULL, 3, 2, '五大中国特色、九条本质要求、五条重大原则与创造人类文明新形态', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_xsx_ch02' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_xsx_ch02_sec02' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_xsx_ch03_sec01', '第一节 中国共产党领导是中国特色社会主义最本质的特征', p.id, NULL, 3, 1, '党的领导是党和国家的根本所在、命脉所在，最高政治领导力量', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_xsx_ch03' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_xsx_ch03_sec01' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_xsx_ch03_sec02', '第二节 坚持党对一切工作的领导', p.id, NULL, 3, 2, '完善党的全面领导体制机制，提高党把方向、谋大局、定政策、促改革能力', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_xsx_ch03' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_xsx_ch03_sec02' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_xsx_ch04_sec01', '第一节 江山就是人民，人民就是江山', p.id, NULL, 3, 1, '始终把人民放在心中最高位置、站稳人民立场', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_xsx_ch04' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_xsx_ch04_sec01' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_xsx_ch04_sec02', '第二节 全面落实以人民为中心的发展思想', p.id, NULL, 3, 2, '发展为了人民、发展依靠人民、发展成果由人民共享，扎实推进全体人民共同富裕', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_xsx_ch04' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_xsx_ch04_sec02' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_xsx_ch05_sec01', '第一节 改革开放是决定当代中国命运的关键一招', p.id, NULL, 3, 1, '改革开放是强国之路、党和人民大踏步赶上时代的重要法宝', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_xsx_ch05' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_xsx_ch05_sec01' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_xsx_ch05_sec02', '第二节 坚定不移全面深化改革', p.id, NULL, 3, 2, '完善和发展中国特色社会主义制度、推进国家治理体系和治理能力现代化', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_xsx_ch05' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_xsx_ch05_sec02' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_xsx_ch05_sec03', '第三节 实行更加积极主动的开放战略', p.id, NULL, 3, 3, '建设更高水平开放型经济新体制、推动共建“一带一路”高质量发展', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_xsx_ch05' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_xsx_ch05_sec03' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_xsx_ch06_sec01', '第一节 完整、准确、全面贯彻新发展理念', p.id, NULL, 3, 1, '创新、协调、绿色、开放、共享发展理念', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_xsx_ch06' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_xsx_ch06_sec01' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_xsx_ch06_sec02', '第二节 加快构建新发展格局', p.id, NULL, 3, 2, '以国内大循环为主体、国内国际双循环相互促进的新发展格局', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_xsx_ch06' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_xsx_ch06_sec02' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_xsx_ch06_sec03', '第三节 发展新质生产力与建设现代化经济体系', p.id, NULL, 3, 3, '科技创新引领产业创新、催生新质生产力、建设现代化产业体系', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_xsx_ch06' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_xsx_ch06_sec03' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_xsx_ch07_sec01', '第一节 教育是国之大计、党之大计', p.id, NULL, 3, 1, '优先发展教育事业、加快建设教育强国、办好人民满意的教育', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_xsx_ch07' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_xsx_ch07_sec01' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_xsx_ch07_sec02', '第二节 科技立则民族立，科技强则国家强', p.id, NULL, 3, 2, '实现高水平科技自立自强、打赢关键核心技术攻坚战', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_xsx_ch07' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_xsx_ch07_sec02' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_xsx_ch07_sec03', '第三节 人才是第一资源', p.id, NULL, 3, 3, '深入实施新时代人才强国战略、全方位培养引进用好人才', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_xsx_ch07' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_xsx_ch07_sec03' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_xsx_ch08_sec01', '第一节 全过程人民民主是社会主义民主政治的本质属性', p.id, NULL, 3, 1, '最广泛、最真实、最管用的全链条全方位全覆盖民主', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_xsx_ch08' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_xsx_ch08_sec01' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_xsx_ch08_sec02', '第二节 健全人民当家作主制度体系', p.id, NULL, 3, 2, '坚持和完善人民代表大会制度、中国共产党领导的多党合作和政治协商制度、基层群众自治制度', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_xsx_ch08' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_xsx_ch08_sec02' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_xsx_ch08_sec03', '第三节 巩固和发展最广泛的爱国统一战线', p.id, NULL, 3, 3, '大统战工作格局、铸牢中华民族共同体意识、坚持我国宗教中国化方向', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_xsx_ch08' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_xsx_ch08_sec03' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_xsx_ch09_sec01', '第一节 习近平法治思想是全面依法治国的根本遵循', p.id, NULL, 3, 1, '十一个坚持的核心要义与科学内涵', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_xsx_ch09' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_xsx_ch09_sec01' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_xsx_ch09_sec02', '第二节 坚持走中国特色社会主义法治道路', p.id, NULL, 3, 2, '坚持党的领导、坚持人民主体地位、坚持法律面前人人平等', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_xsx_ch09' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_xsx_ch09_sec02' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_xsx_ch09_sec03', '第三节 深化法治中国建设', p.id, NULL, 3, 3, '科学立法、严格执法、公正司法、全民守法', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_xsx_ch09' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_xsx_ch09_sec03' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_xsx_ch10_sec01', '第一节 文化是民族生存和发展的重要力量', p.id, NULL, 3, 1, '坚定文化自信、秉持开放包容、坚持守正创新、巩固文化主体性', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_xsx_ch10' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_xsx_ch10_sec01' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_xsx_ch10_sec02', '第二节 建设具有强大凝聚力和引领力的社会主义意识形态', p.id, NULL, 3, 2, '牢牢掌握党对意识形态工作领导权、全面落实意识形态工作责任制', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_xsx_ch10' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_xsx_ch10_sec02' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_xsx_ch10_sec03', '第三节 广泛践行社会主义核心价值观与繁荣发展文化事业', p.id, NULL, 3, 3, '繁荣发展文化事业和文化产业、推动中华优秀传统文化创造性转化创新性发展', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_xsx_ch10' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_xsx_ch10_sec03' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_xsx_ch11_sec01', '第一节 治国有常，利民为本', p.id, NULL, 3, 1, '在发展中保障和改善民生、解决好群众急难愁盼问题', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_xsx_ch11' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_xsx_ch11_sec01' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_xsx_ch11_sec02', '第二节 提高人民生活品质', p.id, NULL, 3, 2, '完善分配制度、实施就业优先战略、健全社会保障体系、推进健康中国建设', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_xsx_ch11' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_xsx_ch11_sec02' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_xsx_ch11_sec03', '第三节 在共建共治共享中推进社会治理现代化', p.id, NULL, 3, 3, '完善社会治理体系、建设人人有责/人人尽责/人人享有的社会治理共同体', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_xsx_ch11' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_xsx_ch11_sec03' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_xsx_ch12_sec01', '第一节 生态文明建设是关乎中华民族永续发展的根本大计', p.id, NULL, 3, 1, '坚持人与自然和谐共生、生态兴则文明兴', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_xsx_ch12' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_xsx_ch12_sec01' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_xsx_ch12_sec02', '第二节 贯彻习近平生态文明思想', p.id, NULL, 3, 2, '绿水青山就是金山银山、山水林田湖草沙一体化保护和系统治理', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_xsx_ch12' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_xsx_ch12_sec02' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_xsx_ch12_sec03', '第三节 建设美丽中国', p.id, NULL, 3, 3, '推进绿色低碳发展、深入打好污染防治攻坚战、积极稳妥推进碳达峰碳中和', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_xsx_ch12' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_xsx_ch12_sec03' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_xsx_ch13_sec01', '第一节 保证国家安全是头等大事', p.id, NULL, 3, 1, '国家安全是民族复兴的根基、统筹发展和安全', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_xsx_ch13' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_xsx_ch13_sec01' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_xsx_ch13_sec02', '第二节 贯彻总体国家安全观', p.id, NULL, 3, 2, '五大要素、五个统筹、十个坚持的总体国家安全观框架', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_xsx_ch13' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_xsx_ch13_sec02' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_xsx_ch13_sec03', '第三节 推进国家安全体系和能力现代化', p.id, NULL, 3, 3, '健全国家安全体系、增强维护国家安全能力、提高公共安全治理水平', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_xsx_ch13' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_xsx_ch13_sec03' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_xsx_ch14_sec01', '第一节 强国必须强军，军强才能国安', p.id, NULL, 3, 1, '巩固国防和强大军队是国家安全的坚强后盾', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_xsx_ch14' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_xsx_ch14_sec01' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_xsx_ch14_sec02', '第二节 实现党在新时代的强军目标', p.id, NULL, 3, 2, '听党指挥、能打胜仗、作风优良，把人民军队建设成为世界一流军队', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_xsx_ch14' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_xsx_ch14_sec02' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_xsx_ch14_sec03', '第三节 推进国防和军队现代化', p.id, NULL, 3, 3, '坚持党对人民军队绝对领导、全面推进政治建军/改革强军/科技强军/人才强军/依法治军', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_xsx_ch14' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_xsx_ch14_sec03' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_xsx_ch15_sec01', '第一节 全面准确贯彻“一国两制”方针', p.id, NULL, 3, 1, '“一国”是根与本、“两制”从属派生，“爱国者治港”、“爱国者治澳”', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_xsx_ch15' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_xsx_ch15_sec01' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_xsx_ch15_sec02', '第二节 保持香港、澳门长期繁荣稳定', p.id, NULL, 3, 2, '落实中央全面管治权、保持港澳独特地位和优势、融入国家发展大局', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_xsx_ch15' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_xsx_ch15_sec02' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_xsx_ch15_sec03', '第三节 推进祖国完全统一', p.id, NULL, 3, 3, '贯彻新时代党解决台湾问题的总体方略、坚持一个中国原则和“九二共识”、反对台独分裂', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_xsx_ch15' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_xsx_ch15_sec03' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_xsx_ch16_sec01', '第一节 新时代中国外交的大政方针', p.id, NULL, 3, 1, '坚持和平发展道路、推动建设相互尊重/公平正义/合作共赢的新型国际关系', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_xsx_ch16' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_xsx_ch16_sec01' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_xsx_ch16_sec02', '第二节 推动构建人类命运共同体', p.id, NULL, 3, 2, '建设持久和平/普遍安全/共同繁荣/开放包容/清洁美丽的世界，弘扬全人类共同价值，落实三大全球倡议', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_xsx_ch16' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_xsx_ch16_sec02' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_xsx_ch16_sec03', '第三节 积极参与全球治理体系改革和建设', p.id, NULL, 3, 3, '践行共商共建共享的全球治理观、坚持真正的多边主义', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_xsx_ch16' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_xsx_ch16_sec03' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_xsx_ch17_sec01', '第一节 勇于自我革命是中国共产党最鲜明的品格', p.id, NULL, 3, 1, '自我革命是跳出治乱兴衰历史周期率的第二个答案、时刻保持解决大党独有难题的清醒', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_xsx_ch17' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_xsx_ch17_sec01' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_xsx_ch17_sec02', '第二节 健全全面从严治党体系', p.id, NULL, 3, 2, '以党的政治建设为统领、把思想建设作为党的基础性建设、正风肃纪、反腐败斗争', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_xsx_ch17' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_xsx_ch17_sec02' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_xsx_ch17_sec03', '第三节 以伟大自我革命引领伟大社会革命', p.id, NULL, 3, 3, '两个伟大革命的辩证关系、把党建设得更加坚强有力', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_xsx_ch17' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_xsx_ch17_sec03' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_sg_ch00_sec01', '第一节 中国近代史与现代史综述', p.id, NULL, 3, 1, '历史分期、两大历史任务与学习目的', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_sg_ch00' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_sg_ch00_sec01' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_sg_ch01_sec01', '第一节 鸦片战争前后的中国与世界', p.id, NULL, 3, 1, '中国封建社会的衰落与西方资本主义的扩张', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_sg_ch01' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_sg_ch01_sec01' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_sg_ch01_sec02', '第二节 西方列强对中国的侵略', p.id, NULL, 3, 2, '军事侵略、政治控制、经济掠夺、文化渗透，不平等条约', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_sg_ch01' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_sg_ch01_sec02' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_sg_ch01_sec03', '第三节 反抗外来侵略的斗争历程与民族意识觉醒', p.id, NULL, 3, 3, '人民群众与爱国官兵的反侵略斗争、反侵略失败原因、民族意识的觉醒', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_sg_ch01' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_sg_ch01_sec03' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_sg_ch02_sec01', '第一节 太平天国农民起义的起落', p.id, NULL, 3, 1, '金田起义、《天朝田亩制度》、《资政新篇》、历史意义与农民阶级局限性', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_sg_ch02' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_sg_ch02_sec01' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_sg_ch02_sec02', '第二节 洋务事业的兴衰', p.id, NULL, 3, 2, '洋务派主张与中体西用、军用民用工业开办、洋务运动历史作用与失败原因', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_sg_ch02' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_sg_ch02_sec02' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_sg_ch02_sec03', '第三节 戊戌维新运动的兴起与夭折', p.id, NULL, 3, 3, '维新派宣传组织、百日维新、维新运动的历史意义与资产阶级软弱妥协教训', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_sg_ch02' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_sg_ch02_sec03' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_sg_ch03_sec01', '第一节 举起近代民族民主革命的旗帜', p.id, NULL, 3, 1, '资产阶级革命派阶级基础、同盟会成立、三民主义学说、革命派与改良派论战', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_sg_ch03' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_sg_ch03_sec01' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_sg_ch03_sec02', '第二节 辛亥革命与中华民국의建立', p.id, NULL, 3, 2, '武昌起义、中华民国临时政府建立、《中华民国临时约法》、辛亥革命的历史意义', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_sg_ch03' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_sg_ch03_sec02' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_sg_ch03_sec03', '第三节 北洋军阀统治与辛亥革命的历史局限', p.id, NULL, 3, 3, '袁世凯复辟与北洋军阀反动统治、反对北洋军阀斗争、旧民主主义革命失败教训', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_sg_ch03' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_sg_ch03_sec03' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_sg_ch04_sec01', '第一节 新文化运动和五四运动', p.id, NULL, 3, 1, '新文化运动与思想解放、五四运动是新民主主义革命的开端', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_sg_ch04' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_sg_ch04_sec01' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_sg_ch04_sec02', '第二节 马克思主义广泛传播与中国共产党诞生', p.id, NULL, 3, 2, '马克思主义在中国的早期传播、早期党组织、中共一大与红船精神、党的民主革命纲领', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_sg_ch04' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_sg_ch04_sec02' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_sg_ch04_sec03', '第三节 国共合作与大革命的高潮及失败', p.id, NULL, 3, 3, '第一次国共合作建立、北伐战争胜利进军、大革命失败的深刻历史教训', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_sg_ch04' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_sg_ch04_sec03' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_sg_ch05_sec01', '第一节 中国共产党对革命新道路的艰苦探索', p.id, NULL, 3, 1, '南昌起义/秋收起义、井冈山根据地开辟、工农武装割据思想与农村包围城市道路', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_sg_ch05' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_sg_ch05_sec01' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_sg_ch05_sec02', '第二节 中国革命在曲折中前进', p.id, NULL, 3, 2, '古田会议、左倾教条主义错误、红军长征与遵义会议确立毛泽东领导地位、长征胜利意义', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_sg_ch05' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_sg_ch05_sec02' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_sg_ch06_sec01', '第一节 日本发动侵华战争与全民族抗战的开始', p.id, NULL, 3, 1, '日本灭亡中国的侵略罪行、抗日民族统一战线形成与全民族抗战路线', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_sg_ch06' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_sg_ch06_sec01' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_sg_ch06_sec02', '第二节 正面战场与敌后战场的开辟', p.id, NULL, 3, 2, '国民党正面战场作战及评价、中国共产党开辟敌后战场、《论持久战》战略方针', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_sg_ch06' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_sg_ch06_sec02' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_sg_ch06_sec03', '第三节 中国共产党是全民族抗战的中流砥柱', p.id, NULL, 3, 3, '坚持抗战团结进步方针、抗日民主根据地建设、新民主主义理论系统阐述、延安整风与党的七大', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_sg_ch06' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_sg_ch06_sec03' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_sg_ch06_sec04', '第四节 抗日战争的胜利及其伟大意义', p.id, NULL, 3, 4, '东方主战场历史贡献、抗战胜利原因与伟大历史意义', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_sg_ch06' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_sg_ch06_sec04' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_sg_ch07_sec01', '第一节 从争取和平民主到进行自卫战争', p.id, NULL, 3, 1, '重庆谈判与政治协商会议、国民党发动全面内战、自卫战争粉碎国民党进攻', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_sg_ch07' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_sg_ch07_sec01' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_sg_ch07_sec02', '第二节 国民党政权的崩溃与第二条战线的形成', p.id, NULL, 3, 2, '解放军转入战略进攻、土地改革运动深入开展、国统区爱国民主运动形成第二条战线', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_sg_ch07' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_sg_ch07_sec02' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_sg_ch07_sec03', '第三节 人民政协的召开与中华人民共和国的成立', p.id, NULL, 3, 3, '辽沈淮海平津三大战役、中共七届二中全会、《论人民民主专政》、中国人民政治协商会议与建国', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_sg_ch07' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_sg_ch07_sec03' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_sg_ch08_sec01', '第一节 新中国的成立与巩固政权的斗争', p.id, NULL, 3, 1, '新中国成立的划时代意义、抗美援朝战争、土改与镇反、国民经济迅速恢复', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_sg_ch08' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_sg_ch08_sec01' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_sg_ch08_sec02', '第二节 社会主义改造的完成与基本制度的确立', p.id, NULL, 3, 2, '过渡时期总路线的提出、第一部宪法颁布、社会主义三大改造基本完成', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_sg_ch08' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_sg_ch08_sec02' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_sg_ch08_sec03', '第三节 社会主义建设道路的初步探索与曲折发展', p.id, NULL, 3, 3, '中共八大正确路线、探索中的严重曲折、社会主义建设取得的重大成就', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_sg_ch08' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_sg_ch08_sec03' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_sg_ch09_sec01', '第一节 历史性的伟大转折与改革开放的起步', p.id, NULL, 3, 1, '真理标准问题大讨论、中共十一届三中全会的伟大历史转折、拨乱反正', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_sg_ch09' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_sg_ch09_sec01' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_sg_ch09_sec02', '第二节 改革开放和现代化建设新局面的展开', p.id, NULL, 3, 2, '农村家庭联产承包责任制、对外开放格局形成、邓小平南方谈话与十四大', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_sg_ch09' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_sg_ch09_sec02' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_sg_ch09_sec03', '第三节 中国特色社会主义事业跨世纪发展与新起点推进', p.id, NULL, 3, 3, '建立社会主义市场经济体制、加入世界贸易组织、统筹推进经济社会全面协调可持续发展', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_sg_ch09' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_sg_ch09_sec03' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_sg_ch10_sec01', '第一节 历史性成就和历史性变革', p.id, NULL, 3, 1, '打赢脱贫攻坚战、全面建成小康社会、党和国家事业取得历史性成就', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_sg_ch10' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_sg_ch10_sec01' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_sg_ch10_sec02', '第二节 开启全面建设社会主义现代化国家新征程', p.id, NULL, 3, 2, '党的二十大擘画的宏伟蓝图、以中国式现代化全面推进中华民族伟大复兴', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_sg_ch10' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_sg_ch10_sec02' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_sx_ch00_sec01', '第一节 时代新人的使命与担当', p.id, NULL, 3, 1, '我们处在中国特色社会主义新时代、有理想敢担当能吃苦肯奋斗', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_sx_ch00' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_sx_ch00_sec01' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_sx_ch00_sec02', '第二节 提升思想道德素质与法治素养', p.id, NULL, 3, 2, '思想道德与法治的辩证关系与相辅相成', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_sx_ch00' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_sx_ch00_sec02' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_sx_ch01_sec01', '第一节 人生观是对人生的总看法', p.id, NULL, 3, 1, '人的本质是一切社会关系的总和、人生观的主要内容及其与世界观价值观关系', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_sx_ch01' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_sx_ch01_sec01' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_sx_ch01_sec02', '第二节 正确的人生观', p.id, NULL, 3, 2, '高尚的人生目的、积极进取的人生态度、人生自我价值与社会价值评价及实现', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_sx_ch01' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_sx_ch01_sec02' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_sx_ch01_sec03', '第三节 创造有意义的人生', p.id, NULL, 3, 3, '辩证对待得与失/顺与逆/苦与乐/荣与辱/生与死，坚决反对拜金主义享乐主义极端个人主义', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_sx_ch01' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_sx_ch01_sec03' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_sx_ch02_sec01', '第一节 理想信念的内涵及重要性', p.id, NULL, 3, 1, '理想与信念的科学内涵、理想信念是精神之钙', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_sx_ch02' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_sx_ch02_sec01' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_sx_ch02_sec02', '第二节 坚定信仰信念信心', p.id, NULL, 3, 2, '增强马克思主义信仰、增强中国特色社会主义信念、增强中华民族伟大复兴信心', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_sx_ch02' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_sx_ch02_sec02' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_sx_ch02_sec03', '第三节 在实现中国梦的实践中放飞青春梦想', p.id, NULL, 3, 3, '科学把握理想与现实辩证统一、坚持个人理想与社会理想有机结合、立志高远脚踏实地', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_sx_ch02' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_sx_ch02_sec03' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_sx_ch03_sec01', '第一节 中国精神是兴国强国之魂', p.id, NULL, 3, 1, '崇尚精神是中华民族优秀传统、以爱国主义为核心的民族精神和以改革创新为核心的时代精神', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_sx_ch03' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_sx_ch03_sec01' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_sx_ch03_sec02', '第二节 做新时代的忠诚爱国者', p.id, NULL, 3, 2, '爱国爱党爱社会主义相统一、维护祖国统一与民族团结、传承中华优秀传统文化', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_sx_ch03' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_sx_ch03_sec02' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_sx_ch03_sec03', '第三节 让改革创新成为青春远航的动力', p.id, NULL, 3, 3, '改革创新是新时代的迫切要求、树立改革创新自觉、做改革创新生力军', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_sx_ch03' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_sx_ch03_sec03' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_sx_ch04_sec01', '第一节 全体人民共同的价值追求', p.id, NULL, 3, 1, '社会主义核心价值观富强民主文明和谐、自由平等公正法治、爱国敬业诚信友善', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_sx_ch04' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_sx_ch04_sec01' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_sx_ch04_sec02', '第二节 社会主义核心价值观的显著特征', p.id, NULL, 3, 2, '反映人类社会发展进步理念、彰显人民至上价值立场、因真实可信而具有强大道义力量', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_sx_ch04' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_sx_ch04_sec02' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_sx_ch04_sec03', '第三节 积极践行社会主义核心价值观', p.id, NULL, 3, 3, '扣好人生扣子、勤学修德明辨笃实、把社会主义核心价值观落细落小落实', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_sx_ch04' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_sx_ch04_sec03' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_sx_ch05_sec01', '第一节 社会主义道德的核心与原则', p.id, NULL, 3, 1, '马克思主义道德观、坚持以为人民服务为核心、坚持以集体主义为原则', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_sx_ch05' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_sx_ch05_sec01' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_sx_ch05_sec02', '第二节 吸收借鉴优秀道德成果', p.id, NULL, 3, 2, '传承中华传统美德、发扬中国革命道德、借鉴人类文明优秀道德成果', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_sx_ch05' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_sx_ch05_sec02' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_sx_ch05_sec03', '第三节 投身崇德向善的道德实践', p.id, NULL, 3, 3, '社会公德、职业道德、家庭美德、个人品德修养', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_sx_ch05' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_sx_ch05_sec03' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_sx_ch06_sec01', '第一节 社会主义法律的特征和运行', p.id, NULL, 3, 1, '法律本质特征与运行环节（立法、执法、司法、守法）', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_sx_ch06' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_sx_ch06_sec01' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_sx_ch06_sec02', '第二节 坚持全面依法治国', p.id, NULL, 3, 2, '习近平法治思想、走中国特色社会主义法治道路、建设法治中国', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_sx_ch06' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_sx_ch06_sec02' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_sx_ch06_sec03', '第三节 维护宪法权威', p.id, NULL, 3, 3, '我国宪法地位与基本原则、我国国体政体与国家机构', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_sx_ch06' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_sx_ch06_sec03' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_sx_ch06_sec04', '第四节 自觉尊法学法守法用法', p.id, NULL, 3, 4, '培养社会主义法治思维、依法行使权利与履行义务', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_sx_ch06' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_sx_ch06_sec04' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_sz_ch01_sec01', '第一节 国内重大时事', p.id, NULL, 3, 1, '当年党和国家重大会议、政治经济改革新举措、重大科技成就', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_sz_ch01' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_sz_ch01_sec01' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_sz_ch01_sec02', '第二节 国际重大时事', p.id, NULL, 3, 2, '国际局势演变、重大主场外交、大国博弈关键节点与重要国际会议', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_sz_ch01' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_sz_ch01_sec02' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_sz_ch02_sec01', '第一节 世界多极化与经济全球化趋势', p.id, NULL, 3, 1, '国际力量对比变化、新型全球化与逆全球化思潮、世界经济动能', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_sz_ch02' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_sz_ch02_sec01' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_sz_ch02_sec02', '第二节 大国关系深刻调整与地区热点焦点', p.id, NULL, 3, 2, '中美俄欧大国关系、地缘政治冲突、传统与非传统安全挑战', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_sz_ch02' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_sz_ch02_sec02' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_sz_ch02_sec03', '第三节 全球治理体系变革与发展中国家崛起', p.id, NULL, 3, 3, '全球南方群体性崛起、多边主义与单边主义斗争、国际金融贸易机制变革', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_sz_ch02' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_sz_ch02_sec03' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_sz_ch02_sec04', '第四节 推动构建人类命运共同体', p.id, NULL, 3, 4, '高质量共建一带一路、全球发展倡议、全球安全倡议、全球文明倡议', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_sz_ch02' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_sz_ch02_sec04' AND e.deleted = 0
          );
    INSERT INTO fba.qbank_v2_knowledge_point (
            system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
        )
        SELECT
            v_system_id, 'kp_kaoyan_sz_ch02_sec05', '第五节 新时代中国特色大国外交战略', p.id, NULL, 3, 5, '独立自主和平外交方针、共商共建共享治理观、新型国际关系建设', 1, NOW(), 0
        FROM fba.qbank_v2_knowledge_point p
        WHERE p.system_id = v_system_id AND p.code = 'kp_kaoyan_sz_ch02' AND p.deleted = 0
          AND NOT EXISTS (
              SELECT 1 FROM fba.qbank_v2_knowledge_point e
              WHERE e.system_id = v_system_id AND e.code = 'kp_kaoyan_sz_ch02_sec05' AND e.deleted = 0
          );

    -- 3. 递归收敛计算 path 路径（支持多级）
    FOR i IN 1..4 LOOP

        UPDATE fba.qbank_v2_knowledge_point kp
        SET path = COALESCE(
                (SELECT p.path || '.' || CAST(kp.id AS VARCHAR)
                   FROM fba.qbank_v2_knowledge_point p
                  WHERE p.id = kp.parent_id AND p.system_id = kp.system_id),
                CAST(kp.id AS VARCHAR)
            ),
            updated_time = NOW()
        WHERE kp.system_id = v_system_id
          AND kp.deleted = 0
          AND (
              kp.path IS NULL OR
              kp.path IS DISTINCT FROM COALESCE(
                  (SELECT p.path || '.' || CAST(kp.id AS VARCHAR)
                     FROM fba.qbank_v2_knowledge_point p
                    WHERE p.id = kp.parent_id AND p.system_id = kp.system_id),
                  CAST(kp.id AS VARCHAR)
              )
          );
    END LOOP;

    -- 4. 修复主键自增序列

    PERFORM setval(
        pg_get_serial_sequence('fba.qbank_v2_knowledge_point', 'id'),
        GREATEST(
            COALESCE((SELECT MAX(id) FROM fba.qbank_v2_knowledge_point), 1),
            COALESCE((SELECT last_value FROM fba.qbank_v2_knowledge_point_id_seq), 1)
        ),
        (SELECT COUNT(*) > 0 FROM fba.qbank_v2_knowledge_point)
    );

    RAISE NOTICE '考研政治三级知识点拓扑扩展完成！';
END $$;
