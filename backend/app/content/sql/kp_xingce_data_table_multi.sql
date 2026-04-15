WITH category_node AS (
    SELECT id
    FROM sys_category
    WHERE app_code = 'youanshang'
      AND type = 'knowledge_point'
      AND code = 'kp_xingce_data_table_multi'
)
INSERT INTO sys_content (
    app_code, title, slug, content_json, content_html, summary, category_id, tags, is_pinned, is_public, is_published, publish_time, view_count, sort_order, extra, created_by, created_time
)
SELECT
    'gongkao', '多表', 'kp-xingce-data-table-multi',
    CAST($${
  "type": "doc",
  "content": [
    {
      "type": "heading",
      "attrs": { "level": 1 },
      "content": [ { "type": "text", "text": "多表资料" } ]
    },
    {
      "type": "highlightBlock",
      "attrs": { "backgroundColor": "#fffbeb" },
      "content": [
        {
          "type": "paragraph",
          "content": [
            { "type": "text", "text": "核心策略：" },
            { "type": "text", "text": "多表必问表头，切忌南辕北辙找错表。", "marks": [ { "type": "bold" } ] }
          ]
        }
      ]
    },
    {
      "type": "paragraph",
      "content": [
        { "type": "text", "text": "多表题目的难点不在于计算，而在于“检索路径跨度大”。比如表1是农产品产量，表2是农产品出口量。题目问：“2023年小麦的出口比重是多少？” 需要在表2找出口量（分子），在表1找产量（分母）。" }
      ]
    },
    {
      "type": "heading",
      "attrs": { "level": 2 },
      "content": [ { "type": "text", "text": "一、做题前的宏观扫描" } ]
    },
    {
      "type": "paragraph",
      "content": [
        { "type": "text", "text": "面对两个或三个表格，用 10 秒钟快速扫描它们的表标题，建立关联认知：" }
      ]
    },
    {
      "type": "bulletList",
      "content": [
        {
          "type": "listItem",
          "content": [
            { "type": "paragraph", "content": [ { "type": "text", "text": "表1标题：全国各省 GDP —— 决定了“省份”的绝对量在这张表。" } ] }
          ]
        },
        {
          "type": "listItem",
          "content": [
            { "type": "paragraph", "content": [ { "type": "text", "text": "表2标题：全国各省 人口数 —— 决定了“人数”在这里。" } ] }
          ]
        }
      ]
    },
    {
      "type": "paragraph",
      "content": [
        { "type": "text", "text": "题目如果问“人均GDP”，你的大脑应该立刻反应：这是表1除以表2的跨表运算。" }
      ]
    },
    {
      "type": "heading",
      "attrs": { "level": 2 },
      "content": [ { "type": "text", "text": "二、跨表陷阱" } ]
    },
    {
      "type": "highlightBlock",
      "attrs": { "backgroundColor": "#fef2f2" },
      "content": [
        {
          "type": "paragraph",
          "content": [
            { "type": "text", "text": "错位风险：", "marks": [ { "type": "bold" } ] }
          ]
        },
        {
          "type": "paragraph",
          "content": [
            { "type": "text", "text": "有些多表资料中，表1和表2的分类顺序可能不一样！比如表1的省份顺序是“北京、上海、广东”，而表2由于是按人口排序的，变成了“广东、山东、河南”。在跨表取数时，绝对不能习惯性认为都在第一行，必须重新在表2按照“北京”二字去定位！" }
          ]
        }
      ]
    }
  ]
}$$ AS jsonb),
    NULL, '多表资料跨表取数逻辑及排序错位防范。', category_node.id, CAST('["资料分析", "表格资料", "多表"]' AS jsonb), FALSE, TRUE, TRUE, NOW(), 0, 0, CAST('{"content_type": "knowledge_point", "category_code": "kp_xingce_data_table_multi", "source": "fba_content_engine"}' AS jsonb), 1, NOW()
FROM category_node
ON CONFLICT (slug)
DO UPDATE SET
    title = EXCLUDED.title, content_json = EXCLUDED.content_json, summary = EXCLUDED.summary, category_id = EXCLUDED.category_id, tags = EXCLUDED.tags, updated_time = NOW();