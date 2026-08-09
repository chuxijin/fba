import json

api_data = {
    "baseKeypointVOS": [
        {"id": 832366, "name": "政治理论", "children": [
            {"id": 833701, "name": "马克思主义", "children": [
                {"id": 841835, "name": "马克思主义哲学", "children": [
                    {"id": 940962, "name": "总论"}, {"id": 841837, "name": "唯物论"}, {"id": 841838, "name": "唯物辩证法"},
                    {"id": 940963, "name": "认识论"}, {"id": 940964, "name": "唯物史观"}, {"id": 940965, "name": "哲学-其他"}]},
                {"id": 841836, "name": "马克思主义政治经济学", "children": [
                    {"id": 841839, "name": "商品经济"}, {"id": 940966, "name": "资本主义制度"}, {"id": 940967, "name": "政治经济学-其他"}]},
                {"id": 940968, "name": "科学社会主义"}]},
            {"id": 784172, "name": "新思想", "children": [
                {"id": 841840, "name": "新思想总论"},
                {"id": 941849, "name": "五位一体建设", "children": [
                    {"id": 841841, "name": "经济建设"}, {"id": 841842, "name": "政治建设"}, {"id": 841843, "name": "文化建设"},
                    {"id": 841844, "name": "社会建设"}, {"id": 841845, "name": "生态文明建设"}]},
                {"id": 941850, "name": "其他建设"}]},
            {"id": 784173, "name": "时事政治", "children": [
                {"id": 841851, "name": "重要文件"}, {"id": 841852, "name": "重要会议讲话"}, {"id": 841853, "name": "重要事件"},
                {"id": 841854, "name": "时事政治-其他"}]},
            {"id": 942938, "name": "毛中特", "children": [
                {"id": 942939, "name": "党的基本知识", "children": [
                    {"id": 942940, "name": "党的历史"}, {"id": 942941, "name": "党章党纪"}]}]}]},
        {"id": 783916, "name": "常识判断", "children": [
            {"id": 784167, "name": "经济常识", "children": [
                {"id": 784175, "name": "宏观经济与调控政策"}, {"id": 942652, "name": "市场经济"},
                {"id": 942653, "name": "国际经济及组织"}, {"id": 942654, "name": "微观经济"}]},
            {"id": 784168, "name": "法律常识", "children": [
                {"id": 942540, "name": "法理学"}, {"id": 942541, "name": "宪法"}, {"id": 784178, "name": "行政法"},
                {"id": 784180, "name": "民法典"}, {"id": 942542, "name": "刑法"}, {"id": 942543, "name": "诉讼法"},
                {"id": 942544, "name": "劳动法和经济法"}, {"id": 784182, "name": "其他法律法规"}]},
            {"id": 784169, "name": "科技常识", "children": [
                {"id": 784185, "name": "物理常识"}, {"id": 784186, "name": "化学常识"}, {"id": 784187, "name": "生物常识"},
                {"id": 784188, "name": "生活常识"}, {"id": 784189, "name": "科技理论与成就"}, {"id": 824746, "name": "科技常识-其他"}]},
            {"id": 784170, "name": "人文常识", "children": [
                {"id": 784190, "name": "中国历史"}, {"id": 784192, "name": "文学常识"}, {"id": 784193, "name": "文化常识"}]},
            {"id": 784171, "name": "地理国情", "children": [
                {"id": 784194, "name": "自然地理"}, {"id": 784195, "name": "中国地理"}, {"id": 943088, "name": "世界地理"},
                {"id": 943089, "name": "其他"}]}]},
        {"id": 783917, "name": "言语理解与表达", "children": [
            {"id": 784198, "name": "逻辑填空", "children": [
                {"id": 784226, "name": "实词填空"}, {"id": 784227, "name": "成语填空"}, {"id": 784228, "name": "混搭填空"},
                {"id": 784229, "name": "词的辨析", "children": [
                    {"id": 784231, "name": "词的辨析-词义侧重"}, {"id": 784232, "name": "词的辨析-搭配对象"},
                    {"id": 784233, "name": "词的辨析-感情色彩"}, {"id": 784234, "name": "词的辨析-程度轻重"}]},
                {"id": 784230, "name": "语境分析", "children": [
                    {"id": 784235, "name": "关联关系-转折关系"}, {"id": 784236, "name": "关联关系-因果关系"},
                    {"id": 784237, "name": "关联关系-并列关系"}, {"id": 784238, "name": "对应关系-解释说明"},
                    {"id": 784239, "name": "对应关系-形象表达"}, {"id": 827859, "name": "对应关系-主题词"},
                    {"id": 827860, "name": "对应关系-前后呼应"}]}]},
            {"id": 784196, "name": "片段阅读", "children": [
                {"id": 784199, "name": "中心理解题", "children": [
                    {"id": 784203, "name": "关联词-转折"}, {"id": 784204, "name": "关联词-因果"}, {"id": 784205, "name": "关联词-对策"},
                    {"id": 784206, "name": "关联词-并列"}, {"id": 784207, "name": "主题词"}, {"id": 784209, "name": "分述句特征-举例子"},
                    {"id": 784210, "name": "分述句特征-数据资料"}, {"id": 784211, "name": "分述句特征-多角度论述"},
                    {"id": 840743, "name": "分述句特征-引入铺垫"}, {"id": 840744, "name": "分述句特征-其他"}, {"id": 784212, "name": "特殊问法"}]},
                {"id": 784200, "name": "细节判断题"},
                {"id": 784201, "name": "词句理解题", "children": [
                    {"id": 784213, "name": "实词"}, {"id": 842998, "name": "代词"}, {"id": 842999, "name": "句子"}]},
                {"id": 784202, "name": "标题填入题"}]},
            {"id": 784197, "name": "语句表达", "children": [
                {"id": 784215, "name": "语句排序题", "children": [
                    {"id": 784218, "name": "确定首句-首句特征"}, {"id": 833707, "name": "确定首句-非首句特征"},
                    {"id": 784220, "name": "确定捆绑"}, {"id": 784221, "name": "确定顺序"}, {"id": 784222, "name": "确定尾句"}]},
                {"id": 784216, "name": "语句填空题", "children": [
                    {"id": 784223, "name": "横线在开头"}, {"id": 784224, "name": "横线在中间"},
                    {"id": 784225, "name": "横线在结尾"}, {"id": 843000, "name": "特殊题型-问语句在文中的位置"}]},
                {"id": 784217, "name": "接语选择题"},
                {"id": 843001, "name": "语句排序题、语句填空题混合题型"}]}]},
        {"id": 783918, "name": "数量关系", "children": [
            {"id": 784242, "name": "数学运算", "children": [
                {"id": 784243, "name": "工程问题", "children": [
                    {"id": 784258, "name": "给完工时间型"}, {"id": 784259, "name": "给效率比例型"},
                    {"id": 784260, "name": "给具体单位型"}, {"id": 784261, "name": "工程问题-其他"}]},
                {"id": 784244, "name": "最值问题", "children": [
                    {"id": 784262, "name": "非典型最值问题"}, {"id": 784263, "name": "构造数列"},
                    {"id": 784264, "name": "最不利构造"}, {"id": 784265, "name": "多集合反向构造"}]},
                {"id": 784245, "name": "年龄问题"},
                {"id": 784246, "name": "周期问题", "children": [
                    {"id": 784266, "name": "周期相遇问题"}, {"id": 784267, "name": "周期余数问题"},
                    {"id": 784268, "name": "周期问题-其他"}]},
                {"id": 784247, "name": "和差倍比问题"}, {"id": 784248, "name": "数列问题"},
                {"id": 784249, "name": "行程问题", "children": [
                    {"id": 784269, "name": "火车过桥"}, {"id": 784270, "name": "平均速度"}, {"id": 784271, "name": "普通行程"},
                    {"id": 784272, "name": "相遇追及"}, {"id": 784273, "name": "流水行船"}, {"id": 784274, "name": "行程问题-其他"}]},
                {"id": 784250, "name": "几何问题", "children": [
                    {"id": 784275, "name": "几何公式类-平面图形"}, {"id": 784276, "name": "几何公式类-立体图形"},
                    {"id": 849716, "name": "几何结论类-相似图形"}, {"id": 849717, "name": "几何结论类-三角形相关"},
                    {"id": 849718, "name": "几何结论类-几何小题型"}, {"id": 849719, "name": "几何其他题型"}]},
                {"id": 784251, "name": "容斥原理问题", "children": [
                    {"id": 784277, "name": "两集合"}, {"id": 784278, "name": "三集合"}]},
                {"id": 784252, "name": "排列组合问题", "children": [
                    {"id": 784279, "name": "基础排列组合"}, {"id": 784280, "name": "相邻问题"}, {"id": 784281, "name": "不相邻问题"},
                    {"id": 784282, "name": "同素分堆问题"}, {"id": 784283, "name": "环形排列问题"}, {"id": 784284, "name": "错位排列"},
                    {"id": 784285, "name": "排列组合问题-其他"}]},
                {"id": 784253, "name": "概率问题", "children": [
                    {"id": 784286, "name": "给情况求概率"}, {"id": 784287, "name": "给概率求概率"},
                    {"id": 784288, "name": "概率问题-其他"}]},
                {"id": 784254, "name": "经济利润问题"}, {"id": 784256, "name": "统筹规划问题"},
                {"id": 810831, "name": "星期日期问题"}, {"id": 842968, "name": "分段计算问题"},
                {"id": 842969, "name": "函数最值问题"}, {"id": 941046, "name": "平均数问题"}]}]},
        {"id": 783919, "name": "判断推理", "children": [
            {"id": 784291, "name": "图形推理", "children": [
                {"id": 784295, "name": "位置规律", "children": [
                    {"id": 784303, "name": "位置规律-平移"}, {"id": 784304, "name": "位置规律-旋转"},
                    {"id": 784305, "name": "位置规律-综合"}, {"id": 842988, "name": "位置规律-翻转"}]},
                {"id": 784296, "name": "样式规律", "children": [
                    {"id": 784306, "name": "样式规律-加减同异"}, {"id": 784307, "name": "样式规律-黑白运算"},
                    {"id": 842989, "name": "样式规律-遍历"}]},
                {"id": 784297, "name": "属性规律", "children": [
                    {"id": 784308, "name": "属性规律-对称性"}, {"id": 842990, "name": "属性规律-开闭性"},
                    {"id": 842991, "name": "属性规律-曲直性"}, {"id": 842992, "name": "属性规律-复合"}]},
                {"id": 784298, "name": "数量规律", "children": [
                    {"id": 784309, "name": "数量规律-点"}, {"id": 784310, "name": "数量规律-线"},
                    {"id": 784311, "name": "数量规律-面"}, {"id": 784312, "name": "数量规律-角"},
                    {"id": 784313, "name": "数量规律-素"}, {"id": 784314, "name": "数量规律-复合"}]},
                {"id": 784299, "name": "特殊规律", "children": [
                    {"id": 784315, "name": "特殊规律-图形间关系"}, {"id": 842993, "name": "特殊规律-功能元素"}]},
                {"id": 784300, "name": "空间类", "children": [
                    {"id": 784317, "name": "空间类-立体拼合"}, {"id": 784318, "name": "空间类-三视图"},
                    {"id": 784319, "name": "空间类-截面图"}, {"id": 784320, "name": "空间类-空间重构-六面体"}]},
                {"id": 784302, "name": "文字/字母/数字类"}, {"id": 784301, "name": "黑白块类"}]},
            {"id": 784292, "name": "定义判断", "children": [
                {"id": 784322, "name": "单定义", "children": [
                    {"id": 784324, "name": "主客体"}, {"id": 784325, "name": "大前提"}, {"id": 784326, "name": "方式目的"},
                    {"id": 784327, "name": "原因结果"}, {"id": 784328, "name": "单定义-其他句式"},
                    {"id": 792382, "name": "故事类"}, {"id": 792383, "name": "拆词"}]},
                {"id": 784323, "name": "多定义", "children": [
                    {"id": 784329, "name": "常规问法"}, {"id": 784330, "name": "特殊问法"}]}]},
            {"id": 784293, "name": "类比推理", "children": [
                {"id": 784331, "name": "语义关系", "children": [
                    {"id": 784334, "name": "语义关系-近义关系"}, {"id": 784335, "name": "语义关系-反义关系"},
                    {"id": 817348, "name": "语义关系-比喻象征义"}, {"id": 784336, "name": "语义-其他"}]},
                {"id": 784332, "name": "逻辑关系", "children": [
                    {"id": 784338, "name": "逻辑关系-并列关系"}, {"id": 784339, "name": "逻辑关系-交叉关系"},
                    {"id": 784340, "name": "逻辑关系-包容关系"}, {"id": 784341, "name": "逻辑关系-对应关系"},
                    {"id": 842994, "name": "逻辑关系-全同关系"}]},
                {"id": 838304, "name": "语法关系"}, {"id": 784333, "name": "拆分思维"}]},
            {"id": 784294, "name": "逻辑判断", "children": [
                {"id": 784342, "name": "加强题型", "children": [
                    {"id": 784347, "name": "搭桥"}, {"id": 784348, "name": "必要条件"}, {"id": 784349, "name": "补充论据"},
                    {"id": 784350, "name": "加强选非题"}, {"id": 784351, "name": "加强-实验类"}]},
                {"id": 784343, "name": "削弱题型", "children": [
                    {"id": 784352, "name": "削弱论点"}, {"id": 784353, "name": "拆桥"}, {"id": 784354, "name": "他因削弱"},
                    {"id": 784355, "name": "削弱选非题"}, {"id": 792384, "name": "削弱论据"},
                    {"id": 792385, "name": "因果倒置"}, {"id": 792386, "name": "削弱-实验类"}]},
                {"id": 784346, "name": "翻译推理", "children": [
                    {"id": 784356, "name": "常规翻译"}, {"id": 792387, "name": "集合推理"}, {"id": 792388, "name": "推理形式"}]},
                {"id": 784344, "name": "组合排列-材料"},
                {"id": 842995, "name": "组合排列-单题", "children": [
                    {"id": 851140, "name": "排除法"}, {"id": 851141, "name": "代入法"}, {"id": 851142, "name": "从最大信息开始推"},
                    {"id": 851143, "name": "假设"}, {"id": 851144, "name": "框架题"}, {"id": 851145, "name": "从确定信息开始推"},
                    {"id": 943529, "name": "组合排列-单题-其他"}]},
                {"id": 784345, "name": "原因解释"},
                {"id": 837343, "name": "真假推理", "children": [
                    {"id": 851146, "name": "只有一真/一假"}, {"id": 851147, "name": "两真两假"},
                    {"id": 851148, "name": "真假推理-其他"}]},
                {"id": 842996, "name": "日常结论"}, {"id": 842997, "name": "论证结构"}]}]},
        {"id": 783920, "name": "资料分析", "children": [
            {"id": 784357, "name": "文字资料"}, {"id": 784358, "name": "统计表"}, {"id": 784359, "name": "统计图"},
            {"id": 784360, "name": "综合资料"},
            {"id": 784361, "name": "简单计算", "children": [
                {"id": 784369, "name": "直接找数"}, {"id": 784370, "name": "简单加减计算"}, {"id": 792390, "name": "排序类"}]},
            {"id": 784362, "name": "基期与现期", "children": [
                {"id": 784371, "name": "基期计算"}, {"id": 784372, "name": "现期计算"}, {"id": 792391, "name": "基期比较"},
                {"id": 792392, "name": "间隔基期"}, {"id": 792393, "name": "基期和差"}]},
            {"id": 784363, "name": "增长率", "children": [
                {"id": 784373, "name": "一般增长率"}, {"id": 784374, "name": "混合增长率"},
                {"id": 792395, "name": "间隔增长率"}, {"id": 792396, "name": "年均增长率"}]},
            {"id": 784364, "name": "增长量", "children": [
                {"id": 784375, "name": "增长量计算"}, {"id": 784376, "name": "增长量比较"},
                {"id": 792397, "name": "间隔增长量"}, {"id": 792398, "name": "年均增长量"}]},
            {"id": 784365, "name": "比重问题", "children": [
                {"id": 784377, "name": "现期比重"}, {"id": 784378, "name": "基期比重"},
                {"id": 784379, "name": "两期比重"}, {"id": 792399, "name": "混合比重"}]},
            {"id": 784366, "name": "平均数问题", "children": [
                {"id": 784380, "name": "基期平均数"}, {"id": 784381, "name": "现期平均数"},
                {"id": 784382, "name": "平均数的增长率"}, {"id": 784383, "name": "平均数的增长量"},
                {"id": 784384, "name": "两期平均数比较"}]},
            {"id": 784367, "name": "倍数与比值相关", "children": [
                {"id": 784385, "name": "基期倍数"}, {"id": 784386, "name": "现期倍数"},
                {"id": 792400, "name": "比值计算"}, {"id": 792401, "name": "比值比较"}, {"id": 792402, "name": "倍数比较"}]},
            {"id": 784368, "name": "综合分析"}]}
    ]
}

def esc(val):
    return val.replace("'", "''")

def gen():
    parts = []

    # 1. Insert knowledge system
    parts.append("INSERT INTO qbank_v2_knowledge_system (code, name, version, description, status, created_by, created_time)")
    parts.append("VALUES ('xingce', '行测', 'fenbi', '粉笔行测知识点体系', 'active', 1, NOW());")
    parts.append("")

    # Build all nodes with depth info
    all_nodes = {}
    d1_nodes = []

    for idx, d1 in enumerate(api_data["baseKeypointVOS"]):
        node = {"id": d1["id"], "name": d1["name"], "depth": 0, "parent_id": None, "sort_order": idx + 1, "children": []}
        all_nodes[d1["id"]] = node
        d1_nodes.append(node)
        if "children" in d1:
            for idx2, d2 in enumerate(d1["children"]):
                node2 = {"id": d2["id"], "name": d2["name"], "depth": 1, "parent_id": d1["id"], "sort_order": idx2 + 1, "children": []}
                all_nodes[d2["id"]] = node2
                node["children"].append(node2)
                if "children" in d2:
                    for idx3, d3 in enumerate(d2["children"]):
                        node3 = {"id": d3["id"], "name": d3["name"], "depth": 2, "parent_id": d2["id"], "sort_order": idx3 + 1, "children": []}
                        all_nodes[d3["id"]] = node3
                        node2["children"].append(node3)
                        if "children" in d3:
                            for idx4, d4 in enumerate(d3["children"]):
                                node4 = {"id": d4["id"], "name": d4["name"], "depth": 3, "parent_id": d3["id"], "sort_order": idx4 + 1, "children": []}
                                all_nodes[d4["id"]] = node4
                                node3["children"].append(node4)

    # Generate inserts per depth level
    for depth in range(4):
        nodes_at_depth = [n for n in all_nodes.values() if n["depth"] == depth]
        if not nodes_at_depth:
            continue
        vals = []
        for n in nodes_at_depth:
            code = f"fenbi_{n['id']}"
            name = esc(n["name"])
            pid = f"(SELECT id FROM qbank_v2_knowledge_point WHERE code = 'fenbi_{n['parent_id']}' AND system_id = (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'))" if n["parent_id"] else "NULL"
            path = f"/{code}"
            parts.append(f"-- {name}")
            parts.append(f"INSERT INTO qbank_v2_knowledge_point (system_id, code, name, depth, parent_id, path, sort_order, created_by, created_time)")
            parts.append(f"SELECT (SELECT id FROM qbank_v2_knowledge_system WHERE code = 'xingce'), '{code}', '{name}', {depth}, {pid}, '/{code}', {n['sort_order']}, 1, NOW();")

    return "\n".join(parts)

if __name__ == "__main__":
    print(gen())