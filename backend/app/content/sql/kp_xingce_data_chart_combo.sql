WITH category_node AS (
    SELECT id
    FROM sys_category
    WHERE app_code = 'youanshang'
      AND type = 'knowledge_point'
      AND code = 'kp_xingce_data_chart_combo'
)
INSERT INTO sys_content (
    app_code, title, slug, content_json, content_html, summary, category_id, tags, is_pinned, is_public, is_published, publish_time, view_count, sort_order, extra, created_by, created_time
)
SELECT
    'gongkao', '复合图', 'kp-xingce-data-chart-combo',
    CAST($${
  "type": "doc",
  "content": [
    {
      "type": "heading",
      "attrs": { "level": 1 },
      "content": [ { "type": "text", "text": "复合图" } ]
    },
    {
      "type": "highlightBlock",
      "attrs": { "backgroundColor": "#fffbeb" },
      "content": [
        {
          "type": "paragraph",
          "content": [
            { "type": "text", "text": "核心策略：" },
            { "type": "text", "text": "双轴图必须“各回各家”，绝对不能张冠李戴读错轴。", "marks": [ { "type": "bold" } ] }
          ]
        }
      ]
    },
    {
      "type": "paragraph",
      "content": [
        { "type": "text", "text": "复合图在考试中占比极高，最典型的形式是：柱状图 + 折线图 共存于一张图表中，且分别对应左、右两根纵轴。" }
      ]
    },
    {
      "type": "heading",
      "attrs": { "level": 2 },
      "content": [ { "type": "text", "text": "一、双轴看图法则" } ]
    },
    {
      "type": "paragraph",
      "content": [
        { "type": "text", "text": "复合图最致命的陷阱就是左右轴看反。破解口诀：" }
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
              "content": [ { "type": "text", "text": "看图例对号入座" } ]
            },
            {
              "type": "paragraph",
              "content": [
                { "type": "text", "text": "通常，柱子代表绝对量（如GDP、产量），读左边纵坐标（亿元、万吨等）；折线代表相对量（如增长率、占比），读右边纵坐标（%）。" }
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
              "content": [ { "type": "text", "text": "拿尺子隔绝视线" } ]
            },
            {
              "type": "paragraph",
              "content": [
                { "type": "text", "text": "在看右边折线的数值时，如果有必要，用笔或尺子把左边的纵轴挡住，强制自己向右水平划线寻找读数。" }
              ]
            }
          ]
        }
      ]
    },
    {
      "type": "heading",
      "attrs": { "level": 2 },
      "content": [ { "type": "text", "text": "二、常考组合：当年量 vs 累计量" } ]
    },
    {
      "type": "paragraph",
      "content": [
        { "type": "text", "text": "除了量+率组合，复合图有时会出现柱子和折线都是绝对量的情况，此时必然一个是“当月量”，一个是“累计量”（1-N月量）。" }
      ]
    },
    {
      "type": "bulletList",
      "content": [
        {
          "type": "listItem",
          "content": [
            { "type": "paragraph", "content": [ { "type": "text", "text": "求特定月份：", "marks": [ { "type": "bold" } ] }, { "type": "text", "text": "如果图表给出的是1-3月累计值和1-2月累计值，要求3月当月值，必须用累计值相减。千万不要直接拿3月对应的那根柱子去当做单月量！" } ] }
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
            { "type": "text", "text": "极易错点：", "marks": [ { "type": "bold" } ] },
            { "type": "text", "text": "在量+率的图表中，折线的最低点（最低的百分比）不代表此时的柱子（绝对量）也最小。绝对量和增长率没有必然的大小绑定关系，千万不要看着折线最低就去选此时对应的年份量最小！" }
          ]
        }
      ]
    }
  ]
}$$ AS jsonb),
    NULL, '复合双轴图左右开弓法，死防张冠李戴。', category_node.id, CAST('["资料分析", "图形资料", "复合图", "双轴图"]' AS jsonb), FALSE, TRUE, TRUE, NOW(), 0, 0, CAST('{"content_type": "knowledge_point", "category_code": "kp_xingce_data_chart_combo", "source": "fba_content_engine"}' AS jsonb), 1, NOW()
FROM category_node
ON CONFLICT (slug)
DO UPDATE SET
    title = EXCLUDED.title, content_json = EXCLUDED.content_json, summary = EXCLUDED.summary, category_id = EXCLUDED.category_id, tags = EXCLUDED.tags, updated_time = NOW();