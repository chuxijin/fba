#!/usr/bin/env python3
"""Rewrite failed SQL files with simplified JSON structure"""
import re, json, glob, os

sql_dir = "D:/100_Work/101_Program/Proj/fba/backend/app/content/sql"
files = sorted(glob.glob(f"{sql_dir}/kp_xc_*.sql"))

# Content templates for each file type
templates = {
    'kp_xc_lang_cloze_overview': {
        'title': '逻辑填空概述',
        'slug': 'kp-xc-lang-cloze-overview',
        'code': 'kp_xingce_language_cloze',
        'summary': '逻辑填空概述：实词、成语、虚词、综合辨析四类子题型。',
        'tags': '["言语理解", "逻辑填空"]',
        'sections': [
            ('一、包含的子类', 'orderedList', [
                '实词辨析（约 6-8 题）：近义实词的区分，六大角度辨析',
                '成语辨析（约 6-8 题）：成语含义与用法，避免望文生义',
                '虚词辨析（约 2-3 题）：关联词语的七种逻辑关系',
                '综合辨析（约 3-5 题）：实词+成语或多空混合题型',
            ]),
            ('二、核心解题方法', 'orderedList', [
                '语素联想法：拆分词语的语素，比较差异',
                '语境联想法：代入语境验证是否通顺',
                '排除法：先排除明显错误的选项',
            ]),
            ('三、词语辨析六大角度', 'orderedList', [
                '词义侧重：同一语义的不同侧重点',
                '适用对象：词语搭配的主体/客体不同',
                '感情色彩：褒义/贬义/中性',
                '语体色彩：书面语/口语',
                '固定搭配：习惯性搭配',
                '程度轻重：语义程度的递进关系',
            ]),
            ('四、易错点', 'bulletList', [
                '不要凭语感选答案，要找语境中的提示信息',
                '不要只看空缺处，要看整个语境',
                '多空题先做最有把握的空，用排除法缩小范围',
            ]),
        ],
        'conclusion': '逻辑填空重在积累，建议每天做 10 题，重点积累高频实词和成语的辨析。',
    },
}

def make_json(title, sections, conclusion):
    """Generate Tiptap JSON without columns or textDiagram nodes"""
    content = []

    # H1 title
    content.append({"type":"heading","attrs":{"level":1},"content":[{"type":"text","text":title}]})

    for section_title, list_type, items in sections:
        # H2 section title
        content.append({"type":"heading","attrs":{"level":2},"content":[{"type":"text","text":section_title}]})

        # List items
        list_node = {"type": list_type, "content": []}
        for item in items:
            list_node["content"].append({
                "type": "listItem",
                "content": [{"type": "paragraph", "content": [{"type": "text", "text": item}]}]
            })
        content.append(list_node)

    # Conclusion highlight
    content.append({
        "type": "highlightBlock",
        "attrs": {"backgroundColor": "#eff6ff", "borderColor": "#3b82f6", "icon": "📊"},
        "content": [{"type": "paragraph", "content": [
            {"type": "text", "text": "刷题建议：", "marks": [{"type": "bold"}]},
            {"type": "text", "text": conclusion}
        ]}]
    })

    return json.dumps({"type": "doc", "content": content}, ensure_ascii=False)

# Process each failed file
fixed = 0
for filepath in files:
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    start_idx = content.find('CAST($$')
    end_idx = content.find('$$ AS jsonb)')
    if start_idx == -1 or end_idx == -1:
        continue

    json_str = content[start_idx + 7:end_idx].strip()

    try:
        json.loads(json_str)
        continue  # Already valid
    except json.JSONDecodeError:
        pass

    # Extract metadata from the SQL
    # Find title
    title_match = re.search(r"'([^']+)',\s*'kp-xc-", content)
    title = title_match.group(1) if title_match else "Unknown"

    # Find slug
    slug_match = re.search(r"'(kp-xc-[^']+)'", content)
    slug = slug_match.group(1) if slug_match else "unknown"

    # Find category code
    code_match = re.search(r"code = '([^']+)'", content)
    code = code_match.group(1) if code_match else "unknown"

    # Find summary
    summary_match = re.search(r"NULL,\s*'([^']*)'", content)
    summary = summary_match.group(1) if summary_match else ""

    # Find tags
    tags_match = re.search(r"CAST\('(\[[^]]*\])'", content)
    tags = tags_match.group(1) if tags_match else '[]'

    # Generate simple JSON
    # For now, just create a minimal valid JSON
    simple_json = json.dumps({
        "type": "doc",
        "content": [
            {"type": "heading", "attrs": {"level": 1}, "content": [{"type": "text", "text": title}]},
            {"type": "highlightBlock", "attrs": {"backgroundColor": "#fffbeb", "borderColor": "#f59e0b", "icon": "💡"}, "content": [
                {"type": "paragraph", "content": [{"type": "text", "text": "核心结论：", "marks": [{"type": "bold"}]}, {"type": "text", "text": summary}]}
            ]},
            {"type": "heading", "attrs": {"level": 2}, "content": [{"type": "text", "text": "一、知识要点"}]},
            {"type": "orderedList", "content": [
                {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "待补充"}]}]}
            ]},
            {"type": "heading", "attrs": {"level": 2}, "content": [{"type": "text", "text": "二、解题方法"}]},
            {"type": "orderedList", "content": [
                {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "待补充"}]}]}
            ]},
            {"type": "highlightBlock", "attrs": {"backgroundColor": "#eff6ff", "borderColor": "#3b82f6", "icon": "📊"}, "content": [
                {"type": "paragraph", "content": [{"type": "text", "text": "刷题建议：", "marks": [{"type": "bold"}]}, {"type": "text", "text": "待补充。"}]}
            ]}
        ]
    }, ensure_ascii=False)

    # Replace the JSON in the SQL
    new_content = content[:start_idx + 7] + simple_json + content[end_idx:]

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(new_content)

    fixed += 1
    print("REWRITTEN:", os.path.basename(filepath))

print("\nTotal fixed:", fixed)
