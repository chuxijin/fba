WITH category_node AS (
    SELECT id
    FROM sys_category
    WHERE app_code = 'youanshang'
      AND type = 'knowledge_point'
      AND code = 'kp_xingce_data_table_single'
)
INSERT INTO sys_content (
    app_code, title, slug, content_json, content_html, summary, category_id, tags, is_pinned, is_public, is_published, publish_time, view_count, sort_order, extra, created_by, created_time
)
SELECT
    'gongkao', '单表', 'kp-xingce-data-table-single',
    CAST($${
  "type": "doc",
  "content": [
    {
      "type": "heading",
      "attrs": { "level": 1 },
      "content": [ { "type": "text", "text": "单表资料" } ]
    },
    {
      "type": "highlightBlock",
      "attrs": { "backgroundColor": "#fffbeb" },
      "content": [
        {
          "type": "paragraph",
          "content": [
            { "type": "text", "text": "核心策略：" },
            { "type": "text", "text": "十字交叉法找交点，注意“合计”与分项的验证。", "marks": [ { "type": "bold" } ] }
          ]
        }
      ]
    },
    {
      "type": "paragraph",
      "content": [
        { "type": "text", "text": "单表找数极其简单，只需要将题干中的两个关键词作为“横坐标”和“纵坐标”，在表格中找到它们的交叉点即可提取出准确数据。" }
      ]
    },
    {
      "type": "heading",
      "attrs": { "level": 2 },
      "content": [ { "type": "text", "text": "一、秒定交点法" } ]
    },
    {
      "type": "text-diagram",
      "attrs": {
        "type": "mermaid",
        "content": "flowchart TD\nA[阅读题目: 2023年江苏省的进出口总额是多少?] --> B[找横排: 定位列标题 进出口总额]\nB --> C[找竖排: 定位行标题 江苏省]\nC --> D[十字交叉: 行列交点即为目标数值]"
      }
    },
    {
      "type": "heading",
      "attrs": { "level": 2 },
      "content": [ { "type": "text", "text": "二、单表的特殊结构：合计项" } ]
    },
    {
      "type": "paragraph",
      "content": [
        { "type": "text", "text": "大多数单表在最上方（或最下方）会有一行名为“总计”或“合计”。在计算比重时，这往往是分母的最快获取渠道。" }
      ]
    },
    {
      "type": "highlightBlock",
      "attrs": { "backgroundColor": "#fef2f2" },
      "content": [
        {
          "type": "paragraph",
          "content": [
            { "type": "text", "text": "避坑指南：隐去合计的表格", "marks": [ { "type": "bold" } ] }
          ]
        },
        {
          "type": "paragraph",
          "content": [
            { "type": "text", "text": "有时表格不给“合计”行，但让你求“某项在整体中的比重”。此时必须耐下心来把表格某一列的所有分项相加，绝不能漏加或者错把某个大类下的子类当成平级的类加进去。" }
          ]
        }
      ]
    }
  ]
}$$ AS jsonb),
    NULL, '单表的十字交叉找数法及合计项计算提醒。', category_node.id, CAST('["资料分析", "表格资料", "单表"]' AS jsonb), FALSE, TRUE, TRUE, NOW(), 0, 0, CAST('{"content_type": "knowledge_point", "category_code": "kp_xingce_data_table_single", "source": "fba_content_engine"}' AS jsonb), 1, NOW()
FROM category_node
ON CONFLICT (slug)
DO UPDATE SET
    title = EXCLUDED.title, content_json = EXCLUDED.content_json, summary = EXCLUDED.summary, category_id = EXCLUDED.category_id, tags = EXCLUDED.tags, updated_time = NOW();