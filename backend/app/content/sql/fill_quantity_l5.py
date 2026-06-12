#!/usr/bin/env python3
"""Fill real content for 数量关系 L5 数学运算 overviews"""
import json, os

sql_dir = "D:/100_Work/101_Program/Proj/fba/backend/app/content/sql"

# (code, slug, title, conclusion, knowledge_points, methods, mistakes, practice)
l5_math = [
    ("kp_xingce_quantity_math_operation_inclusion_exclusion", "容斥问题",
     "容斥问题是数量关系高频考点，核心是多集合交并补的计数，两集合和三集合公式必须熟练掌握。",
     ["两集合容斥公式：A∪B = A + B - A∩B，即总人数 = 只参加A + 只参加B + 都参加 + 都不参加",
      "三集合容斥公式：A∪B∪C = A + B + C - A∩B - A∩C - B∩C + A∩B∩C",
      "三集合标准型：总数 = A + B + C - 仅两项 - 2×三项都 + 都不参加",
      "画韦恩图是解容斥题最直观的方法，用圆圈表示各集合，从内向外逐步填写",
      '容斥问题常与最值结合，如"至少参加一项"求最小值，"至多参加一项"求最大值'],
     ["公式法：直接套用两集合或三集合公式，适合条件清晰的题目",
      "韦恩图法：画图标注各区域人数，从中心（三项都参加）向外填写",
      "方程法：设未知量表示交集部分，列方程求解",
      "整体减去都不：总数 - 都不参加 = 至少参加一项"],
     ['混淆"仅参加两项"和"参加两项"：前者不含三项都参加的，后者可能包含',
      '三集合公式中"至少参加两项"的计算容易漏掉三项都参加的部分',
      '忘记"都不参加"这一项，导致总数对不上'],
     "容斥问题每年必考1-2题，建议先背熟公式再做题，重点练习三集合标准型。"),

    ("kp_xingce_quantity_math_operation_permutation_combination", "排列组合",
     "排列组合是数量关系的核心基础，分类加法和分步乘法是基本原理，排列和组合的区别在于是否考虑顺序。",
     ["分类加法原理：完成一件事有n类方法，各类方法数分别为m1,m2,...,mn，则总方法数 = m1+m2+...+mn",
      "分步乘法原理：完成一件事需n个步骤，各步方法数分别为m1,m2,...,mn，则总方法数 = m1×m2×...×mn",
      "排列Anm = n!/(n-m)!，从n个不同元素中取m个排成一列，顺序有关",
      "组合Cnm = n!/[m!(n-m)!]，从n个不同元素中取m个组成一组，顺序无关",
      "常用技巧：捆绑法（相邻问题）、插空法（不相邻问题）、隔板法（相同元素分组）"],
     ["先判断是排列还是组合：有序选排列，无序选组合",
      "先分类再分步：先确定用加法还是乘法，再计算每类/每步的方法数",
      "特殊元素优先处理：先安排有限制的元素，再安排无限制的",
      "正难则反：直接计算困难时，用总数减去反面情况"],
     ['混淆排列和组合：看到"选"就用组合，但"选出来排成一排"要用排列',
      "重复计数：捆绑法忘记内部排列，或插空法算错空位数",
      "分类不互斥：用加法原理时各类情况必须互斥，否则要减去重复"],
     "排列组合是概率和容斥的基础，必须先掌握。建议分类练习：基础计算、捆绑插空、隔板法、分组分配。"),

    ("kp_xingce_quantity_math_operation_grass_eating", "牛吃草问题",
     "牛吃草问题本质是追及问题的变形，核心是草在同时生长，解题关键是求出草的生长速度和原有草量。",
     ["基本模型：原有草量M，草每天生长r，每头牛每天吃1份草",
      "核心公式：M = (N - r) × T，其中N为牛的数量，T为吃完天数",
      "两组条件列方程：M = (N1-r)×T1 = (N2-r)×T2，解出r和M",
      "草生长速度 r = (N1×T1 - N2×T2)/(T1 - T2)",
      "变形题型：窗口售票（人排队）、自动扶梯、水管注水等都可用牛吃草模型"],
     ["设每头牛每天吃草量为1份，统一单位",
      "用两组条件列方程组，先求草的生长速度r，再求原有草量M",
      '求"几头牛几天吃完"：N = M/T + r',
      '变形识别：看到"同时进同时出"类问题，联想牛吃草模型'],
     ["忽略草在生长，直接用原有草量除以牛数",
      "两组条件列方程时搞混N和T的对应关系",
      "变形题不会转化：如窗口售票问题不知道类比牛吃草"],
     '牛吃草问题公式固定，属于"背公式就能做对"的题型。重点练习标准型和变形应用。'),

    ("kp_xingce_quantity_math_operation_extreme_value", "最值问题",
     "最值问题是数量关系的高频考点，核心思想是在约束条件下求最大或最小值，最不利原则是最常考的类型。",
     ["最不利原则（至少...才能保证）：考虑最坏情况再加1，答案 = 最不利情况 + 1",
      "和定最值：多个数之和固定，求某个数的最大/最小值。原则：此消彼长",
      "积定最值：多个正数之和固定，乘积最大时各数相等（或尽量接近）",
      "均值不等式：a+b ≥ 2√(ab)，当且仅当a=b时取等号",
      "构造法：根据题意构造出满足条件的极端情况"],
     ['最不利原则题：先想"最倒霉的情况是什么"，再加1',
      "和定最值题：求最大值让其他尽量小，求最小值让其他尽量大",
      "整数约束：人数、个数必须是正整数，利用整除性缩小范围",
      "极端构造法：直接构造出满足条件的极端情况来验证"],
     ["最不利原则忘记加1",
      '和定最值忽略"互不相等"等约束条件',
      "整数约束下直接用均值不等式，没有考虑整数解"],
     "最值问题是高频考点，最不利原则几乎每年必考。建议重点练习最不利原则和和定最值两类题型。"),

    ("kp_xingce_quantity_math_operation_profit", "经济利润问题",
     "经济利润问题围绕利润、成本、售价、利润率四个量展开，核心公式必须熟练，打折促销是常考场景。",
     ["核心公式：利润 = 售价 - 成本，利润率 = 利润/成本 × 100%",
      "售价 = 成本 × (1 + 利润率)，成本 = 售价 / (1 + 利润率)",
      "打折：实际售价 = 标价 × 折扣率（如八折 = 0.8）",
      "分段计价：不同数量区间单价不同，如阶梯电价、阶梯水费",
      "盈亏平衡：总收入 = 总成本时的销量或单价"],
     ["设成本或售价为未知量，用利润率公式列方程",
      "打折题先算标价，再乘折扣率得到实际售价",
      "分段计价题分段计算，注意每段的边界值",
      "多件组合题用总价减去单件价格之和算优惠"],
     ["利润率的分母是成本不是售价，这是最常见的错误",
      "打折和利润率的关系搞混：八折不等于利润率20%",
      '分段计价时边界值算错，如"超过100件"是>100还是≥100'],
     "经济利润问题公式性强，练熟公式就能拿分。重点练习打折促销和分段计价两种题型。"),

    ("kp_xingce_quantity_math_operation_ratio_multiple", "比例倍数问题",
     "比例倍数问题是数量关系的基础工具，正反比关系广泛应用于行程、工程、浓度等多个模块。",
     ["正比关系：y = kx，x增大y也增大，如速度一定时路程与时间成正比",
      "反比关系：y = k/x，x增大y减小，如路程一定时速度与时间成反比",
      "连比与份数：a:b:c = m:n:p，总份数为m+n+p，各部分占比为m/(m+n+p)",
      "按比例分配：总量按份数比分配，每份 = 总量/总份数",
      "比例变化：原始比a:b，变化后a':b'，用比例统一法求解"],
     ["正反比判断：固定一个量，看另外两个量的关系",
      "份数法：把比例看成份数，用份数的增减来分析变化",
      "比例统一：多个比例中找公共量，统一份数后合并",
      "代入验证：用比例关系代入原题验证是否正确"],
     ["正反比判断错误：把正比当成反比或 vice versa",
      "连比没有统一公共量，直接把两个比例的数字拼在一起",
      "比例变化时忘记考虑基数的变化"],
     "比例倍数是很多题型的基础工具，必须熟练。建议先掌握正反比和份数法，再练习综合应用。"),

    ("kp_xingce_quantity_math_operation_planning", "统筹规划问题",
     "统筹规划问题考查优化思维，在约束条件下找最优方案，常见类型有时间安排、顺序优化、资源分配。",
     ["时间安排：多项任务如何安排顺序使总时间最短，常涉及等待时间",
      "顺序优化：确定最优执行顺序，如打水问题让等待时间最短",
      "资源分配：有限资源如何分配使效益最大",
      "路线规划：最短路径、最少中转等优化问题",
      "排队等待：多窗口排队，使总等待时间最短"],
     ["枚举法：选项有限时逐一列举比较，找最优方案",
      "贪心法：每步都选当前最优选项，适合局部最优即全局最优的情况",
      "排序法：按某个关键指标排序后依次安排",
      "代入验证法：将选项代入条件逐一验证"],
     ["贪心法不总是最优：局部最优不一定全局最优",
      '忽略约束条件：如"每人至少完成一项"等限制',
      "枚举不完整：遗漏某些可行方案"],
     "统筹规划题型灵活，没有固定公式。建议多做真题积累经验，重点练习时间安排和顺序优化。"),

    ("kp_xingce_quantity_math_operation_geometry", "几何问题",
     "几何问题是数量关系的常考模块，包括平面几何和立体几何，核心是掌握常见图形的周长、面积、体积公式。",
     ["平面图形面积：三角形S=½ah，矩形S=ab，圆S=πr²，梯形S=½(a+b)h",
      "立体几何体积：长方体V=abh，球体V=4/3πr³，圆柱V=πr²h，圆锥V=1/3πr²h",
      "相似比与面积比：相似比k，则面积比k²，体积比k³",
      "最短路径问题：两点之间线段最短，涉及对称变换",
      "几何计数：数图形个数，注意分类有序不重不漏"],
     ["公式法：直接套用周长、面积、体积公式",
      "割补法：不规则图形分割或补成规则图形再计算",
      "相似比法：利用相似三角形的边长比、面积比关系",
      "对称法：最短路径问题用对称变换转化为直线距离"],
     ["公式记错：如圆锥体积忘记乘1/3",
      "相似比用错：面积比是相似比的平方，不是一次方",
      "单位不统一：题目给的单位和公式要求的单位不一致"],
     "几何题需要熟记公式，建议整理一张公式卡片随身带。重点练习面积计算和最短路径问题。"),

    ("kp_xingce_quantity_math_operation_equation", "方程与不定方程",
     "方程是数量关系最基础的解题工具，大部分题都可以用方程来解。不定方程是公考特色题型，需要结合整除和奇偶性分析。",
     ["一元一次方程：ax+b=0，x=-b/a，适用于单一未知量",
      "二元一次方程组：两个方程两个未知量，消元法或代入法求解",
      "不定方程：方程数少于未知量数，如ax+by=c，需要正整数解",
      "不定方程解法：利用整除性缩小范围，再用奇偶性排除，最后试值",
      "不定方程组：先消元化为一个不定方程，再按不定方程方法求解"],
     ["设未知量列方程：选择合适的未知量，使方程尽量简单",
      "消元法解方程组：加减消元或代入消元",
      "整除分析法解不定方程：看系数的整除关系缩小解的范围",
      "奇偶分析法：利用奇偶性排除不可能的解"],
     ["不定方程直接试值不考虑整除性，效率低且容易遗漏",
      "设未知量不当导致方程复杂，如该设份数却设了具体数值",
      "忽略未知量的正整数约束"],
     "方程是万能工具，但不定方程需要特殊技巧。建议先练熟标准方程，再重点突破不定方程的整除和奇偶分析。"),

    ("kp_xingce_quantity_math_operation_probability", "概率问题",
     "概率问题考查事件发生的可能性大小，核心是古典概型和分类计数，对立事件和独立重复试验是常考类型。",
     ["古典概型：P(A) = A包含的基本事件数 / 总基本事件数，要求等可能",
      '对立事件：P(A) = 1 - P(非A)，"至少一个"类问题常用对立事件',
      "互斥事件加法：P(A或B) = P(A) + P(B)，A和B不能同时发生",
      "独立事件乘法：P(A且B) = P(A) × P(B)，A和B互不影响",
      "独立重复试验：n次试验中恰好发生k次的概率 = C(n,k) × p^k × (1-p)^(n-k)"],
     ["古典概型：先确定总事件数和目标事件数，注意等可能条件",
      '对立事件法：看到"至少"就用对立事件，1减去全不发生的概率',
      "分类计数法：用排列组合计算满足条件的方法数",
      "独立重复试验：直接套用伯努利公式"],
     ["古典概型不满足等可能条件就乱用公式",
      "互斥和独立搞混：互斥是不能同时发生，独立是互不影响",
      '"至少"问题不用对立事件，直接算导致分类遗漏'],
     "概率题与排列组合紧密相关，建议先掌握排列组合再学概率。重点练习对立事件和独立重复试验。"),

    ("kp_xingce_quantity_math_operation_calendar", "星期日期问题",
     "星期日期问题围绕闰年平年和星期推算展开，核心是掌握闰年判定规则和星期的周期性。",
     ["闰年判定：能被4整除且不能被100整除，或能被400整除",
      "闰年366天（2月29天），平年365天（2月28天）",
      "星期周期：每7天一个循环，365÷7=52余1，平年星期+1；366÷7=52余2，闰年星期+2",
      "月份天数：1/3/5/7/8/10/12月31天，4/6/9/11月30天，2月28或29天",
      "日期范围统计：某月有几个星期几的问题，用整除和余数分析"],
     ["闰年判定法：先看能否被400整除，再看能否被4整除但不能被100整除",
      "星期推算法：计算两个日期之间相差的天数，除以7看余数",
      "周期分析法：找出循环周期，用总天数除以周期取余",
      "列表法：把月份天数列出来逐月推算"],
     ["忘记整百年要能被400整除才是闰年（如1900年不是闰年）",
      "跨月推算时月份天数算错",
      "星期推算时余数方向搞反（加还是减）"],
     "星期日期问题难度不高但容易粗心。建议练习闰年判定和跨月星期推算两类题型。"),

    ("kp_xingce_quantity_math_operation_remainder_divisibility", "余数与整除",
     "余数与整除是数量关系的基础工具，整除判定规则和同余思想在很多题型中都有应用。",
     ["整除判定：能被2整除看末位，被3整除看各位数字之和，被4整除看末两位，被8整除看末三位",
      "能被9整除看各位数字之和，被11整除看奇数位与偶数位之差",
      "同余思想：a和b除以m余数相同，则(a-b)能被m整除",
      "奇偶性：奇数±奇数=偶数，偶数±偶数=偶数，奇数±偶数=奇数",
      "余数性质：被除数 = 除数 × 商 + 余数，余数 < 除数"],
     ["整除判定法：根据数字特征快速判断能否被某数整除",
      "同余法：多个数除以同一个数余数相同，利用差值的整除性",
      "奇偶分析法：利用奇偶性排除不可能的选项",
      "代入验证法：将选项代入条件验证是否满足整除或余数关系"],
     ["整除判定规则记错，如被3整除和被9整除的规则搞混",
      "同余思想用错：应该是(a-b)能被m整除，不是(a+b)",
      "忽略余数必须小于除数的约束"],
     "余数整除是基础工具题，单独出题不多但广泛应用。建议熟记整除判定规则和同余思想。"),
]

def make_json(title, conclusion, knowledge_points, methods, mistakes, practice):
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
            for p in knowledge_points
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

generated = 0
for code, title, conclusion, knowledge_points, methods, mistakes, practice in l5_math:
    slug = "kp-xc-" + code.replace("kp_xingce_", "").replace("_", "-")
    summary = f"数量关系-数学运算-{title}的核心知识点和解题方法。"
    tags = json.dumps(["数量关系", "数学运算", title], ensure_ascii=False)
    json_content = make_json(title, conclusion, knowledge_points, methods, mistakes, practice)

    sql = f"""WITH category_node AS (
    SELECT id FROM sys_category WHERE app_code = 'youanshang' AND type = 'knowledge_point' AND code = '{code}'
)
INSERT INTO sys_content (app_code, title, slug, content_json, content_html, summary, category_id, tags, is_pinned, is_public, is_published, publish_time, view_count, sort_order, extra, created_by, created_time)
SELECT 'gongkao', '{title}', '{slug}', CAST($${json_content}$$ AS jsonb), NULL, '{summary}', category_node.id, CAST('{tags}' AS jsonb), FALSE, TRUE, TRUE, NOW(), 0, 0, CAST('{{"content_type": "knowledge_point", "category_code": "{code}", "source": "fba_content_engine"}}' AS jsonb), 1, NOW()
FROM category_node ON CONFLICT (slug) DO UPDATE SET title = EXCLUDED.title, content_json = EXCLUDED.content_json, summary = EXCLUDED.summary, category_id = EXCLUDED.category_id, tags = EXCLUDED.tags, extra = EXCLUDED.extra, updated_time = NOW();
"""
    filename = f"kp_xc_{code.replace('kp_xingce_', '')}.sql"
    filepath = os.path.join(sql_dir, filename)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(sql)
    generated += 1
    print(f"[{generated}] {title}")

print(f"\nDone: {generated} files")
