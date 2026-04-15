WITH category_node AS (
    SELECT id
    FROM sys_category
    WHERE app_code = 'youanshang'
      AND type = 'knowledge_point'
      AND code = 'kp_xingce_data_mixed_text_chart'
)
INSERT INTO sys_content (
    app_code, title, slug, content_json, content_html, summary, category_id, tags, is_pinned, is_public, is_published, publish_time, view_count, sort_order, extra, created_by, created_time
)
SELECT
    'gongkao', '文图综合', 'kp-xingce-data-mixed-text-chart',
    CAST($${
  "type": "doc",
  "content": [
    {
      "type": "heading",
      "attrs": { "level": 1 },
      "content": [ { "type": "text", "text": "文图综合" } ]
    },
    {
      "type": "highlightBlock",
      "attrs": { "backgroundColor": "#fffbeb" },
      "content": [
        {
          "type": "paragraph",
          "content": [
            { "type": "text", "text": "核心策略：" },
            { "type": "text", "text": "文字找绝对值，图形看结构率。", "marks": [ { "type": "bold" } ] }
          ]
        }
      ]
    },
    {
      "type": "heading",
      "attrs": { "level": 2 },
      "content": [ { "type": "text", "text": "一、经典组合：文字 + 饼图" } ]
    },
    {
      "type": "paragraph",
      "content": [
        { "type": "text", "text": "这可以说是资料分析最“仁慈”的组合了。图形通常是一个极其直观的饼图（只标有百分比，没有具体数字），而旁边的文字会轻描淡写地说一句：“2023年，全年总收入达到 8900 亿元……”" }
      ]
    },
    {
      "type": "bulletList",
      "content": [
        {
          "type": "listItem",
          "content": [
            { "type": "paragraph", "content": [ { "type": "text", "text": "破题法：" }, { "type": "text", "text": "求某切片绝对量 = 文字里的“总额” × 饼图里的“百分比”。一秒直杀答案。" } ] }
          ]
        }
      ]
    },
    {
      "type": "heading",
      "attrs": { "level": 2 },
      "content": [ { "type": "text", "text": "二、经典组合：文字 + 柱状折线图" } ]
    },
    {
      "type": "paragraph",
      "content": [
        { "type": "text", "text": "这种组合通常是为了增加“查找跨度”。" }
      ]
    },
    {
      "type": "orderedList",
      "attrs": { "start": 1 },
      "content": [
        {
          "type": "listItem",
          "content": [
            { "type": "paragraph", "content": [ { "type": "text", "text": "图形通常展示 2018-2023 年 连续 6 年的总量和增速。" } ] }
          ]
        },
        {
          "type": "listItem",
          "content": [
            { "type": "paragraph", "content": [ { "type": "text", "text": "文字则专门针对 2023 年这一年的数据进行“下钻分解”，告诉你这其中第一产业是多少、第二产业是多少。" } ] }
          ]
        }
      ]
    },
    {
      "type": "highlightBlock",
      "attrs": { "backgroundColor": "#fef2f2" },
      "content": [
        {
          "type": "paragraph",
          "content": [
            { "type": "text", "text": "时间锚点雷区：", "marks": [ { "type": "bold" } ] }
          ]
        },
        {
          "type": "paragraph",
          "content": [
            { "type": "text", "text": "如果你在做关于 2022 年（历史年份）的拆解题，千万不要去读下面文字里的拆解比例！因为文字通常只描述最新一年的明细。历史年份的具体构成，在材料里往往是没有给出的（属于无法推出）。" }
          ]
        }
      ]
    }
  ]
}$$ AS jsonb),
    NULL, '文字找基数，图形定比例，经典饼图组合解法。', category_node.id, CAST('["资料分析", "综合资料", "文图综合"]' AS jsonb), FALSE, TRUE, TRUE, NOW(), 0, 0, CAST('{"content_type": "knowledge_point", "category_code": "kp_xingce_data_mixed_text_chart", "source": "fba_content_engine"}' AS jsonb), 1, NOW()
FROM category_node
ON CONFLICT (slug)
DO UPDATE SET
    title = EXCLUDED.title, content_json = EXCLUDED.content_json, summary = EXCLUDED.summary, category_id = EXCLUDED.category_id, tags = EXCLUDED.tags, updated_time = NOW();