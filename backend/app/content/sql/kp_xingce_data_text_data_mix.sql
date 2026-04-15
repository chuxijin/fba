WITH category_node AS (
    SELECT id
    FROM sys_category
    WHERE app_code = 'youanshang'
      AND type = 'knowledge_point'
      AND code = 'kp_xingce_data_text_data_mix'
)
INSERT INTO sys_content (
    app_code, title, slug, content_json, content_html, summary, category_id, tags, is_pinned, is_public, is_published, publish_time, view_count, sort_order, extra, created_by, created_time
)
SELECT
    'gongkao', '文字数据混排', 'kp-xingce-data-text-data-mix',
    CAST($${
  "type": "doc",
  "content": [
    {
      "type": "heading",
      "attrs": { "level": 1 },
      "content": [ { "type": "text", "text": "文字数据混排" } ]
    },
    {
      "type": "highlightBlock",
      "attrs": { "backgroundColor": "#fffbeb" },
      "content": [
        {
          "type": "paragraph",
          "content": [
            { "type": "text", "text": "核心策略：" },
            { "type": "text", "text": "文本看结构，列表看对齐。", "marks": [ { "type": "bold" } ] }
          ]
        }
      ]
    },
    {
      "type": "heading",
      "attrs": { "level": 2 },
      "content": [ { "type": "text", "text": "一、什么是混排？" } ]
    },
    {
      "type": "paragraph",
      "content": [
        { "type": "text", "text": "有些文字资料并不是纯散文段落，而是在文字中夹杂了带序号的列表、条目，或者是没有表格边框但格式对齐的数据阵列（伪表格）。" }
      ]
    },
    {
      "type": "heading",
      "attrs": { "level": 2 },
      "content": [ { "type": "text", "text": "二、解题法宝：明确层级关系" } ]
    },
    {
      "type": "paragraph",
      "content": [
        { "type": "text", "text": "混排材料由于格式的特殊性，天生自带强烈的总分结构属性。列表前的那段文字往往是“总纲”，而列表项则是“分类明细”。" }
      ]
    },
    {
      "type": "orderedList",
      "attrs": { "start": 1 },
      "content": [
        {
          "type": "listItem",
          "content": [
            { "type": "paragraph", "content": [ { "type": "text", "text": "抓住总起句：", "marks": [ { "type": "bold" } ] }, { "type": "text", "text": "在列表前面的段落里寻找“总量”、“总计”的数据，这是计算比重、平均数的关键分母。" } ] }
          ]
        },
        {
          "type": "listItem",
          "content": [
            { "type": "paragraph", "content": [ { "type": "text", "text": "利用排版优势秒定位：", "marks": [ { "type": "bold" } ] }, { "type": "text", "text": "列表项往往首字就是主体名称（如“（一）东部地区... （二）中部地区...”）。找数时直接看行首即可，不必逐字扫描。" } ] }
          ]
        }
      ]
    },
    {
      "type": "heading",
      "attrs": { "level": 2 },
      "content": [ { "type": "text", "text": "三、易错雷区" } ]
    },
    {
      "type": "highlightBlock",
      "attrs": { "backgroundColor": "#fef2f2" },
      "content": [
        {
          "type": "paragraph",
          "content": [
            { "type": "text", "text": "警惕列表分类不全：", "marks": [ { "type": "bold" } ] }
          ]
        },
        {
          "type": "paragraph",
          "content": [
            { "type": "text", "text": "总纲给出总量是 100，下面列了 A、B、C 三个分类，你把 A+B+C 加起来发现只有 90。不要以为题目出错了，而是材料经常只列举“主要分类”，隐藏了“其他”。做题时不要想当然认为列表项加起来等于总数，必须使用总纲中给出的官方总数计算。" }
          ]
        }
      ]
    }
  ]
}$$ AS jsonb),
    NULL, '文字数据混排结构的总分关系剖析。', category_node.id, CAST('["资料分析", "材料识别", "数据混排"]' AS jsonb), FALSE, TRUE, TRUE, NOW(), 0, 0, CAST('{"content_type": "knowledge_point", "category_code": "kp_xingce_data_text_data_mix", "source": "fba_content_engine"}' AS jsonb), 1, NOW()
FROM category_node
ON CONFLICT (slug)
DO UPDATE SET
    title = EXCLUDED.title, content_json = EXCLUDED.content_json, summary = EXCLUDED.summary, category_id = EXCLUDED.category_id, tags = EXCLUDED.tags, updated_time = NOW();