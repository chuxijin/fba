WITH category_node AS (
    SELECT id FROM sys_category WHERE app_code = 'youanshang' AND type = 'knowledge_point' AND code = 'kp_cal_m_complex'
)
INSERT INTO sys_content (app_code, title, slug, content_json, content_html, summary, category_id, tags, is_pinned, is_public, is_published, publish_time, view_count, sort_order, extra, created_by, created_time)
SELECT 'gongkao', '复杂星期日期应用', 'kp-cal-m-complex', CAST($${"type": "doc", "content": [{"type": "heading", "attrs": {"level": 1}, "content": [{"type": "text", "text": "复杂星期日期应用"}]}, {"type": "paragraph", "content": [{"type": "text", "text": "画日历网格是最好的解题手段。"}]}]}$$ AS jsonb), NULL, '复杂星期日期应用的核心考点与实战推导。', category_node.id, CAST('["数量关系", "复杂星期日期应用"]' AS jsonb), FALSE, TRUE, TRUE, NOW(), 0, 0, CAST('{"content_type": "knowledge_point", "category_code": "kp_cal_m_complex", "source": "fba_content_engine"}' AS jsonb), 1, NOW()
FROM category_node ON CONFLICT (slug) DO UPDATE SET title = EXCLUDED.title, content_json = EXCLUDED.content_json, summary = EXCLUDED.summary, category_id = EXCLUDED.category_id, tags = EXCLUDED.tags, updated_time = NOW();
