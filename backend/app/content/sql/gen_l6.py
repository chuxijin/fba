#!/usr/bin/env python3
"""Generate SQL for L6 nodes"""
import json, os

sql_dir = "D:/100_Work/101_Program/Proj/fba/backend/app/content/sql"

# L6 nodes: (id, code, name, parent_name)
l6_nodes = [
    (492, "kp_eng_basic", "基础工程", "工程问题"),
    (493, "kp_eng_coop", "合作工程", "工程问题"),
    (494, "kp_eng_shift", "轮换工程", "工程问题"),
    (495, "kp_eng_stage", "分段工程", "工程问题"),
    (496, "kp_eng_eff_change", "效率变化工程", "工程问题"),
    (497, "kp_eng_constraint", "条件制约工程", "工程问题"),
    (432, "kp_travel_chase", "追及问题", "行程问题"),
    (433, "kp_travel_roundtrip", "往返行程", "行程问题"),
    (434, "kp_travel_multi_meet", "多人多次相遇", "行程问题"),
    (435, "kp_travel_circle", "环形行程", "行程问题"),
    (436, "kp_travel_boat", "流水行船", "行程问题"),
    (437, "kp_travel_train", "火车行程", "行程问题"),
    (438, "kp_travel_escalator", "扶梯行程", "行程问题"),
    (439, "kp_travel_ratio", "比例行程", "行程问题"),
    (440, "kp_travel_avg_speed", "平均速度", "行程问题"),
    (441, "kp_travel_segment_speed", "分段变速行程", "行程问题"),
    (537, "kp_age_basic", "基础年龄", "年龄问题"),
    (538, "kp_age_diff", "年龄差不变", "年龄问题"),
    (539, "kp_age_multiple", "年龄倍数", "年龄问题"),
    (540, "kp_age_before_after", "若干年前后", "年龄问题"),
    (541, "kp_age_multi_people", "多人年龄关系", "年龄问题"),
    (542, "kp_age_average", "平均年龄", "年龄问题"),
    (543, "kp_age_year", "年龄与年份", "年龄问题"),
    (577, "kp_conc_basic", "基础浓度", "浓度问题"),
    (578, "kp_conc_mix", "混合溶液", "浓度问题"),
    (579, "kp_conc_dilute", "稀释与浓缩", "浓度问题"),
    (580, "kp_conc_change", "溶质溶剂变化", "浓度问题"),
    (581, "kp_conc_repeat", "反复操作", "浓度问题"),
    (583, "kp_conc_ratio", "溶液配比", "浓度问题"),
    (702, "kp_pc_basic", "基础计数", "排列组合"),
    (703, "kp_pc_case_step", "分类分步", "排列组合"),
    (704, "kp_pc_perm", "排列问题", "排列组合"),
    (705, "kp_pc_comb", "组合问题", "排列组合"),
    (706, "kp_pc_special_limit", "特殊元素限制", "排列组合"),
    (707, "kp_pc_group_assign", "分组分配", "排列组合"),
    (708, "kp_pc_bind_gap", "捆绑与插空", "排列组合"),
    (709, "kp_pc_derange_circle", "错位与环排", "排列组合"),
    (1005, "kp_grass_basic", "基础牛吃草", "牛吃草问题"),
    (1006, "kp_grass_growth", "草生长量", "牛吃草问题"),
    (1007, "kp_grass_multi", "多牛多地", "牛吃草问题"),
    (917, "kp_ext_basic", "基础最值", "最值问题"),
    (918, "kp_ext_sum_product", "和定积值最值", "最值问题"),
    (920, "kp_ext_distribution", "方案分配最值", "最值问题"),
    (921, "kp_ext_number", "数列数值最值", "最值问题"),
    (922, "kp_ext_application", "实际应用最值", "最值问题"),
    (617, "kp_profit_basic", "基础利润", "经济利润问题"),
    (618, "kp_profit_cost_price_rate", "成本售价利润率", "经济利润问题"),
    (619, "kp_profit_discount", "打折促销", "经济利润问题"),
    (621, "kp_profit_tier_price", "分段计价", "经济利润问题"),
    (622, "kp_profit_bundle", "多件组合销售", "经济利润问题"),
    (623, "kp_profit_break_even", "盈亏平衡", "经济利润问题"),
    (624, "kp_profit_tax_fee", "税费佣金", "经济利润问题"),
    (662, "kp_ratio_basic", "基础比例", "比例倍数问题"),
    (663, "kp_ratio_parts", "连比与份数", "比例倍数问题"),
    (664, "kp_ratio_direct_inverse", "正反比关系", "比例倍数问题"),
    (665, "kp_ratio_change", "比例变化", "比例倍数问题"),
    (666, "kp_ratio_multiple", "倍数关系", "比例倍数问题"),
    (667, "kp_ratio_distribution", "按比例分配", "比例倍数问题"),
    (877, "kp_plan_basic", "基础统筹", "统筹规划问题"),
    (878, "kp_plan_time", "时间安排", "统筹规划问题"),
    (879, "kp_plan_order", "顺序优化", "统筹规划问题"),
    (880, "kp_plan_resource", "资源分配", "统筹规划问题"),
    (881, "kp_plan_route", "路线规划", "统筹规划问题"),
    (882, "kp_plan_queue", "排队等待", "统筹规划问题"),
    (883, "kp_plan_opt", "最优决策", "统筹规划问题"),
    (792, "kp_geo_plane_basic", "平面图形基础", "几何问题"),
    (793, "kp_geo_triangle_quad", "三角形与四边形", "几何问题"),
    (794, "kp_geo_circle_sector", "圆与扇形", "几何问题"),
    (795, "kp_geo_perimeter_area", "周长面积计算", "几何问题"),
    (796, "kp_geo_solid", "立体几何", "几何问题"),
    (797, "kp_geo_count", "几何计数", "几何问题"),
    (798, "kp_geo_extreme", "最值几何", "几何问题"),
    (799, "kp_geo_coordinate", "解析与坐标几何", "几何问题"),
    (837, "kp_eq_basic", "基础方程", "方程与不定方程"),
    (838, "kp_eq_linear", "一元一次方程", "方程与不定方程"),
    (839, "kp_eq_system", "二元一次方程组", "方程与不定方程"),
    (840, "kp_eq_indef_basic", "不定方程基础", "方程与不定方程"),
    (841, "kp_eq_div_parity", "整除与奇偶约束", "方程与不定方程"),
    (843, "kp_eq_app", "方程应用题", "方程与不定方程"),
    (747, "kp_prob_basic", "基础概率", "概率问题"),
    (748, "kp_prob_classic", "古典概率", "概率问题"),
    (749, "kp_prob_counting", "分类计数概率", "概率问题"),
    (750, "kp_prob_complement", "对立事件与至少", "概率问题"),
    (751, "kp_prob_repeat", "独立重复试验", "概率问题"),
    (752, "kp_prob_draw", "抽取与放回", "概率问题"),
    (753, "kp_prob_geometry", "几何概率", "概率问题"),
    (754, "kp_prob_condition", "条件概率直观题", "概率问题"),
    (977, "kp_cal_basic", "基础日期计算", "星期日期问题"),
    (978, "kp_cal_weekday", "星期推算", "星期日期问题"),
    (979, "kp_cal_leap_year", "闰年与平年", "星期日期问题"),
    (980, "kp_cal_cycle", "周期问题", "星期日期问题"),
    (981, "kp_cal_range_count", "日期范围统计", "星期日期问题"),
    (982, "kp_cal_special", "特殊日期问题", "星期日期问题"),
    (945, "kp_rd_div_rule", "整除判定", "余数与整除"),
    (946, "kp_rd_remainder_basic", "余数基本性质", "余数与整除"),
    (947, "kp_rd_congruence", "同余思想", "余数与整除"),
    (948, "kp_rd_parity_multiple", "奇偶与倍数", "余数与整除"),
    (949, "kp_rd_construct", "整除构造", "余数与整除"),
    (950, "kp_rd_cycle", "余数周期", "余数与整除"),
    (951, "kp_rd_equation", "方程中的余数整除", "余数与整除"),
]

def make_json(name, parent):
    return json.dumps({
        "type": "doc",
        "content": [
            {"type": "heading", "attrs": {"level": 1}, "content": [{"type": "text", "text": name}]},
            {"type": "highlightBlock", "attrs": {"backgroundColor": "#fffbeb", "borderColor": "#f59e0b", "icon": "💡"}, "content": [
                {"type": "paragraph", "content": [{"type": "text", "text": "核心结论：", "marks": [{"type": "bold"}]}, {"type": "text", "text": f"{parent}-{name}的核心知识点和解题方法。"}]}
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

generated = 0
for node_id, code, name, parent_name in l6_nodes:
    slug = f"kp-xc-{code.replace('kp_', '').replace('_', '-')}"
    summary = f"数量关系-{parent_name}-{name}的核心知识点。"
    tags = f'["数量关系", "{parent_name}", "{name}"]'
    json_content = make_json(name, parent_name)

    sql = f"""WITH category_node AS (
    SELECT id FROM sys_category WHERE app_code = 'youanshang' AND type = 'knowledge_point' AND code = '{code}'
)
INSERT INTO sys_content (app_code, title, slug, content_json, content_html, summary, category_id, tags, is_pinned, is_public, is_published, publish_time, view_count, sort_order, extra, created_by, created_time)
SELECT 'gongkao', '{name}', '{slug}', CAST($${json_content}$$ AS jsonb), NULL, '{summary}', category_node.id, CAST('{tags}' AS jsonb), FALSE, TRUE, TRUE, NOW(), 0, 0, CAST('{{"content_type": "knowledge_point", "category_code": "{code}", "source": "fba_content_engine"}}' AS jsonb), 1, NOW()
FROM category_node ON CONFLICT (slug) DO UPDATE SET title = EXCLUDED.title, content_json = EXCLUDED.content_json, summary = EXCLUDED.summary, category_id = EXCLUDED.category_id, tags = EXCLUDED.tags, extra = EXCLUDED.extra, updated_time = NOW();
"""

    filename = f"kp_xc_{code.replace('kp_', '')}.sql"
    filepath = os.path.join(sql_dir, filename)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(sql)

    generated += 1

print(f"Generated {generated} L6 SQL files")
