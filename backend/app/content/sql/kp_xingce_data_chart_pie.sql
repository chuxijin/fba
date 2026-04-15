WITH category_node AS (
    SELECT id
    FROM sys_category
    WHERE app_code = 'youanshang'
      AND type = 'knowledge_point'
      AND code = 'kp_xingce_data_chart_pie'
)
INSERT INTO sys_content (
    app_code, title, slug, content_json, content_html, summary, category_id, tags, is_pinned, is_public, is_published, publish_time, view_count, sort_order, extra, created_by, created_time
)
SELECT
    'gongkao', '饼图', 'kp-xingce-data-chart-pie',
    CAST($${
  "type": "doc",
  "content": [
    {
      "type": "heading",
      "attrs": { "level": 1 },
      "content": [ { "type": "text", "text": "饼图" } ]
    },
    {
      "type": "highlightBlock",
      "attrs": { "backgroundColor": "#fffbeb" },
      "content": [
        {
          "type": "paragraph",
          "content": [
            { "type": "text", "text": "核心策略：" },
            { "type": "text", "text": "饼图天生自带“部分与整体”的结构，主要用来考察比重问题。", "marks": [ { "type": "bold" } ] }
          ]
        }
      ]
    },
    {
      "type": "heading",
      "attrs": { "level": 2 },
      "content": [ { "type": "text", "text": "一、秒定半壁江山法" } ]
    },
    {
      "type": "paragraph",
      "content": [
        { "type": "text", "text": "饼图的形状可以用来进行快速的排除和估算：" }
      ]
    },
    {
      "type": "bulletList",
      "content": [
        {
          "type": "listItem",
          "content": [
            { "type": "paragraph", "content": [ { "type": "text", "text": "半圆（一条平直的直径）：代表刚好 50%。" } ] }
          ]
        },
        {
          "type": "listItem",
          "content": [
            { "type": "paragraph", "content": [ { "type": "text", "text": "直角扇形（90度）：代表刚好 25%。" } ] }
          ]
        },
        {
          "type": "listItem",
          "content": [
            { "type": "paragraph", "content": [ { "type": "text", "text": "锐角扇形（<90度）：代表一定小于 25%。" } ] }
          ]
        }
      ]
    },
    {
      "type": "paragraph",
      "content": [
        { "type": "text", "text": "当选项差距很大时，直接通过观察目标扇形的角度，就能秒杀判断其比重在哪个区间。" }
      ]
    },
    {
      "type": "heading",
      "attrs": { "level": 2 },
      "content": [ { "type": "text", "text": "二、饼图的两类数据" } ]
    },
    {
      "type": "paragraph",
      "content": [
        { "type": "text", "text": "饼图上的标注通常有两种形式，做题时一定要看清：" }
      ]
    },
    {
      "type": "orderedList",
      "attrs": { "start": 1 },
      "content": [
        {
          "type": "listItem",
          "content": [
            { "type": "paragraph", "content": [ { "type": "text", "text": "标的是百分比（%）：", "marks": [ { "type": "bold" } ] }, { "type": "text", "text": "只告诉你占比，不能直接当绝对量用。要求绝对量必须回头去找“总盘子”是多少。" } ] }
          ]
        },
        {
          "type": "listItem",
          "content": [
            { "type": "paragraph", "content": [ { "type": "text", "text": "标的是绝对量（如：350万元）：", "marks": [ { "type": "bold" } ] }, { "type": "text", "text": "这时如果你要求比重，必须老老实实把所有切片的绝对量加起来当分母。" } ] }
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
            { "type": "text", "text": "易错坑点：", "marks": [ { "type": "bold" } ] },
            { "type": "text", "text": "题目给出2023年的饼图，问2022年（基期）某部分的比重图长什么样。千万不要直接用现期饼图的大小去选！因为不同部分的增长率不同，比重会发生变化，必须算出基期数据后再定型。" }
          ]
        }
      ]
    }
  ]
}$$ AS jsonb),
    NULL, '利用饼图直角、平角秒定比重，规避图上单位陷阱。', category_node.id, CAST('["资料分析", "图形资料", "饼图", "比重"]' AS jsonb), FALSE, TRUE, TRUE, NOW(), 0, 0, CAST('{"content_type": "knowledge_point", "category_code": "kp_xingce_data_chart_pie", "source": "fba_content_engine"}' AS jsonb), 1, NOW()
FROM category_node
ON CONFLICT (slug)
DO UPDATE SET
    title = EXCLUDED.title, content_json = EXCLUDED.content_json, summary = EXCLUDED.summary, category_id = EXCLUDED.category_id, tags = EXCLUDED.tags, updated_time = NOW();