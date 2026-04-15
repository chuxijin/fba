WITH category_node AS (
    SELECT id
    FROM sys_category
    WHERE app_code = 'youanshang'
      AND type = 'knowledge_point'
      AND code = 'kp_xingce_data_mixed_all'
)
INSERT INTO sys_content (
    app_code, title, slug, content_json, content_html, summary, category_id, tags, is_pinned, is_public, is_published, publish_time, view_count, sort_order, extra, created_by, created_time
)
SELECT
    'gongkao', '图文表综合', 'kp-xingce-data-mixed-all',
    CAST($${
  "type": "doc",
  "content": [
    {
      "type": "heading",
      "attrs": { "level": 1 },
      "content": [ { "type": "text", "text": "图文表综合" } ]
    },
    {
      "type": "highlightBlock",
      "attrs": { "backgroundColor": "#fffbeb" },
      "content": [
        {
          "type": "paragraph",
          "content": [
            { "type": "text", "text": "核心策略：" },
            { "type": "text", "text": "不要被篇幅吓倒，拆分成独立模块单独击破。", "marks": [ { "type": "bold" } ] }
          ]
        }
      ]
    },
    {
      "type": "paragraph",
      "content": [
        { "type": "text", "text": "这就是传说中的“大乱炖”材料。一段文字，配个大图，图下面又压着一个表。考场上遇到这种材料，很多考生的第一反应是心态崩溃。" }
      ]
    },
    {
      "type": "heading",
      "attrs": { "level": 2 },
      "content": [ { "type": "text", "text": "一、纸老虎的本质" } ]
    },
    {
      "type": "paragraph",
      "content": [
        { "type": "text", "text": "其实图文表综合材料的单道题目，" }, { "type": "text", "text": "难度反而比纯文字材料低", "marks": [ { "type": "bold" } ] }, { "type": "text", "text": "。因为材料多，命题人为了控制做题时间，通常不会在找数上故意绕很大弯子。" }
      ]
    },
    {
      "type": "heading",
      "attrs": { "level": 2 },
      "content": [ { "type": "text", "text": "二、解题心法：模块化隔离" } ]
    },
    {
      "type": "orderedList",
      "attrs": { "start": 1 },
      "content": [
        {
          "type": "listItem",
          "content": [
            { "type": "paragraph", "content": [ { "type": "text", "text": "第一题通常只对应文字区（考宏观）。" } ] }
          ]
        },
        {
          "type": "listItem",
          "content": [
            { "type": "paragraph", "content": [ { "type": "text", "text": "第二题通常只对应图形区（考趋势）。" } ] }
          ]
        },
        {
          "type": "listItem",
          "content": [
            { "type": "paragraph", "content": [ { "type": "text", "text": "第三题通常只对应表格区（考排序）。" } ] }
          ]
        },
        {
          "type": "listItem",
          "content": [
            { "type": "paragraph", "content": [ { "type": "text", "text": "第四题可能是图表/图文跨越（考除法比重）。" } ] }
          ]
        },
        {
          "type": "listItem",
          "content": [
            { "type": "paragraph", "content": [ { "type": "text", "text": "第五题综合选项判定，分别空降各个模块验证。" } ] }
          ]
        }
      ]
    },
    {
      "type": "highlightBlock",
      "attrs": { "backgroundColor": "#eff6ff", "borderColor": "#3b82f6", "icon": "💡" },
      "content": [
        {
          "type": "paragraph",
          "content": [
            { "type": "text", "text": "降维打击：", "marks": [ { "type": "bold" } ] },
            { "type": "text", "text": "遇到这种大题，做第一小题时，拿手把图和表捂住，只看那段文字。做第二题时捂住文字只看图。用这种“物理隔离”法强行降低视觉负担，心就不乱了。" }
          ]
        }
      ]
    }
  ]
}$$ AS jsonb),
    NULL, '应对海量信息的模块化隔离心法。', category_node.id, CAST('["资料分析", "综合资料", "图文表"]' AS jsonb), FALSE, TRUE, TRUE, NOW(), 0, 0, CAST('{"content_type": "knowledge_point", "category_code": "kp_xingce_data_mixed_all", "source": "fba_content_engine"}' AS jsonb), 1, NOW()
FROM category_node
ON CONFLICT (slug)
DO UPDATE SET
    title = EXCLUDED.title, content_json = EXCLUDED.content_json, summary = EXCLUDED.summary, category_id = EXCLUDED.category_id, tags = EXCLUDED.tags, updated_time = NOW();