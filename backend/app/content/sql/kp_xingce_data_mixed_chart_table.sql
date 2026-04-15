WITH category_node AS (
    SELECT id
    FROM sys_category
    WHERE app_code = 'youanshang'
      AND type = 'knowledge_point'
      AND code = 'kp_xingce_data_mixed_chart_table'
)
INSERT INTO sys_content (
    app_code, title, slug, content_json, content_html, summary, category_id, tags, is_pinned, is_public, is_published, publish_time, view_count, sort_order, extra, created_by, created_time
)
SELECT
    'gongkao', '图表综合', 'kp-xingce-data-mixed-chart-table',
    CAST($${
  "type": "doc",
  "content": [
    {
      "type": "heading",
      "attrs": { "level": 1 },
      "content": [ { "type": "text", "text": "图表综合" } ]
    },
    {
      "type": "highlightBlock",
      "attrs": { "backgroundColor": "#fffbeb" },
      "content": [
        {
          "type": "paragraph",
          "content": [
            { "type": "text", "text": "核心策略：" },
            { "type": "text", "text": "图定时间面，表定空间面（一维+二维）。", "marks": [ { "type": "bold" } ] }
          ]
        }
      ]
    },
    {
      "type": "paragraph",
      "content": [
        { "type": "text", "text": "图表综合是信息量最大的一种形式。因为图形（如图1）和表格（如表1）各自都能承载巨大的数据量。" }
      ]
    },
    {
      "type": "heading",
      "attrs": { "level": 2 },
      "content": [ { "type": "text", "text": "一、看清“经纬度”" } ]
    },
    {
      "type": "paragraph",
      "content": [
        { "type": "text", "text": "绝大多数情况下，图表综合是这样分配任务的：" }
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
              "content": [ { "type": "text", "text": "图的任务（时间维度）" } ]
            },
            {
              "type": "paragraph",
              "content": [
                { "type": "text", "text": "用柱状图+折线图的形式，展示全国层面 2018-2023 连续数年的宏观大盘走势（总量与增速）。" }
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
              "content": [ { "type": "text", "text": "表的任务（空间拆解维度）" } ]
            },
            {
              "type": "paragraph",
              "content": [
                { "type": "text", "text": "专门针对最新一年（如2023年），用表格的形式把全国大盘拆解给 31 个省份，或者拆解给不同的产业门类。" }
              ]
            }
          ]
        }
      ]
    },
    {
      "type": "heading",
      "attrs": { "level": 2 },
      "content": [ { "type": "text", "text": "二、跨区取数实战" } ]
    },
    {
      "type": "text-diagram",
      "attrs": {
        "type": "mermaid",
        "content": "flowchart TD\nA[题目: 2022年江苏省的产值占全国的比重是多少?] --> B[找江苏: 在 表格 里找江苏2023产值和增速, 推算出2022年江苏产值 分子]\nB --> C[找全国: 去 图形 里直接读出2022年全国总产值对应的柱子 分母]\nC --> D[分子除以分母得出答案]"
      }
    },
    {
      "type": "highlightBlock",
      "attrs": { "backgroundColor": "#fef2f2" },
      "content": [
        {
          "type": "paragraph",
          "content": [
            { "type": "text", "text": "注意口径对齐：", "marks": [ { "type": "bold" } ] }
          ]
        },
        {
          "type": "paragraph",
          "content": [
            { "type": "text", "text": "有时候图叫“规模以上工业增加值”，表叫“高技术制造业增加值”。这是包含关系，取数做除法前，确认题干问的是谁在谁里的比重，谁去分子谁去分母。" }
          ]
        }
      ]
    }
  ]
}$$ AS jsonb),
    NULL, '图表综合题时间的宏观大势与空间的微观拆解。', category_node.id, CAST('["资料分析", "综合资料", "图表综合"]' AS jsonb), FALSE, TRUE, TRUE, NOW(), 0, 0, CAST('{"content_type": "knowledge_point", "category_code": "kp_xingce_data_mixed_chart_table", "source": "fba_content_engine"}' AS jsonb), 1, NOW()
FROM category_node
ON CONFLICT (slug)
DO UPDATE SET
    title = EXCLUDED.title, content_json = EXCLUDED.content_json, summary = EXCLUDED.summary, category_id = EXCLUDED.category_id, tags = EXCLUDED.tags, updated_time = NOW();