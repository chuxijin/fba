WITH category_node AS (
    SELECT id
    FROM sys_category
    WHERE app_code = 'youanshang'
      AND type = 'knowledge_point'
      AND code = 'kp_xingce_data_chart_line'
)
INSERT INTO sys_content (
    app_code, title, slug, content_json, content_html, summary, category_id, tags, is_pinned, is_public, is_published, publish_time, view_count, sort_order, extra, created_by, created_time
)
SELECT
    'gongkao', '折线图', 'kp-xingce-data-chart-line',
    CAST($${
  "type": "doc",
  "content": [
    {
      "type": "heading",
      "attrs": { "level": 1 },
      "content": [ { "type": "text", "text": "折线图" } ]
    },
    {
      "type": "highlightBlock",
      "attrs": { "backgroundColor": "#fffbeb" },
      "content": [
        {
          "type": "paragraph",
          "content": [
            { "type": "text", "text": "核心策略：" },
            { "type": "text", "text": "看趋势重于看数值，斜率暗含增长率大小。", "marks": [ { "type": "bold" } ] }
          ]
        }
      ]
    },
    {
      "type": "paragraph",
      "content": [
        { "type": "text", "text": "折线图最擅长展示数据随时间的“变化趋势”。行测中常常用折线图来代表增长率（%）、比重或者某项指数的变化。" }
      ]
    },
    {
      "type": "heading",
      "attrs": { "level": 2 },
      "content": [ { "type": "text", "text": "一、如何看“斜率”" } ]
    },
    {
      "type": "paragraph",
      "content": [
        { "type": "text", "text": "如果折线图没有标注具体数值，题目又问“哪一年增长最快（增量/增长率）”：" }
      ]
    },
    {
      "type": "bulletList",
      "content": [
        {
          "type": "listItem",
          "content": [
            { "type": "paragraph", "content": [ { "type": "text", "text": "线越“陡峭”，说明变化越剧烈。" } ] }
          ]
        },
        {
          "type": "listItem",
          "content": [
            { "type": "paragraph", "content": [ { "type": "text", "text": "线越“平缓”，说明数据比较平稳。" } ] }
          ]
        },
        {
          "type": "listItem",
          "content": [
            { "type": "paragraph", "content": [ { "type": "text", "text": "向下折的线段代表出现“负增长”。" } ] }
          ]
        }
      ]
    },
    {
      "type": "heading",
      "attrs": { "level": 2 },
      "content": [ { "type": "text", "text": "二、负数区陷阱" } ]
    },
    {
      "type": "paragraph",
      "content": [
        { "type": "text", "text": "当折线代表“增长率”时，横坐标轴的 0 轴是生死线：" }
      ]
    },
    {
      "type": "bulletList",
      "content": [
        {
          "type": "listItem",
          "content": [
            { "type": "paragraph", "content": [ { "type": "text", "text": "在 0 轴以上折线不论怎么上下波动，只要没跌破 0，说明每年的绝对量都在" }, { "type": "text", "text": "增加", "marks": [ { "type": "bold" } ] }, { "type": "text", "text": "（哪怕折线往下走，也只是增得慢了）。" } ] }
          ]
        },
        {
          "type": "listItem",
          "content": [
            { "type": "paragraph", "content": [ { "type": "text", "text": "只有折线穿过 0 轴掉到下方，才说明当年的绝对量" }, { "type": "text", "text": "减少", "marks": [ { "type": "bold" } ] }, { "type": "text", "text": "了。" } ] }
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
            { "type": "text", "text": "避坑提示：", "marks": [ { "type": "bold" } ] },
            { "type": "text", "text": "题目问：“某量在图示年份中连年增长。” 只要你看到代表增长率的折线都在 0 轴之上，这句话就是对的，别管那根线是不是滑坡形状！" }
          ]
        }
      ]
    }
  ]
}$$ AS jsonb),
    NULL, '折线图看趋势、斜率，识别零轴上下的增减陷阱。', category_node.id, CAST('["资料分析", "图形资料", "折线图"]' AS jsonb), FALSE, TRUE, TRUE, NOW(), 0, 0, CAST('{"content_type": "knowledge_point", "category_code": "kp_xingce_data_chart_line", "source": "fba_content_engine"}' AS jsonb), 1, NOW()
FROM category_node
ON CONFLICT (slug)
DO UPDATE SET
    title = EXCLUDED.title, content_json = EXCLUDED.content_json, summary = EXCLUDED.summary, category_id = EXCLUDED.category_id, tags = EXCLUDED.tags, updated_time = NOW();