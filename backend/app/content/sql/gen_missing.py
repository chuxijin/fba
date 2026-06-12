#!/usr/bin/env python3
"""Generate SQL seed files for all missing content nodes"""
import json, os

sql_dir = "D:/100_Work/101_Program/Proj/fba/backend/app/content/sql"

# Node data: (id, code, name, level, parent_name, summary, tags)
nodes = [
    # L3
    (337, "kp_xingce_common_sense", "常识判断", 3, "行测", "行测一级知识点：常识判断", '["常识判断"]'),
    (338, "kp_xingce_language", "言语理解与表达", 3, "行测", "行测一级知识点：言语理解与表达", '["言语理解"]'),
    (340, "kp_xingce_logic", "判断推理", 3, "行测", "行测一级知识点：判断推理", '["判断推理"]'),
    # L4 - 资料分析
    (381, "kp_xingce_data_analysis_statistical_terms", "统计术语", 4, "资料分析", "资料分析-统计术语：同比、环比、百分数、百分点等基础概念。", '["资料分析", "统计术语"]'),
    (382, "kp_xingce_data_analysis_basic_calculation", "简单计算", 4, "资料分析", "资料分析-简单计算：截位直除、百化分、分数比较等速算技巧。", '["资料分析", "简单计算"]'),
    (383, "kp_xingce_data_analysis_current_and_base", "现期与基期", 4, "资料分析", "资料分析-现期与基期：基期=现期/(1+r)，现期=基期×(1+r)。", '["资料分析", "现期基期"]'),
    (388, "kp_xingce_data_analysis_comparison_sorting", "比较排序", 4, "资料分析", "资料分析-比较排序：增长率、比重、平均数等的大小排序技巧。", '["资料分析", "比较排序"]'),
    (389, "kp_xingce_data_analysis_comprehensive_analysis", "综合分析", 4, "资料分析", "资料分析-综合分析：选项判定、组合计算、复杂比较等综合题型。", '["资料分析", "综合分析"]'),
    # L5 - 数学运算
    (348, "kp_xingce_quantity_math_operation_inclusion_exclusion", "容斥问题", 5, "数学运算", "容斥问题：两集合A∪B=A+B-A∩B，三集合容斥公式。", '["数量关系", "数学运算", "容斥问题"]'),
    (349, "kp_xingce_quantity_math_operation_permutation_combination", "排列组合", 5, "数学运算", "排列组合：分类加法、分步乘法、排列Anm、组合Cnm。", '["数量关系", "数学运算", "排列组合"]'),
    (350, "kp_xingce_quantity_math_operation_grass_eating", "牛吃草问题", 5, "数学运算", "牛吃草问题：原有草量、草生长速度、牛吃草速度的关系。", '["数量关系", "数学运算", "牛吃草"]'),
    (351, "kp_xingce_quantity_math_operation_extreme_value", "最值问题", 5, "数学运算", "最值问题：最不利原则、和定积值、均值不等式。", '["数量关系", "数学运算", "最值问题"]'),
    (352, "kp_xingce_quantity_math_operation_profit", "经济利润问题", 5, "数学运算", "经济利润问题：利润=售价-成本，利润率=利润/成本。", '["数量关系", "数学运算", "经济利润"]'),
    (353, "kp_xingce_quantity_math_operation_ratio_multiple", "比例倍数问题", 5, "数学运算", "比例倍数问题：正反比关系、连比份数、按比例分配。", '["数量关系", "数学运算", "比例倍数"]'),
    (354, "kp_xingce_quantity_math_operation_planning", "统筹规划问题", 5, "数学运算", "统筹规划问题：时间安排、顺序优化、资源分配、最优决策。", '["数量关系", "数学运算", "统筹规划"]'),
    (355, "kp_xingce_quantity_math_operation_geometry", "几何问题", 5, "数学运算", "几何问题：平面图形、立体几何、周长面积体积计算。", '["数量关系", "数学运算", "几何问题"]'),
    (356, "kp_xingce_quantity_math_operation_equation", "方程与不定方程", 5, "数学运算", "方程与不定方程：一元一次、二元一次、不定方程整数解。", '["数量关系", "数学运算", "方程"]'),
    (357, "kp_xingce_quantity_math_operation_probability", "概率问题", 5, "数学运算", "概率问题：古典概型、条件概率、独立重复试验。", '["数量关系", "数学运算", "概率"]'),
    (358, "kp_xingce_quantity_math_operation_calendar", "星期日期问题", 5, "数学运算", "星期日期问题：闰年平年、星期推算、日期计算。", '["数量关系", "数学运算", "星期日期"]'),
    (359, "kp_xingce_quantity_math_operation_remainder_divisibility", "余数与整除", 5, "数学运算", "余数与整除：整除判定、同余思想、奇偶倍数。", '["数量关系", "数学运算", "余数整除"]'),
    # L5 - 数字推理
    (360, "kp_xingce_quantity_number_reasoning_arithmetic", "等差数列", 5, "数字推理", "等差数列：公差d，an=a1+(n-1)d，等差中项。", '["数量关系", "数字推理", "等差数列"]'),
    (361, "kp_xingce_quantity_number_reasoning_geometric", "等比数列", 5, "数字推理", "等比数列：公比q，an=a1×q^(n-1)，等比中项。", '["数量关系", "数字推理", "等比数列"]'),
    (362, "kp_xingce_quantity_number_reasoning_power", "幂次数列", 5, "数字推理", "幂次数列：平方数、立方数、2^n等幂数规律。", '["数量关系", "数字推理", "幂次数列"]'),
    (363, "kp_xingce_quantity_number_reasoning_recurrence", "递推数列", 5, "数字推理", "递推数列：后项由前项通过某种运算得到。", '["数量关系", "数字推理", "递推数列"]'),
    (364, "kp_xingce_quantity_number_reasoning_grouping", "分组数列", 5, "数字推理", "分组数列：奇数项和偶数项分别成规律。", '["数量关系", "数字推理", "分组数列"]'),
    (365, "kp_xingce_quantity_number_reasoning_cross", "交叉数列", 5, "数字推理", "交叉数列：两个数列交叉排列。", '["数量关系", "数字推理", "交叉数列"]'),
    (366, "kp_xingce_quantity_number_reasoning_combination", "组合数列", 5, "数字推理", "组合数列：由多个简单数列组合而成。", '["数量关系", "数字推理", "组合数列"]'),
    (367, "kp_xingce_quantity_number_reasoning_multi_level", "多级数列", 5, "数字推理", "多级数列：通过多次做差/做比得到规律。", '["数量关系", "数字推理", "多级数列"]'),
    (368, "kp_xingce_quantity_number_reasoning_fraction", "分数数列", 5, "数字推理", "分数数列：分子分母分别成规律，反约分。", '["数量关系", "数字推理", "分数数列"]'),
    (369, "kp_xingce_quantity_number_reasoning_decimal", "小数数列", 5, "数字推理", "小数数列：整数部分和小数部分分别成规律。", '["数量关系", "数字推理", "小数数列"]'),
    (370, "kp_xingce_quantity_number_reasoning_digit_feature", "数位特征数列", 5, "数字推理", "数位特征数列：各位数字之和/积成规律。", '["数量关系", "数字推理", "数位特征"]'),
    (371, "kp_xingce_quantity_number_reasoning_periodic", "周期循环数列", 5, "数字推理", "周期循环数列：规律呈周期性重复。", '["数量关系", "数字推理", "周期循环"]'),
    (372, "kp_xingce_quantity_number_reasoning_special_pattern", "特殊规律数列", 5, "数字推理", "特殊规律数列：其他非常见规律。", '["数量关系", "数字推理", "特殊规律"]'),
]

def make_json(title, summary):
    return json.dumps({
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
            {"type": "heading", "attrs": {"level": 2}, "content": [{"type": "text", "text": "三、易错点"}]},
            {"type": "bulletList", "content": [
                {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "待补充"}]}]}
            ]},
            {"type": "highlightBlock", "attrs": {"backgroundColor": "#eff6ff", "borderColor": "#3b82f6", "icon": "📊"}, "content": [
                {"type": "paragraph", "content": [{"type": "text", "text": "刷题建议：", "marks": [{"type": "bold"}]}, {"type": "text", "text": "待补充。"}]}
            ]}
        ]
    }, ensure_ascii=False)

generated = 0
for node_id, code, name, level, parent_name, summary, tags in nodes:
    slug = "kp-xc-" + code.replace("kp_xingce_", "").replace("_", "-")
    title = name
    json_content = make_json(title, summary)

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

print(f"Generated {generated} SQL files")
