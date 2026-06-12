#!/usr/bin/env python3
"""Fill real content for 资料分析 L4 + L3 overviews"""
import json, os

sql_dir = "D:/100_Work/101_Program/Proj/fba/backend/app/content/sql"

nodes = [
    # ========== 资料分析 L4 ==========
    ("kp_xingce_data_analysis_statistical_terms", "data-analysis-statistical-terms", "统计术语", 4,
     "统计术语是资料分析的基础，掌握同比、环比、百分数、百分点等概念是解题前提。",
     ["同比：与上年同期相比，如2024年3月 vs 2023年3月",
      "环比：与相邻上期相比，如2024年3月 vs 2024年2月",
      "百分数：表示比率，如增长20%",
      "百分点：百分数的差值，如从5%增长到8%，增长了3个百分点",
      "基期与现期：基期是对比的基准，现期是当前时期"],
     ["熟记各术语的定义和区别",
      "同比和环比的区别：同比看年份，环比看相邻期",
      "百分数和百分点的区别：百分数是比率，百分点是差值",
      "基期和现期的判断：题目问的时期是现期，对比的是基期"],
     ["同比和环比搞混",
      "百分数和百分点搞混",
      "基期和现期搞反"],
     "统计术语是资料分析的基础。同比看年份，环比看相邻期，百分数是比率，百分点是差值。"),

    ("kp_xingce_data_analysis_basic_calculation", "data-analysis-basic-calculation", "简单计算", 4,
     "简单计算是资料分析的速算技巧，截位直除、百化分、分数比较是最核心的方法。",
     ["截位直除：将数据截取前几位有效数字后直接相除",
      "百化分：将百分数化为分数简化计算，如25%=1/4, 12.5%=1/8",
      "分数比较：分子大分母小的分数更大",
      "增长率比较：用现期/基期-1 或 直接比较增长量/基期"],
     ["截位直除：保留2-3位有效数字",
      "百化分：熟记常见百分数对应的分数",
      "分数比较：交叉相乘法或直除法",
      "选项差距大时用估算，差距小时精算"],
     ["截位时有效数字保留太多导致计算复杂",
      "百化分时分数记错",
      "分数比较方向搞反"],
     '简单计算的核心是"能估就不精算"。截位直除是最常用的速算方法。'),

    ("kp_xingce_data_analysis_current_and_base", "data-analysis-current-and-base", "现期与基期", 4,
     "现期与基期是资料分析的核心概念，基期=现期/(1+r)，现期=基期*(1+r)。",
     ["现期 = 基期 * (1 + 增长率r)",
      "基期 = 现期 / (1 + 增长率r)",
      "增长量 = 现期 - 基期 = 基期 * r",
      "增长率 r = 增长量 / 基期 = (现期 - 基期) / 基期"],
     ["确定哪个是现期哪个是基期",
      "已知现期和增长率求基期：基期 = 现期/(1+r)",
      "已知基期和增长率求现期：现期 = 基期*(1+r)",
      "增长率较小时可用近似：基期 ≈ 现期*(1-r)"],
     ["现期和基期搞反",
      "增长率的正负搞错",
      "近似公式用错条件"],
     "现期与基期是资料分析的核心公式。基期=现期/(1+r)必须熟练。"),

    ("kp_xingce_data_analysis_comparison_sorting", "data-analysis-comparison-sorting", "比较排序", 4,
     "比较排序是资料分析的常考题型，需要比较增长率、比重、平均数等的大小。",
     ["增长率比较：用增长量/基期 或 现期/基期-1",
      "比重比较：部分/整体 的大小",
      "平均数比较：总量/份数 的大小",
      "排序方法：先估算再精算，选项差距大时估算"],
     ["先看选项差距，差距大用估算",
      "增长率比较用截位直除",
      "比重和平均数用公式计算",
      "排序时注意是从大到小还是从小到大"],
     ["排序方向搞反",
      "估算误差导致排序错误",
      "比较对象搞混"],
     '比较排序的关键是"先估后排"。选项差距大时用估算，差距小时精算。'),

    ("kp_xingce_data_analysis_comprehensive_analysis", "data-analysis-comprehensive-analysis", "综合分析", 4,
     "综合分析是资料分析的综合题型，通常给出多个说法要求判断对错，需要逐项验证。",
     ["逐项验证法：将每个说法分别验证",
      "排除法：找到一个错误的就排除",
      "优先验证容易的：先验证计算简单的说法",
      "选项判定：哪个说法正确/错误"],
     ["先看问题问的是哪个说法",
      "逐项验证，找到错误就排除",
      "优先验证容易计算的说法",
      '注意"以下说法正确/错误的是"'],
     ["逐项验证时遗漏某个说法",
      "计算错误导致判断错误",
      "问题理解错误"],
     '综合分析的关键是"逐项验证排除"。先验证容易的，找到错误就排除。'),

    # ========== L3 概述 ==========
    ("kp_xingce_common_sense", "xingce-common-sense", "常识判断", 3,
     "常识判断是行测五大模块之一，考查政治、经济、法律、科技、人文、地理等基础知识。",
     ["政治常识：马克思主义、毛泽东思想、中国特色社会主义理论",
      "法律常识：宪法、民法、刑法、行政法等基础法律知识",
      "经济常识：微观经济、宏观经济、国际经济基础概念",
      "科技常识：物理、化学、生物、信息技术等基础科学知识",
      "人文历史：中国历史、世界历史、文学艺术、传统文化"],
     ["排除法：排除明显错误的选项",
      "联想法：将知识点与已知信息关联",
      "推理法：根据逻辑关系推断答案",
      "积累法：日常积累是提高常识的根本"],
     ["常识靠积累，短期突击效果有限",
      "不要在常识题上花太多时间",
      "不确定时选第一直觉"],
     "常识判断范围广、难度大，建议日常多积累。考试时控制时间，不要纠结。"),

    ("kp_xingce_language", "xingce-language", "言语理解与表达", 3,
     "言语理解与表达是行测的核心模块，包括逻辑填空、片段阅读、语句表达三种题型。",
     ["逻辑填空：实词辨析、成语辨析、虚词辨析、综合辨析",
      "片段阅读：主旨概括、意图判断、细节理解、标题选择",
      "语句表达：语句排序、语句填空、下文推断",
      "阅读量大：平均每题阅读量约200字"],
     ["逻辑填空：找语境提示信息，不要凭语感",
      "主旨概括：找主题句（首尾句、转折后）",
      "意图判断：在主旨基础上推断作者意图",
      "语句排序：找首句、抓关联、验顺序"],
     ["逻辑填空凭语感不找提示信息",
      "主旨概括选了细节而非主旨",
      "意图判断过度推断"],
     "言语理解是行测分值最高的模块。逻辑填空靠积累，片段阅读靠技巧，语句表达靠逻辑。"),

    ("kp_xingce_logic", "xingce-logic", "判断推理", 3,
     "判断推理是行测的核心模块，包括图形推理、定义判断、类比推理、逻辑判断四种题型。",
     ["图形推理：规律推理、空间推理、属性推理、数量推理",
      "定义判断：单定义、多定义、匹配定义",
      "类比推理：逻辑关系、言语关系、经验常识",
      "逻辑判断：翻译推理、真假推理、分析推理、加强削弱"],
     ["图形推理：看元素组成找规律（相同看位置，相似看样式，不同看数量）",
      "定义判断：抓关键词逐一匹配",
      "类比推理：先横看关系再纵看对应",
      "逻辑判断：翻译推理用公式，加强削弱找论点论据"],
     ["图形推理规律想不到",
      "定义判断关键词抓不准",
      "逻辑判断论点论据搞混"],
     "判断推理是行测的提分重点。图形推理靠观察，定义判断靠细心，类比推理靠积累，逻辑判断靠方法。"),
]

def make_l4_json(title, conclusion, knowledge, methods, mistakes, practice):
    content = [
        {"type": "heading", "attrs": {"level": 1}, "content": [{"type": "text", "text": title}]},
        {"type": "highlightBlock", "attrs": {"backgroundColor": "#fffbeb", "borderColor": "#f59e0b", "icon": "💡"}, "content": [
            {"type": "paragraph", "content": [
                {"type": "text", "text": "核心结论：", "marks": [{"type": "bold"}]},
                {"type": "text", "text": conclusion}
            ]}
        ]},
        {"type": "heading", "attrs": {"level": 2}, "content": [{"type": "text", "text": "一、知识要点"}]},
        {"type": "orderedList", "content": [
            {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": p}]}]}
            for p in knowledge
        ]},
        {"type": "heading", "attrs": {"level": 2}, "content": [{"type": "text", "text": "二、解题方法"}]},
        {"type": "orderedList", "content": [
            {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": m}]}]}
            for m in methods
        ]},
        {"type": "heading", "attrs": {"level": 2}, "content": [{"type": "text", "text": "三、易错点"}]},
        {"type": "bulletList", "content": [
            {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": e}]}]}
            for e in mistakes
        ]},
        {"type": "highlightBlock", "attrs": {"backgroundColor": "#eff6ff", "borderColor": "#3b82f6", "icon": "📊"}, "content": [
            {"type": "paragraph", "content": [
                {"type": "text", "text": "刷题建议：", "marks": [{"type": "bold"}]},
                {"type": "text", "text": practice}
            ]}
        ]}
    ]
    return json.dumps({"type": "doc", "content": content}, ensure_ascii=False)

def make_l3_json(title, conclusion, knowledge, methods, mistakes, practice):
    content = [
        {"type": "heading", "attrs": {"level": 1}, "content": [{"type": "text", "text": title}]},
        {"type": "highlightBlock", "attrs": {"backgroundColor": "#fffbeb", "borderColor": "#f59e0b", "icon": "💡"}, "content": [
            {"type": "paragraph", "content": [
                {"type": "text", "text": "核心结论：", "marks": [{"type": "bold"}]},
                {"type": "text", "text": conclusion}
            ]}
        ]},
        {"type": "heading", "attrs": {"level": 2}, "content": [{"type": "text", "text": "一、包含的子模块"}]},
        {"type": "orderedList", "content": [
            {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": p}]}]}
            for p in knowledge
        ]},
        {"type": "heading", "attrs": {"level": 2}, "content": [{"type": "text", "text": "二、核心解题方法"}]},
        {"type": "orderedList", "content": [
            {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": m}]}]}
            for m in methods
        ]},
        {"type": "heading", "attrs": {"level": 2}, "content": [{"type": "text", "text": "三、备考建议"}]},
        {"type": "bulletList", "content": [
            {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": e}]}]}
            for e in mistakes
        ]},
        {"type": "highlightBlock", "attrs": {"backgroundColor": "#eff6ff", "borderColor": "#3b82f6", "icon": "📊"}, "content": [
            {"type": "paragraph", "content": [
                {"type": "text", "text": "刷题建议：", "marks": [{"type": "bold"}]},
                {"type": "text", "text": practice}
            ]}
        ]}
    ]
    return json.dumps({"type": "doc", "content": content}, ensure_ascii=False)

generated = 0
for code, slug_suffix, title, level, conclusion, knowledge, methods, mistakes, practice in nodes:
    slug = f"kp-xc-{slug_suffix}"
    if level == 4:
        summary = f"资料分析-{title}的核心知识点和解题方法。"
        tags = json.dumps(["资料分析", title], ensure_ascii=False)
        json_content = make_l4_json(title, conclusion, knowledge, methods, mistakes, practice)
    else:
        summary = f"行测-{title}模块概述。"
        tags = json.dumps([title], ensure_ascii=False)
        json_content = make_l3_json(title, conclusion, knowledge, methods, mistakes, practice)

    sql = f"""WITH category_node AS (
    SELECT id FROM sys_category WHERE app_code = 'youanshang' AND type = 'knowledge_point' AND code = '{code}'
)
INSERT INTO sys_content (app_code, title, slug, content_json, content_html, summary, category_id, tags, is_pinned, is_public, is_published, publish_time, view_count, sort_order, extra, created_by, created_time)
SELECT 'gongkao', '{title}', '{slug}', CAST($${json_content}$$ AS jsonb), NULL, '{summary}', category_node.id, CAST('{tags}' AS jsonb), FALSE, TRUE, TRUE, NOW(), 0, 0, CAST('{{"content_type": "knowledge_point", "category_code": "{code}", "source": "fba_content_engine"}}' AS jsonb), 1, NOW()
FROM category_node ON CONFLICT (slug) DO UPDATE SET title = EXCLUDED.title, content_json = EXCLUDED.content_json, summary = EXCLUDED.summary, category_id = EXCLUDED.category_id, tags = EXCLUDED.tags, extra = EXCLUDED.extra, updated_time = NOW();
"""
    filename = f"kp_xc_{code.replace('kp_xingce_', '').replace('kp_xc_', '')}.sql"
    filepath = os.path.join(sql_dir, filename)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(sql)
    generated += 1
    print(f"[{generated}] L{level} {title}")

print(f"\nDone: {generated} files")
