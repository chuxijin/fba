import json

api_data = {"baseKeypointVOS": [
    {"id": 832366, "name": "政治理论", "children": [
        {"id": 833701, "name": "马克思主义"}, {"id": 784172, "name": "新思想"},
        {"id": 784173, "name": "时事政治"}, {"id": 942938, "name": "毛中特"}]},
    {"id": 783916, "name": "常识判断", "children": [
        {"id": 784167, "name": "经济常识"}, {"id": 784168, "name": "法律常识"},
        {"id": 784169, "name": "科技常识"}, {"id": 784170, "name": "人文常识"},
        {"id": 784171, "name": "地理国情"}]},
    {"id": 783917, "name": "言语理解与表达", "children": [
        {"id": 784198, "name": "逻辑填空"}, {"id": 784196, "name": "片段阅读"},
        {"id": 784197, "name": "语句表达"}]},
    {"id": 783918, "name": "数量关系", "children": [
        {"id": 784242, "name": "数学运算"}]},
    {"id": 783919, "name": "判断推理", "children": [
        {"id": 784291, "name": "图形推理"}, {"id": 784292, "name": "定义判断"},
        {"id": 784293, "name": "类比推理"}, {"id": 784294, "name": "逻辑判断"}]},
    {"id": 783920, "name": "资料分析", "children": [
        {"id": 784357, "name": "文字资料"}, {"id": 784358, "name": "统计表"},
        {"id": 784359, "name": "统计图"}, {"id": 784360, "name": "综合资料"},
        {"id": 784361, "name": "简单计算"}, {"id": 784362, "name": "基期与现期"},
        {"id": 784363, "name": "增长率"}, {"id": 784364, "name": "增长量"},
        {"id": 784365, "name": "比重问题"}, {"id": 784366, "name": "平均数问题"},
        {"id": 784367, "name": "倍数与比值相关"}, {"id": 784368, "name": "综合分析"}]}
]}

def esc(v):
    return v.replace("'", "''")

for d1 in api_data["baseKeypointVOS"]:
    for idx, c in enumerate(d1.get("children", []), 1):
        sql = (
            f"INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time) "
            f"SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), "
            f"'fenbi_{c['id']}', '{esc(c['name'])}', 1, "
            f"(SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_{d1['id']}' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce')), "
            f"'/fenbi_{c['id']}', {idx}, 1, NOW();"
        )
        print(sql)