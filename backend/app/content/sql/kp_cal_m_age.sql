WITH category_node AS (
    SELECT id FROM sys_category WHERE app_code = 'youanshang' AND type = 'knowledge_point' AND code = 'kp_cal_m_age'
)
INSERT INTO sys_content (app_code, title, slug, content_json, content_html, summary, category_id, tags, is_pinned, is_public, is_published, publish_time, view_count, sort_order, extra, created_by, created_time)
SELECT 'gongkao', '日期与年龄综合', 'kp-cal-m-age', CAST($${"type": "doc", "content": [{"type": "heading", "attrs": {"level": 1}, "content": [{"type": "text", "text": "日期与年龄综合"}]}, {"type": "paragraph", "content": [{"type": "text", "text": "结合闰年 2月29日 生日的年龄跨度问题。"}]}]}$$ AS jsonb), NULL, '日期与年龄综合的核心考点与实战推导。', category_node.id, CAST('["数量关系", "日期与年龄综合"]' AS jsonb), FALSE, TRUE, TRUE, NOW(), 0, 0, CAST('{"content_type": "knowledge_point", "category_code": "kp_cal_m_age", "source": "fba_content_engine"}' AS jsonb), 1, NOW()
FROM category_node ON CONFLICT (slug) DO UPDATE SET title = EXCLUDED.title, content_json = EXCLUDED.content_json, summary = EXCLUDED.summary, category_id = EXCLUDED.category_id, tags = EXCLUDED.tags, updated_time = NOW();
