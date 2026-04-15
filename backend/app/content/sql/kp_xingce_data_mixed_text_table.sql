WITH category_node AS (
    SELECT id
    FROM sys_category
    WHERE app_code = 'youanshang'
      AND type = 'knowledge_point'
      AND code = 'kp_xingce_data_mixed_text_table'
)
INSERT INTO sys_content (
    app_code, title, slug, content_json, content_html, summary, category_id, tags, is_pinned, is_public, is_published, publish_time, view_count, sort_order, extra, created_by, created_time
)
SELECT
    'gongkao', '文表综合', 'kp-xingce-data-mixed-text-table',
    CAST($${
  "type": "doc",
  "content": [
    {
      "type": "heading",
      "attrs": { "level": 1 },
      "content": [ { "type": "text", "text": "文表综合" } ]
    },
    {
      "type": "highlightBlock",
      "attrs": { "backgroundColor": "#fffbeb" },
      "content": [
        {
          "type": "paragraph",
          "content": [
            { "type": "text", "text": "核心策略：" },
            { "type": "text", "text": "文字负责“定基调”（宏观数据），表格负责“铺明细”（微观数据）。", "marks": [ { "type": "bold" } ] }
          ]
        }
      ]
    },
    {
      "type": "paragraph",
      "content": [
        { "type": "text", "text": "在文表综合中，文字通常较短，放在表格正上方或正下方。这种组合是最好找数据的组合。" }
      ]
    },
    {
      "type": "heading",
      "attrs": { "level": 2 },
      "content": [ { "type": "text", "text": "一、经典考法：求整体中的比重" } ]
    },
    {
      "type": "paragraph",
      "content": [
        { "type": "text", "text": "这是文表综合最爱的考法。题目要求计算表格中某一项在“全国/全省”大盘子里的比重。" }
      ]
    },
    {
      "type": "bulletList",
      "content": [
        {
          "type": "listItem",
          "content": [
            { "type": "paragraph", "content": [ { "type": "text", "text": "找分子：" }, { "type": "text", "text": "直接在", "marks": [ { "type": "bold" } ] }, { "type": "text", "text": "表格", "marks": [ { "type": "bold", "type": "textStyle", "color": "#2563eb" } ] }, { "type": "text", "text": "里定位某地市、某产业的具体数值。", "marks": [ { "type": "bold" } ] } ] }
          ]
        },
        {
          "type": "listItem",
          "content": [
            { "type": "paragraph", "content": [ { "type": "text", "text": "找分母（总盘子）：" }, { "type": "text", "text": "如果表格没有“总计”行，千万别去傻傻加和！总盘子（如全国GDP总值）必定写在表格上方的", "marks": [ { "type": "bold" } ] }, { "type": "text", "text": "文字段落", "marks": [ { "type": "bold", "type": "textStyle", "color": "#ef4444" } ] }, { "type": "text", "text": "里。", "marks": [ { "type": "bold" } ] } ] }
          ]
        }
      ]
    },
    {
      "type": "heading",
      "attrs": { "level": 2 },
      "content": [ { "type": "text", "text": "二、经典考法：缺失信息的补充" } ]
    },
    {
      "type": "paragraph",
      "content": [
        { "type": "text", "text": "有时候你看表格，发现第一行只有“现期量”，死活找不到“增长率”。不要慌，去扫一眼旁边的文字段。文字段里一定写着“……其中各项指标增长率如下：A为... B为...”。" }
      ]
    },
    {
      "type": "highlightBlock",
      "attrs": { "backgroundColor": "#fef2f2" },
      "content": [
        {
          "type": "paragraph",
          "content": [
            { "type": "text", "text": "避坑指南：单位不统一", "marks": [ { "type": "bold" } ] }
          ]
        },
        {
          "type": "paragraph",
          "content": [
            { "type": "text", "text": "跨文字和表格取数时，最容易踩的坑就是单位错位。比如文字说“全国总计 1.2 ", "marks": [ { "type": "bold" } ] }, { "type": "text", "text": "万亿", "marks": [ { "type": "bold", "type": "textStyle", "color": "#ef4444" } ] }, { "type": "text", "text": "元”，表格里给的是“各省数据（单位：", "marks": [ { "type": "bold" } ] }, { "type": "text", "text": "亿元", "marks": [ { "type": "bold", "type": "textStyle", "color": "#2563eb" } ] }, { "type": "text", "text": "）”。在进行除法前，必须在脑子里换算好量级，否则容易差小数点。" }
          ]
        }
      ]
    }
  ]
}$$ AS jsonb),
    NULL, '文字给宏观总量，表格铺微观细节的结合套路。', category_node.id, CAST('["资料分析", "综合资料", "文表综合"]' AS jsonb), FALSE, TRUE, TRUE, NOW(), 0, 0, CAST('{"content_type": "knowledge_point", "category_code": "kp_xingce_data_mixed_text_table", "source": "fba_content_engine"}' AS jsonb), 1, NOW()
FROM category_node
ON CONFLICT (slug)
DO UPDATE SET
    title = EXCLUDED.title, content_json = EXCLUDED.content_json, summary = EXCLUDED.summary, category_id = EXCLUDED.category_id, tags = EXCLUDED.tags, updated_time = NOW();