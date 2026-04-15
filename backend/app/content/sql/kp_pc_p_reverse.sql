WITH category_node AS (
    SELECT id FROM sys_category WHERE app_code = 'youanshang' AND type = 'knowledge_point' AND code = 'kp_pc_p_reverse'
)
INSERT INTO sys_content (app_code, title, slug, content_json, content_html, summary, category_id, tags, is_pinned, is_public, is_published, publish_time, view_count, sort_order, extra, created_by, created_time)
SELECT 'gongkao', '排列反求', 'kp-pc-p-reverse', CAST($${"type": "doc", "content": [{"type": "heading", "attrs": {"level": 1}, "content": [{"type": "text", "text": "排列反求"}]}, {"type": "paragraph", "content": [{"type": "text", "text": "已知排列数求元素个数。"}]}]}$$ AS jsonb), NULL, '排列反求的核心考点与实战推导。', category_node.id, CAST('["数量关系", "排列组合", "排列反求"]' AS jsonb), FALSE, TRUE, TRUE, NOW(), 0, 0, CAST('{"content_type": "knowledge_point", "category_code": "kp_pc_p_reverse", "source": "fba_content_engine"}' AS jsonb), 1, NOW()
FROM category_node ON CONFLICT (slug) DO UPDATE SET title = EXCLUDED.title, content_json = EXCLUDED.content_json, summary = EXCLUDED.summary, category_id = EXCLUDED.category_id, tags = EXCLUDED.tags, updated_time = NOW();
