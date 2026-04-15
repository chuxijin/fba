WITH category_node AS (
    SELECT id
    FROM sys_category
    WHERE app_code = 'youanshang'
      AND type = 'knowledge_point'
      AND code = 'kp_xingce_data_table_cross'
)
INSERT INTO sys_content (
    app_code, title, slug, content_json, content_html, summary, category_id, tags, is_pinned, is_public, is_published, publish_time, view_count, sort_order, extra, created_by, created_time
)
SELECT
    'gongkao', '交叉表', 'kp-xingce-data-table-cross',
    CAST($${
  "type": "doc",
  "content": [
    {
      "type": "heading",
      "attrs": { "level": 1 },
      "content": [ { "type": "text", "text": "交叉表资料" } ]
    },
    {
      "type": "highlightBlock",
      "attrs": { "backgroundColor": "#fffbeb" },
      "content": [
        {
          "type": "paragraph",
          "content": [
            { "type": "text", "text": "核心策略：" },
            { "type": "text", "text": "死盯缩进和合并单元格，分清父级与子级。", "marks": [ { "type": "bold" } ] }
          ]
        }
      ]
    },
    {
      "type": "paragraph",
      "content": [
        { "type": "text", "text": "交叉表是一种自带层级嵌套的复杂表格。比如表头第一行是“男性、女性”，而“男性”底下又合并囊括了“20岁以下、20-40岁、40岁以上”三列。这就是列嵌套。" }
      ]
    },
    {
      "type": "heading",
      "attrs": { "level": 2 },
      "content": [ { "type": "text", "text": "一、识别交叉表的层级关系" } ]
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
              "content": [ { "type": "text", "text": "看缩进（行嵌套）" } ]
            },
            {
              "type": "paragraph",
              "content": [
                { "type": "text", "text": "在最左侧的分类列，有些项目前面有空格缩进。比如“总计”顶格写，底下有“东部地区”也是顶格，而“江苏、浙江”会往后缩两格。这表示它们属于东部地区的子分类。" }
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
              "content": [ { "type": "text", "text": "看合并框（列嵌套）" } ]
            },
            {
              "type": "paragraph",
              "content": [
                { "type": "text", "text": "表头最上一层是一个长横格（如：本科及以上），下方分出两列短格（男生、女生）。求“本科学历男生”时，必须从第一层进本科，再在第二层锁定男生列。" }
              ]
            }
          ]
        }
      ]
    },
    {
      "type": "heading",
      "attrs": { "level": 2 },
      "content": [ { "type": "text", "text": "二、极高频陷阱" } ]
    },
    {
      "type": "highlightBlock",
      "attrs": { "backgroundColor": "#fef2f2" },
      "content": [
        {
          "type": "paragraph",
          "content": [
            { "type": "text", "text": "重复计算陷阱：", "marks": [ { "type": "bold" } ] }
          ]
        },
        {
          "type": "paragraph",
          "content": [
            { "type": "text", "text": "在存在“行嵌套”（包含缩进子级）的表格里，命题人可能会让你求“以下选项中，XX数值之和大于1000万的有几个？”。如果你没发现选项中既有“东部地区”（父级），又有“江苏”（子级），把它们直接盲目相加，就会导致江苏的数据被重复加了两次！所以在进行加法运算时，必须明确它们是否属于同一平级层级。" }
          ]
        }
      ]
    }
  ]
}$$ AS jsonb),
    NULL, '交叉表行列嵌套关系解析与重复计算陷阱。', category_node.id, CAST('["资料分析", "表格资料", "交叉表"]' AS jsonb), FALSE, TRUE, TRUE, NOW(), 0, 0, CAST('{"content_type": "knowledge_point", "category_code": "kp_xingce_data_table_cross", "source": "fba_content_engine"}' AS jsonb), 1, NOW()
FROM category_node
ON CONFLICT (slug)
DO UPDATE SET
    title = EXCLUDED.title, content_json = EXCLUDED.content_json, summary = EXCLUDED.summary, category_id = EXCLUDED.category_id, tags = EXCLUDED.tags, updated_time = NOW();