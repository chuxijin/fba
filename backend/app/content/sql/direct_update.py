#!/usr/bin/env python3
"""Directly update remaining records with real content"""
import json

# The 9 remaining records and their new content
updates = [
    (1622, "数量关系总览", "kp-xc-quantity-overview",
     {"type": "doc", "content": [
         {"type": "heading", "attrs": {"level": 1}, "content": [{"type": "text", "text": "数量关系总览"}]},
         {"type": "highlightBlock", "attrs": {"backgroundColor": "#fffbeb", "borderColor": "#f59e0b", "icon": "💡"}, "content": [
             {"type": "paragraph", "content": [
                 {"type": "text", "text": "核心结论：", "marks": [{"type": "bold"}]},
                 {"type": "text", "text": "数量关系是行测的难点模块，包括数学运算和数字推理两种题型，考查数学思维和计算能力。"}
             ]}
         ]},
         {"type": "heading", "attrs": {"level": 2}, "content": [{"type": "text", "text": "一、包含的子模块"}]},
         {"type": "orderedList", "content": [
             {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "数学运算模块：工程问题、行程问题、排列组合、概率、经济利润等"}]}]},
             {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "数字推理模块：等差数列、等比数列、幂次数列、递推数列等"}]}]},
             {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "题型分布：数学运算约10-15题，数字推理约5题"}]}]},
             {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "难度分布：简单题约占30%，中等题约占50%，难题约占20%"}]}]}
         ]},
         {"type": "heading", "attrs": {"level": 2}, "content": [{"type": "text", "text": "二、核心解题方法"}]},
         {"type": "orderedList", "content": [
             {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "先做简单题：工程、行程、排列组合等有固定公式的题型"}]}]},
             {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "代入排除法：将选项代入验证，适合大部分题型"}]}]},
             {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "特殊值法：设特殊值简化计算"}]}]},
             {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "放弃策略：难题果断放弃，把时间留给其他模块"}]}]}
         ]},
         {"type": "heading", "attrs": {"level": 2}, "content": [{"type": "text", "text": "三、备考建议"}]},
         {"type": "bulletList", "content": [
             {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "数量关系是行测最难的模块，不要追求全对"}]}]},
             {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "重点掌握高频题型（工程、行程、排列组合）"}]}]},
             {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "考试时先做数量关系中简单的题，难题放最后"}]}]}
         ]},
         {"type": "highlightBlock", "attrs": {"backgroundColor": "#eff6ff", "borderColor": "#3b82f6", "icon": "📊"}, "content": [
             {"type": "paragraph", "content": [
                 {"type": "text", "text": "刷题建议：", "marks": [{"type": "bold"}]},
                 {"type": "text", "text": "数量关系不需要全对，抓住高频题型即可。建议重点练习工程、行程、排列组合。"}
             ]}
         ]}
     ]}),
    (1602, "片段阅读概述", "kp-xc-lang-reading-overview",
     {"type": "doc", "content": [
         {"type": "heading", "attrs": {"level": 1}, "content": [{"type": "text", "text": "片段阅读概述"}]},
         {"type": "highlightBlock", "attrs": {"backgroundColor": "#fffbeb", "borderColor": "#f59e0b", "icon": "💡"}, "content": [
             {"type": "paragraph", "content": [
                 {"type": "text", "text": "核心结论：", "marks": [{"type": "bold"}]},
                 {"type": "text", "text": "片段阅读是言语理解的核心题型，给出一段文字要求回答相关问题，考查阅读理解能力。"}
             ]}
         ]},
         {"type": "heading", "attrs": {"level": 2}, "content": [{"type": "text", "text": "一、知识要点"}]},
         {"type": "orderedList", "content": [
             {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "主旨概括题：概括文段的中心思想"}]}]},
             {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "意图判断题：推断作者的写作意图"}]}]},
             {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "细节理解题：判断选项与原文是否一致"}]}]},
             {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "态度观点题：判断作者的态度和观点"}]}]},
             {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "标题选择题：为文段选择最合适的标题"}]}]},
             {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "词句理解题：理解文中特定词语或句子的含义"}]}]}
         ]},
         {"type": "heading", "attrs": {"level": 2}, "content": [{"type": "text", "text": "二、解题方法"}]},
         {"type": "orderedList", "content": [
             {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "找主题句：首尾句、转折后、总结句"}]}]},
             {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "关联词定位：转折、因果、递进、并列"}]}]},
             {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "排除干扰项：偷换概念、以偏概全、无中生有"}]}]},
             {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "先看问题再读文段：带着问题找答案"}]}]}
         ]},
         {"type": "heading", "attrs": {"level": 2}, "content": [{"type": "text", "text": "三、易错点"}]},
         {"type": "bulletList", "content": [
             {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "不要逐字逐句读，要快速定位关键信息"}]}]},
             {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "干扰项的识别是提高正确率的关键"}]}]},
             {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "主旨概括选了细节而非主旨"}]}]}
         ]},
         {"type": "highlightBlock", "attrs": {"backgroundColor": "#eff6ff", "borderColor": "#3b82f6", "icon": "📊"}, "content": [
             {"type": "paragraph", "content": [
                 {"type": "text", "text": "刷题建议：", "marks": [{"type": "bold"}]},
                 {"type": "text", "text": "片段阅读是言语理解的主体。掌握找主题句和排除干扰项两大技巧，正确率可以稳定在75%以上。"}
             ]}
         ]}
     ]}),
    (1596, "篇章阅读概述", "kp-xc-lang-passage-overview",
     {"type": "doc", "content": [
         {"type": "heading", "attrs": {"level": 1}, "content": [{"type": "text", "text": "篇章阅读概述"}]},
         {"type": "highlightBlock", "attrs": {"backgroundColor": "#fffbeb", "borderColor": "#f59e0b", "icon": "💡"}, "content": [
             {"type": "paragraph", "content": [
                 {"type": "text", "text": "核心结论：", "marks": [{"type": "bold"}]},
                 {"type": "text", "text": "篇章阅读是言语理解的进阶题型，给出一篇长文（约1000字）要求回答多个问题。"}
             ]}
         ]},
         {"type": "heading", "attrs": {"level": 2}, "content": [{"type": "text", "text": "一、知识要点"}]},
         {"type": "orderedList", "content": [
             {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "题型多样：主旨概括、细节理解、词句理解、语句填空等综合出现"}]}]},
             {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "阅读量大：约1000字的长文，需要快速定位信息"}]}]},
             {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "问题关联：多个问题可能涉及同一段落"}]}]},
             {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "时间压力：每篇约5道题，需要在5分钟内完成"}]}]}
         ]},
         {"type": "heading", "attrs": {"level": 2}, "content": [{"type": "text", "text": "二、解题方法"}]},
         {"type": "orderedList", "content": [
             {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "先看问题再读文章：带着问题定位关键段落"}]}]},
             {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "标注关键信息：用笔标记重要句子和关键词"}]}]},
             {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "跳读和扫读：不重要的段落快速跳过"}]}]},
             {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "分段处理：每段对应1-2个问题"}]}]}
         ]},
         {"type": "heading", "attrs": {"level": 2}, "content": [{"type": "text", "text": "三、易错点"}]},
         {"type": "bulletList", "content": [
             {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "不要逐字逐句读全文"}]}]},
             {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "时间分配：读文章2分钟，答题3分钟"}]}]},
             {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "先看问题再读文章是关键"}]}]}
         ]},
         {"type": "highlightBlock", "attrs": {"backgroundColor": "#eff6ff", "borderColor": "#3b82f6", "icon": "📊"}, "content": [
             {"type": "paragraph", "content": [
                 {"type": "text", "text": "刷题建议：", "marks": [{"type": "bold"}]},
                 {"type": "text", "text": "篇章阅读是言语理解中最耗时的题型。掌握跳读和定位技巧是关键。"}
             ]}
         ]}
     ]}),
    (1607, "语句表达概述", "kp-xc-lang-sentence-overview",
     {"type": "doc", "content": [
         {"type": "heading", "attrs": {"level": 1}, "content": [{"type": "text", "text": "语句表达概述"}]},
         {"type": "highlightBlock", "attrs": {"backgroundColor": "#fffbeb", "borderColor": "#f59e0b", "icon": "💡"}, "content": [
             {"type": "paragraph", "content": [
                 {"type": "text", "text": "核心结论：", "marks": [{"type": "bold"}]},
                 {"type": "text", "text": "语句表达是言语理解的第三种题型，考查语言组织和表达能力，包括排序、填空、推断。"}
             ]}
         ]},
         {"type": "heading", "attrs": {"level": 2}, "content": [{"type": "text", "text": "一、知识要点"}]},
         {"type": "orderedList", "content": [
             {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "语句排序题：将打乱的句子重新排列成通顺的段落"}]}]},
             {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "语句填空题：在文段中填入最合适的句子"}]}]},
             {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "下文推断题：推断文段接下来最可能说什么"}]}]}
         ]},
         {"type": "heading", "attrs": {"level": 2}, "content": [{"type": "text", "text": "二、解题方法"}]},
         {"type": "orderedList", "content": [
             {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "语句排序：找首句、抓关联、验顺序"}]}]},
             {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "语句填空：看上下文衔接，找逻辑关系"}]}]},
             {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "下文推断：看尾句，推断下文话题"}]}]},
             {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "关联词和指代词是重要的解题线索"}]}]}
         ]},
         {"type": "heading", "attrs": {"level": 2}, "content": [{"type": "text", "text": "三、易错点"}]},
         {"type": "bulletList", "content": [
             {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "排序题先确定首句再找关联"}]}]},
             {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "填空题看上下文的衔接"}]}]},
             {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "推断题看尾句"}]}]}
         ]},
         {"type": "highlightBlock", "attrs": {"backgroundColor": "#eff6ff", "borderColor": "#3b82f6", "icon": "📊"}, "content": [
             {"type": "paragraph", "content": [
                 {"type": "text", "text": "刷题建议：", "marks": [{"type": "bold"}]},
                 {"type": "text", "text": "语句表达约占言语理解的15%。排序题找首句，填空题看衔接，推断题看尾句。"}
             ]}
         ]}
     ]}),
    (1618, "逻辑推理总览", "kp-xc-logic-overview",
     {"type": "doc", "content": [
         {"type": "heading", "attrs": {"level": 1}, "content": [{"type": "text", "text": "逻辑推理总览"}]},
         {"type": "highlightBlock", "attrs": {"backgroundColor": "#fffbeb", "borderColor": "#f59e0b", "icon": "💡"}, "content": [
             {"type": "paragraph", "content": [
                 {"type": "text", "text": "核心结论：", "marks": [{"type": "bold"}]},
                 {"type": "text", "text": "逻辑推理是判断推理的核心题型，包括形式逻辑和论证推理两大类。"}
             ]}
         ]},
         {"type": "heading", "attrs": {"level": 2}, "content": [{"type": "text", "text": "一、知识要点"}]},
         {"type": "orderedList", "content": [
             {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "形式逻辑：翻译推理、真假推理、分析推理、集合推理"}]}]},
             {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "论证推理：加强削弱、日常推理、平行结构"}]}]},
             {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "题量：通常8-10题"}]}]},
             {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "难度：形式逻辑需要公式，论证推理需要理解论点论据"}]}]}
         ]},
         {"type": "heading", "attrs": {"level": 2}, "content": [{"type": "text", "text": "二、解题方法"}]},
         {"type": "orderedList", "content": [
             {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "形式逻辑：用公式和符号化方法"}]}]},
             {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "论证推理：找论点和论据，分析论证结构"}]}]},
             {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "加强削弱：判断选项对论点的支持或削弱程度"}]}]},
             {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "日常推理：用排除法和代入法"}]}]}
         ]},
         {"type": "heading", "attrs": {"level": 2}, "content": [{"type": "text", "text": "三、易错点"}]},
         {"type": "bulletList", "content": [
             {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "逻辑推理需要系统学习逻辑知识"}]}]},
             {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "形式逻辑靠公式，论证推理靠理解"}]}]},
             {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "加强削弱题是高频考点"}]}]}
         ]},
         {"type": "highlightBlock", "attrs": {"backgroundColor": "#eff6ff", "borderColor": "#3b82f6", "icon": "📊"}, "content": [
             {"type": "paragraph", "content": [
                 {"type": "text", "text": "刷题建议：", "marks": [{"type": "bold"}]},
                 {"type": "text", "text": "逻辑推理是判断推理中难度最高的题型。形式逻辑靠公式，论证推理靠理解论点论据。"}
             ]}
         ]}
     ]}),
    (1614, "形式逻辑概述", "kp-xc-logic-formal-overview",
     {"type": "doc", "content": [
         {"type": "heading", "attrs": {"level": 1}, "content": [{"type": "text", "text": "形式逻辑概述"}]},
         {"type": "highlightBlock", "attrs": {"backgroundColor": "#fffbeb", "borderColor": "#f59e0b", "icon": "💡"}, "content": [
             {"type": "paragraph", "content": [
                 {"type": "text", "text": "核心结论：", "marks": [{"type": "bold"}]},
                 {"type": "text", "text": "形式逻辑是逻辑推理的基础，用符号和公式来分析逻辑关系。"}
             ]}
         ]},
         {"type": "heading", "attrs": {"level": 2}, "content": [{"type": "text", "text": "一、知识要点"}]},
         {"type": "orderedList", "content": [
             {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "命题逻辑：如果P则Q、P或Q、P且Q、非P"}]}]},
             {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "推理规则：肯前肯后、否后否前、逆否等价"}]}]},
             {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "三段论：大前提、小前提、结论"}]}]},
             {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "集合推理：所有、有些、某个的推理关系"}]}]}
         ]},
         {"type": "heading", "attrs": {"level": 2}, "content": [{"type": "text", "text": "二、解题方法"}]},
         {"type": "orderedList", "content": [
             {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "符号化：将文字转化为逻辑符号"}]}]},
             {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "用公式：肯前肯后、否后否前"}]}]},
             {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "画图法：用韦恩图分析集合关系"}]}]},
             {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "排除法：用逻辑规则排除错误选项"}]}]}
         ]},
         {"type": "heading", "attrs": {"level": 2}, "content": [{"type": "text", "text": "三、易错点"}]},
         {"type": "bulletList", "content": [
             {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "不要凭直觉判断，要用逻辑规则"}]}]},
             {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "肯前肯后和否后否前是最基本的推理规则"}]}]},
             {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "不要混淆充分条件和必要条件"}]}]}
         ]},
         {"type": "highlightBlock", "attrs": {"backgroundColor": "#eff6ff", "borderColor": "#3b82f6", "icon": "📊"}, "content": [
             {"type": "paragraph", "content": [
                 {"type": "text", "text": "刷题建议：", "marks": [{"type": "bold"}]},
                 {"type": "text", "text": "形式逻辑需要系统学习逻辑规则。符号化和公式法是解题的核心工具。"}
             ]}
         ]}
     ]}),
    (1587, "综合辨析", "kp-xc-lang-cloze-comprehensive",
     {"type": "doc", "content": [
         {"type": "heading", "attrs": {"level": 1}, "content": [{"type": "text", "text": "综合辨析"}]},
         {"type": "highlightBlock", "attrs": {"backgroundColor": "#fffbeb", "borderColor": "#f59e0b", "icon": "💡"}, "content": [
             {"type": "paragraph", "content": [
                 {"type": "text", "text": "核心结论：", "marks": [{"type": "bold"}]},
                 {"type": "text", "text": "综合辨析是逻辑填空的进阶题型，通常涉及多个空和多种词语类型的混合。"}
             ]}
         ]},
         {"type": "heading", "attrs": {"level": 2}, "content": [{"type": "text", "text": "一、知识要点"}]},
         {"type": "orderedList", "content": [
             {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "多空题：2-3个空，每个空可能是实词、成语或虚词"}]}]},
             {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "混合题型：实词+成语、实词+虚词、成语+虚词等"}]}]},
             {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "难度较高：需要综合运用多种辨析方法"}]}]},
             {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "题量增加：近年来综合辨析题量逐渐增多"}]}]}
         ]},
         {"type": "heading", "attrs": {"level": 2}, "content": [{"type": "text", "text": "二、解题方法"}]},
         {"type": "orderedList", "content": [
             {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "先做最有把握的空：用排除法缩小范围"}]}]},
             {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "逐一验证：每个空都要验证"}]}]},
             {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "综合运用：实词用六角度，成语看含义，虚词看逻辑"}]}]},
             {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "语感辅助：最后用语感验证整体通顺度"}]}]}
         ]},
         {"type": "heading", "attrs": {"level": 2}, "content": [{"type": "text", "text": "三、易错点"}]},
         {"type": "bulletList", "content": [
             {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "不要在一个空上纠结太久"}]}]},
             {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "多空题用排除法效率最高"}]}]},
             {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "先做有把握的空是关键"}]}]}
         ]},
         {"type": "highlightBlock", "attrs": {"backgroundColor": "#eff6ff", "borderColor": "#3b82f6", "icon": "📊"}, "content": [
             {"type": "paragraph", "content": [
                 {"type": "text", "text": "刷题建议：", "marks": [{"type": "bold"}]},
                 {"type": "text", "text": "综合辨析是逻辑填空中难度最高的题型。先做有把握的空，用排除法缩小范围。"}
             ]}
         ]}
     ]}),
    (1588, "虚词辨析", "kp-xc-lang-cloze-function-word",
     {"type": "doc", "content": [
         {"type": "heading", "attrs": {"level": 1}, "content": [{"type": "text", "text": "虚词辨析"}]},
         {"type": "highlightBlock", "attrs": {"backgroundColor": "#fffbeb", "borderColor": "#f59e0b", "icon": "💡"}, "content": [
             {"type": "paragraph", "content": [
                 {"type": "text", "text": "核心结论：", "marks": [{"type": "bold"}]},
                 {"type": "text", "text": "虚词辨析考查关联词语的运用能力，需要掌握七种逻辑关系。"}
             ]}
         ]},
         {"type": "heading", "attrs": {"level": 2}, "content": [{"type": "text", "text": "一、知识要点"}]},
         {"type": "orderedList", "content": [
             {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "转折关系：虽然...但是...、尽管...却..."}]}]},
             {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "因果关系：因为...所以...、由于...因此..."}]}]},
             {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "递进关系：不仅...而且...、尚且...何况..."}]}]},
             {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "条件关系：只要...就...、只有...才..."}]}]},
             {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "假设关系：如果...那么...、即使...也..."}]}]},
             {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "并列关系：既...又...、一边...一边..."}]}]}
         ]},
         {"type": "heading", "attrs": {"level": 2}, "content": [{"type": "text", "text": "二、解题方法"}]},
         {"type": "orderedList", "content": [
             {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "判断逻辑关系：看前后句的逻辑关系"}]}]},
             {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "关联词搭配：熟记关联词的固定搭配"}]}]},
             {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "语境验证：代入语境看是否通顺"}]}]},
             {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "排除法：先排除明显错误的搭配"}]}]}
         ]},
         {"type": "heading", "attrs": {"level": 2}, "content": [{"type": "text", "text": "三、易错点"}]},
         {"type": "bulletList", "content": [
             {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "关联词的固定搭配必须熟记"}]}]},
             {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "不要混淆相似的关联词"}]}]},
             {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "判断逻辑关系是关键"}]}]}
         ]},
         {"type": "highlightBlock", "attrs": {"backgroundColor": "#eff6ff", "borderColor": "#3b82f6", "icon": "📊"}, "content": [
             {"type": "paragraph", "content": [
                 {"type": "text", "text": "刷题建议：", "marks": [{"type": "bold"}]},
                 {"type": "text", "text": "虚词辨析相对简单，掌握七种逻辑关系和关联词搭配即可。"}
             ]}
         ]}
     ]}),
    (1611, "论证推理概述", "kp-xc-logic-arg-overview",
     {"type": "doc", "content": [
         {"type": "heading", "attrs": {"level": 1}, "content": [{"type": "text", "text": "论证推理概述"}]},
         {"type": "highlightBlock", "attrs": {"backgroundColor": "#fffbeb", "borderColor": "#f59e0b", "icon": "💡"}, "content": [
             {"type": "paragraph", "content": [
                 {"type": "text", "text": "核心结论：", "marks": [{"type": "bold"}]},
                 {"type": "text", "text": "论证推理是逻辑判断的核心题型，考查对论证结构的分析和评价能力。"}
             ]}
         ]},
         {"type": "heading", "attrs": {"level": 2}, "content": [{"type": "text", "text": "一、知识要点"}]},
         {"type": "orderedList", "content": [
             {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "论证结构：论点、论据、论证方式"}]}]},
             {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "加强削弱：支持或反驳论证"}]}]},
             {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "前提假设：论证成立的必要条件"}]}]},
             {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "评价论证：分析论证的有效性"}]}]}
         ]},
         {"type": "heading", "attrs": {"level": 2}, "content": [{"type": "text", "text": "二、解题方法"}]},
         {"type": "orderedList", "content": [
             {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "找论点：通常在首句或尾句"}]}]},
             {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "找论据：支持论点的证据"}]}]},
             {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "分析论证方式：归纳、演绎、类比"}]}]},
             {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "加强削弱：支持或反驳论点/论据/论证方式"}]}]}
         ]},
         {"type": "heading", "attrs": {"level": 2}, "content": [{"type": "text", "text": "三、易错点"}]},
         {"type": "bulletList", "content": [
             {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "加强削弱题是高频考点"}]}]},
             {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "前提假设题用否定代入法"}]}]},
             {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "找论点论据是解题的基础"}]}]}
         ]},
         {"type": "highlightBlock", "attrs": {"backgroundColor": "#eff6ff", "borderColor": "#3b82f6", "icon": "📊"}, "content": [
             {"type": "paragraph", "content": [
                 {"type": "text", "text": "刷题建议：", "marks": [{"type": "bold"}]},
                 {"type": "text", "text": "论证推理是逻辑判断的主体。找论点论据、分析论证结构是解题的基础。"}
             ]}
         ]}
     ]}),
]

# Generate SQL for each update
for record_id, title, slug, content_json in updates:
    json_str = json.dumps(content_json, ensure_ascii=False)
    sql = f"""UPDATE sys_content
SET content_json = CAST($${json_str}$$ AS jsonb), updated_time = NOW()
WHERE id = {record_id};"""
    print(f"-- {title} (id={record_id})")
    print(sql)
    print()
