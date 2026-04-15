WITH category_node AS (
    SELECT id
    FROM sys_category
    WHERE app_code = 'youanshang'
      AND type = 'knowledge_point'
      AND code = 'kp_xingce_data_chart_bar'
)
INSERT INTO sys_content (
    app_code, title, slug, content_json, content_html, summary, category_id, tags, is_pinned, is_public, is_published, publish_time, view_count, sort_order, extra, created_by, created_time
)
SELECT
    'gongkao', '柱状图', 'kp-xingce-data-chart-bar',
    CAST($${
  "type": "doc",
  "content": [
    {
      "type": "heading",
      "attrs": { "level": 1 },
      "content": [ { "type": "text", "text": "柱状图" } ]
    },
    {
      "type": "highlightBlock",
      "attrs": { "backgroundColor": "#fffbeb" },
      "content": [
        {
          "type": "paragraph",
          "content": [
            { "type": "text", "text": "核心策略：" },
            { "type": "text", "text": "用尺子比高低，注意堆叠图的“减法”。", "marks": [ { "type": "bold" } ] }
          ]
        }
      ]
    },
    {
      "type": "paragraph",
      "content": [
        { "type": "text", "text": "柱状图最能直观反映绝对量的大小。在资料分析中，遇到柱状图，找极大值、极小值或者看整体增减趋势是最快的。" }
      ]
    },
    {
      "type": "heading",
      "attrs": { "level": 2 },
      "content": [ { "type": "text", "text": "一、普通柱状图" } ]
    },
    {
      "type": "paragraph",
      "content": [
        { "type": "text", "text": "找数最简单，直接读取柱子顶端标注的数字即可。如果没标数字，可以用考场上携带的直尺去横坐标轴上比对读数。" }
      ]
    },
    {
      "type": "heading",
      "attrs": { "level": 2 },
      "content": [ { "type": "text", "text": "二、难点：堆叠柱状图" } ]
    },
    {
      "type": "paragraph",
      "content": [
        { "type": "text", "text": "堆叠柱状图是把 A 和 B 两个部分量上下拼成一根柱子。这是柱状图题型中最容易失分的地方。" }
      ]
    },
    {
      "type": "columns",
      "attrs": { "cols": 2 },
      "content": [
        {
          "type": "column",
          "attrs": { "index": 0 },
          "content": [
            {
              "type": "heading",
              "attrs": { "level": 3 },
              "content": [ { "type": "text", "text": "底部柱子" } ]
            },
            {
              "type": "paragraph",
              "content": [
                { "type": "text", "text": "紧贴横坐标的底层柱子，可以直接通过左侧纵轴读出其具体数值。" }
              ]
            }
          ]
        },
        {
          "type": "column",
          "attrs": { "index": 1 },
          "content": [
            {
              "type": "heading",
              "attrs": { "level": 3 },
              "content": [ { "type": "text", "text": "上部悬空柱子" } ]
            },
            {
              "type": "paragraph",
              "content": [
                { "type": "text", "text": "悬在半空的柱子，", "marks": [ { "type": "bold" } ] },
                { "type": "text", "text": "绝对不能直接读纵坐标刻度", "marks": [ { "type": "bold", "type": "textStyle", "color": "#ef4444" } ] },
                { "type": "text", "text": "！必须用其顶端对应数值 减去 底端对应数值，才是它真实的量。" }
              ]
            }
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
            { "type": "text", "text": "易错提醒：", "marks": [ { "type": "bold" } ] },
            { "type": "text", "text": "很多考生在看堆叠图的上半部分时，习惯性往左横划看纵坐标，读出来的其实是“整体总量”，从而导致算错比重和增长率。记住：悬空柱 = 上刻度 - 下刻度。" }
          ]
        }
      ]
    }
  ]
}$$ AS jsonb),
    NULL, '柱状图的读取技巧与堆叠图计算陷阱。', category_node.id, CAST('["资料分析", "图形资料", "柱状图"]' AS jsonb), FALSE, TRUE, TRUE, NOW(), 0, 0, CAST('{"content_type": "knowledge_point", "category_code": "kp_xingce_data_chart_bar", "source": "fba_content_engine"}' AS jsonb), 1, NOW()
FROM category_node
ON CONFLICT (slug)
DO UPDATE SET
    title = EXCLUDED.title, content_json = EXCLUDED.content_json, summary = EXCLUDED.summary, category_id = EXCLUDED.category_id, tags = EXCLUDED.tags, updated_time = NOW();