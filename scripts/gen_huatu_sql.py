"""Generate SQL INSERT statements for Huatu version of 行测 knowledge system."""

points = [
    # (name, parent_name, depth)
    # Depth 0 - top-level categories (parent=None)
    ("资料分析", None, 0),
    ("常识判断", None, 0),
    ("言语理解与表达", None, 0),
    ("数量关系", None, 0),
    ("判断推理", None, 0),
    ("政治理论", None, 0),
    ("待分配", None, 0),

    # Depth 1 - under 资料分析
    ("综合分析类", "资料分析", 1),
    ("简单计算", "资料分析", 1),
    ("简单比较", "资料分析", 1),
    ("增长量", "资料分析", 1),
    ("增长率", "资料分析", 1),
    ("比重", "资料分析", 1),
    ("平均数", "资料分析", 1),
    ("倍数", "资料分析", 1),
    ("其他类", "资料分析", 1),
    ("基期与现期（旧）", "资料分析", 1),
    ("基期量", "资料分析", 1),
    ("现期量", "资料分析", 1),

    # Depth 1 - under 常识判断
    ("法律", "常识判断", 1),
    ("历史", "常识判断", 1),
    ("人文", "常识判断", 1),
    ("科技", "常识判断", 1),
    ("经济", "常识判断", 1),
    ("管理公文（旧）", "常识判断", 1),
    ("地理", "常识判断", 1),
    ("管理", "常识判断", 1),
    ("公文", "常识判断", 1),
    ("哲学", "常识判断", 1),
    ("党章党史", "常识判断", 1),

    # Depth 1 - under 言语理解与表达
    ("片段阅读", "言语理解与表达", 1),
    ("逻辑填空", "言语理解与表达", 1),
    ("语句表达", "言语理解与表达", 1),
    ("篇章阅读", "言语理解与表达", 1),

    # Depth 1 - under 数量关系
    ("数字推理", "数量关系", 1),
    ("数学运算", "数量关系", 1),

    # Depth 1 - under 判断推理
    ("类比推理", "判断推理", 1),
    ("定义判断", "判断推理", 1),
    ("逻辑判断", "判断推理", 1),
    ("事件排序", "判断推理", 1),
    ("图形推理", "判断推理", 1),
    ("科学推理", "判断推理", 1),

    # Depth 1 - under 政治理论
    ("时政", "政治理论", 1),
    ("党的创新理论", "政治理论", 1),
    ("马克思主义原理", "政治理论", 1),
    ("其他", "政治理论", 1),

    # Depth 1 - under 待分配
    ("资料分析", "待分配", 1),

    # Depth 2 - under 综合分析类
    ("其他类", "综合分析类", 2),
    ("简单计算", "综合分析类", 2),
    ("简单比较", "综合分析类", 2),
    ("基期量", "综合分析类", 2),
    ("现期量", "综合分析类", 2),
    ("增长量", "综合分析类", 2),
    ("增长率", "综合分析类", 2),
    ("比重", "综合分析类", 2),
    ("平均数", "综合分析类", 2),
    ("倍数", "综合分析类", 2),
    ("选是类分析题", "综合分析类", 2),
    ("选非类分析题", "综合分析类", 2),
    ("多选类分析题", "综合分析类", 2),

    # Depth 2 - under 简单计算
    ("直接读数", "简单计算", 2),
    ("和差类", "简单计算", 2),

    # Depth 2 - under 简单比较
    ("读数比较", "简单比较", 2),
    ("和差比较", "简单比较", 2),
    ("排序比较", "简单比较", 2),

    # Depth 2 - under 增长量
    ("增长量计算", "增长量", 2),
    ("增长量比较", "增长量", 2),
    ("间隔增长量", "增长量", 2),
    ("年均增长量", "增长量", 2),

    # Depth 2 - under 增长率
    ("增长率计算", "增长率", 2),
    ("增长率比较", "增长率", 2),

    # Depth 2 - under 比重
    ("利润率类", "比重", 2),
    ("现期比重", "比重", 2),
    ("基期比重", "比重", 2),
    ("混合比重计算", "比重", 2),
    ("两期比重", "比重", 2),
    ("比值", "比重", 2),
    ("两期比重比较", "比重", 2),
    ("现期比值计算", "比重", 2),
    ("现期比值比较", "比重", 2),
    ("比重比较", "比重", 2),

    # Depth 2 - under 平均数
    ("现期平均数", "平均数", 2),
    ("现期平均数比较", "平均数", 2),
    ("两期平均数", "平均数", 2),
    ("基期平均数", "平均数", 2),
    ("混合平均数计算", "平均数", 2),
    ("平均数增长量比较", "平均数", 2),
    ("平均数增长率", "平均数", 2),
    ("平均数增长率比较", "平均数", 2),

    # Depth 2 - under 倍数
    ("现期倍数", "倍数", 2),
    ("间隔倍数", "倍数", 2),
    ("基期倍数", "倍数", 2),
    ("倍数杂糅", "倍数", 2),
    ("两期倍数", "倍数", 2),

    # Depth 2 - under 其他类
    ("其他计算", "其他类", 2),
    ("其他比较", "其他类", 2),

    # Depth 2 - under 基期与现期（旧）
    ("基期量", "基期与现期（旧）", 2),
    ("现期量", "基期与现期（旧）", 2),

    # Depth 2 - under 基期量
    ("基期量计算", "基期量", 2),
    ("间隔基期量", "基期量", 2),
    ("基期量和差运算", "基期量", 2),
    ("基期量比较", "基期量", 2),

    # Depth 2 - under 现期量
    ("现期量计算", "现期量", 2),
    ("现期量比较", "现期量", 2),

    # Depth 2 - under 法律
    ("宪法", "法律", 2),
    ("行政法", "法律", 2),
    ("民法", "法律", 2),
    ("刑法", "法律", 2),
    ("法理学", "法律", 2),
    ("诉讼法", "法律", 2),
    ("经济法", "法律", 2),
    ("其他法律", "法律", 2),

    # Depth 2 - under 历史
    ("中国史", "历史", 2),
    ("世界史", "历史", 2),

    # Depth 2 - under 人文
    ("文学", "人文", 2),
    ("语言文字", "人文", 2),
    ("传统民俗", "人文", 2),
    ("人文其他", "人文", 2),
    ("艺术常识", "人文", 2),
    ("建筑工程", "人文", 2),
    ("古代文化", "人文", 2),
    ("文学常识", "人文", 2),
    ("人文其它", "人文", 2),

    # Depth 2 - under 科技
    ("科技成就", "科技", 2),
    ("信息技术", "科技", 2),
    ("生物医学", "科技", 2),
    ("地理国情", "科技", 2),
    ("生活常识", "科技", 2),
    ("物理常识", "科技", 2),
    ("化学常识", "科技", 2),

    # Depth 2 - under 经济
    ("马克思主义政治经济学", "经济", 2),
    ("微观经济", "经济", 2),
    ("宏观经济", "经济", 2),
    ("经济组织", "经济", 2),
    ("经济组织与经济名词", "经济", 2),

    # Depth 2 - under 管理公文（旧）
    ("管理（旧）", "管理公文（旧）", 2),
    ("公文（旧）", "管理公文（旧）", 2),

    # Depth 2 - under 地理
    ("自然地理", "地理", 2),
    ("中国地理", "地理", 2),
    ("世界地理", "地理", 2),
    ("省情省况", "地理", 2),

    # Depth 2 - under 管理
    ("管理概述", "管理", 2),
    ("行政管理", "管理", 2),
    ("公共管理", "管理", 2),

    # Depth 2 - under 公文
    ("公文绪论", "公文", 2),
    ("行文规范", "公文", 2),
    ("公文格式", "公文", 2),
    ("公文处理", "公文", 2),
    ("公文写作", "公文", 2),

    # Depth 2 - under 哲学
    ("哲学其它", "哲学", 2),
    ("哲学概述", "哲学", 2),
    ("唯物论", "哲学", 2),
    ("辩证法", "哲学", 2),
    ("认识论", "哲学", 2),
    ("历史唯物主义", "哲学", 2),

    # Depth 2 - under 党章党史
    ("党章党史其它", "党章党史", 2),
    ("党章", "党章党史", 2),
    ("党史大事", "党章党史", 2),
    ("党史其他", "党章党史", 2),

    # Depth 2 - under 片段阅读
    ("主旨概括", "片段阅读", 2),
    ("意图判断", "片段阅读", 2),
    ("标题选择", "片段阅读", 2),
    ("态度理解", "片段阅读", 2),
    ("细节理解", "片段阅读", 2),
    ("词句理解", "片段阅读", 2),
    ("代词指代", "片段阅读", 2),
    ("道理启示", "片段阅读", 2),

    # Depth 2 - under 逻辑填空
    ("实词填空", "逻辑填空", 2),
    ("成语填空", "逻辑填空", 2),
    ("混搭填空", "逻辑填空", 2),

    # Depth 2 - under 语句表达
    ("语句排序", "语句表达", 2),
    ("语句填空", "语句表达", 2),
    ("下文推断", "语句表达", 2),

    # Depth 2 - under 篇章阅读
    ("篇章阅读", "篇章阅读", 2),

    # Depth 2 - under 数字推理
    ("多级数列", "数字推理", 2),
    ("分数数列", "数字推理", 2),
    ("幂次数列", "数字推理", 2),
    ("递推数列", "数字推理", 2),
    ("多重数列", "数字推理", 2),
    ("数图推理", "数字推理", 2),

    # Depth 2 - under 数学运算
    ("代入排除法", "数学运算", 2),
    ("枚举归纳法", "数学运算", 2),
    ("赋值法", "数学运算", 2),
    ("方程法", "数学运算", 2),
    ("工程问题", "数学运算", 2),
    ("行程问题", "数学运算", 2),
    ("经济利润问题", "数学运算", 2),
    ("容斥原理问题", "数学运算", 2),
    ("排列组合问题", "数学运算", 2),
    ("概率问题", "数学运算", 2),
    ("几何问题", "数学运算", 2),
    ("最值问题", "数学运算", 2),
    ("溶液问题", "数学运算", 2),
    ("和差倍比问题", "数学运算", 2),
    ("计算问题", "数学运算", 2),
    ("统筹规划问题", "数学运算", 2),
    ("日期问题", "数学运算", 2),
    ("年龄问题", "数学运算", 2),
    ("星期日期问题", "数学运算", 2),
    ("数列问题", "数学运算", 2),
    ("周期问题", "数学运算", 2),
    ("平均数问题", "数学运算", 2),
    ("函数问题", "数学运算", 2),
    ("比赛问题", "数学运算", 2),
    ("其他问题", "数学运算", 2),

    # Depth 2 - under 类比推理
    ("外延关系", "类比推理", 2),
    ("内涵关系", "类比推理", 2),
    ("词义关系", "类比推理", 2),
    ("语法关系", "类比推理", 2),
    ("逻辑关系", "类比推理", 2),
    ("其他关系", "类比推理", 2),

    # Depth 2 - under 定义判断
    ("单定义", "定义判断", 2),
    ("多定义", "定义判断", 2),

    # Depth 2 - under 逻辑判断
    ("翻译推理", "逻辑判断", 2),
    ("分析推理", "逻辑判断", 2),
    ("真假推理", "逻辑判断", 2),
    ("归纳推理", "逻辑判断", 2),
    ("原因解释", "逻辑判断", 2),
    ("加强论证", "逻辑判断", 2),
    ("削弱论证", "逻辑判断", 2),
    ("日常结论", "逻辑判断", 2),

    # Depth 2 - under 事件排序
    ("事件排序", "事件排序", 2),

    # Depth 2 - under 图形推理
    ("位置类", "图形推理", 2),
    ("样式类", "图形推理", 2),
    ("数量类", "图形推理", 2),
    ("属性类", "图形推理", 2),
    ("功能类", "图形推理", 2),
    ("空间重构", "图形推理", 2),
    ("立体类", "图形推理", 2),
    ("平面拼合", "图形推理", 2),

    # Depth 2 - under 科学推理
    ("物理", "科学推理", 2),
    ("化学", "科学推理", 2),
    ("生物", "科学推理", 2),
    ("地理", "科学推理", 2),
    ("其他", "科学推理", 2),

    # Depth 2 - under 时政
    ("时政", "时政", 2),

    # Depth 2 - under 党的创新理论
    ("党的创新理论", "党的创新理论", 2),

    # Depth 2 - under 马克思主义原理
    ("马克思主义原理", "马克思主义原理", 2),

    # Depth 2 - under 其他（政治理论）
    ("其他", "其他", 2),

    # Depth 2 - under 资料分析（待分配）
    ("资料分析", "资料分析", 2),
]

# Assign sequential codes preserving original order
sequenced = []
seq = 1
for name, parent, depth in points:
    code = f"huatu_{seq}"
    sequenced.append((code, name, parent, depth))
    seq += 1

# Build a map: (name, depth) -> code
name_depth_code = {}
for code, name, parent, depth in sequenced:
    name_depth_code[(name, depth)] = code

def get_parent_code(name, child_depth):
    parent_depth = child_depth - 1
    key = (name, parent_depth)
    return name_depth_code.get(key)

lines = []
lines.append("-- Huatu (华图) 行测 Knowledge System")
lines.append("")
lines.append("-- 1. Insert knowledge system")
lines.append("INSERT INTO qbank_v2_knowledge_system (code, name, version, description, status, created_by, created_time)")
lines.append("SELECT 'xingce', '行测', 'huatu', '华图版行测知识点体系', 'active', 1, NOW()")
lines.append("WHERE NOT EXISTS (SELECT 1 FROM qbank_v2_knowledge_system WHERE code = 'xingce' AND version = 'huatu' AND deleted = false);")
lines.append("")

# Group by depth for ordered output
lines.append("-- 2. Insert knowledge points (depth 0 - top-level)")
for code, name, parent, depth in sequenced:
    if depth == 0:
        lines.append(
            f"INSERT INTO qbank_v2_knowledge_point (system_id, code, name, parent_id, path, depth, sort_order, created_by, created_time) "
            f"SELECT ks.id, '{code}', '{name}', NULL, '{code}', 0, 0, 1, NOW() "
            f"FROM qbank_v2_knowledge_system ks "
            f"WHERE ks.code = 'xingce' AND ks.version = 'huatu' AND ks.deleted = false "
            f"AND NOT EXISTS (SELECT 1 FROM qbank_v2_knowledge_point p WHERE p.system_id = ks.id AND p.code = '{code}');"
        )

lines.append("")
lines.append("-- 3. Insert knowledge points (depth 1)")
for code, name, parent, depth in sequenced:
    if depth == 1:
        parent_code = get_parent_code(parent, depth)
        lines.append(
            f"INSERT INTO qbank_v2_knowledge_point (system_id, code, name, parent_id, path, depth, sort_order, created_by, created_time) "
            f"SELECT ks.id, '{code}', '{name}', p.id, CONCAT(p.path, '/', '{code}'), 1, 0, 1, NOW() "
            f"FROM qbank_v2_knowledge_system ks "
            f"JOIN qbank_v2_knowledge_point p ON p.system_id = ks.id AND p.code = '{parent_code}' "
            f"WHERE ks.code = 'xingce' AND ks.version = 'huatu' AND ks.deleted = false "
            f"AND NOT EXISTS (SELECT 1 FROM qbank_v2_knowledge_point p2 WHERE p2.system_id = ks.id AND p2.code = '{code}');"
        )

lines.append("")
lines.append("-- 4. Insert knowledge points (depth 2)")
for code, name, parent, depth in sequenced:
    if depth == 2:
        parent_code = get_parent_code(parent, depth)
        lines.append(
            f"INSERT INTO qbank_v2_knowledge_point (system_id, code, name, parent_id, path, depth, sort_order, created_by, created_time) "
            f"SELECT ks.id, '{code}', '{name}', p.id, CONCAT(p.path, '/', '{code}'), 2, 0, 1, NOW() "
            f"FROM qbank_v2_knowledge_system ks "
            f"JOIN qbank_v2_knowledge_point p ON p.system_id = ks.id AND p.code = '{parent_code}' "
            f"WHERE ks.code = 'xingce' AND ks.version = 'huatu' AND ks.deleted = false "
            f"AND NOT EXISTS (SELECT 1 FROM qbank_v2_knowledge_point p2 WHERE p2.system_id = ks.id AND p2.code = '{code}');"
        )

lines.append("")

output = "\n".join(lines)

import os
script_dir = os.path.dirname(os.path.abspath(__file__))
output_path = os.path.join(script_dir, "insert_huatu.sql")
with open(output_path, "w", encoding="utf-8") as f:
    f.write(output)

print(f"SQL generated: {output_path}")
print(f"Total statements: {len(lines)}")