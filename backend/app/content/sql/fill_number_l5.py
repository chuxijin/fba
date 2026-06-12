#!/usr/bin/env python3
"""Fill real content for 数量关系 L5 数字推理 overviews"""
import json, os

sql_dir = "D:/100_Work/101_Program/Proj/fba/backend/app/content/sql"

l5_number = [
    ("kp_xingce_quantity_number_reasoning_arithmetic", "等差数列",
     "等差数列是最基础的数列类型，相邻两项之差为常数d，公考中常考等差数列的变形和应用。",
     ["通项公式：an = a1 + (n-1)d，其中d为公差",
      "等差中项：若a,b,c成等差数列，则b = (a+c)/2，即中间项等于两边的平均值",
      "前n项和：Sn = n(a1+an)/2 = na1 + n(n-1)d/2",
      "性质：若m+n = p+q，则am+an = ap+aq",
      "变形：二级等差（相邻项的差成等差）、三级等差"],
     ["看相邻两项的差是否相等，判断是否为等差数列",
      "差值不等时，再对差值做差（二级差），看是否为等差",
      "利用等差中项验证：中间项是否等于两边的平均值",
      "从选项反推：代入选项验证是否满足等差关系"],
     ["只看一级差就下结论，忽略二级差的可能性",
      "把等差数列和等比数列搞混",
      "忽略负公差的情况（递减等差数列）"],
     "等差数列是数字推理的基础，必须首先掌握。建议先练一级差，再练二级差变形。"),

    ("kp_xingce_quantity_number_reasoning_geometric", "等比数列",
     "等比数列相邻两项之比为常数q，公比q不等于0，在公考中常与等差数列结合出题。",
     ["通项公式：an = a1 × q^(n-1)，其中q为公比",
      "等比中项：若a,b,c成等比数列，则b² = ac",
      "前n项和：Sn = a1(1-q^n)/(1-q)，当q≠1时",
      "性质：若m+n = p+q，则am×an = ap×aq",
      "变形：公比为分数、负数、交替变化等"],
     ["看相邻两项的比是否相等，判断是否为等比数列",
      "比值不固定时，看是否为变比数列（公比有规律变化）",
      "利用等比中项验证：中间项的平方是否等于两边的乘积",
      "注意公比为负数或分数的情况"],
     ["忽略公比为1的特殊情况（常数列）",
      "公比为负数时符号规律判断错误",
      "把等比数列的增长速度误判为等差"],
     "等比数列增长速度快，看到数字快速增大时优先考虑。重点练习公比为负数和分数的情况。"),

    ("kp_xingce_quantity_number_reasoning_power", "幂次数列",
     "幂次数列以平方数、立方数、2的幂次等为基础进行变形，是数字推理的高频考点。",
     ["常见平方数：1,4,9,16,25,36,49,64,81,100,121,144,169,196,225",
      "常见立方数：1,8,27,64,125,216,343,512,729,1000",
      "常见2的幂次：1,2,4,8,16,32,64,128,256,512,1024",
      "变形方式：底数有规律（如1,4,9,16,...）、指数有规律（如2^1,3^2,4^3,...）",
      "幂次±常数：如2,5,10,17,26,... = 1²+1, 2²+1, 3²+1, ..."],
     ["看到接近平方数或立方数的数字，尝试加减一个小常数",
      "列出常见幂次数表，快速比对",
      "底数和指数分别找规律",
      "特殊数字敏感：如125=5³, 64=8²=4³=2⁶"],
     ["平方数和立方数记错",
      "忽略幂次±常数的变形",
      "底数和指数的规律搞混"],
     "建议背熟20以内的平方数和10以内的立方数，这是做幂次数列的基础。"),

    ("kp_xingce_quantity_number_reasoning_recurrence", "递推数列",
     "递推数列的后项由前项通过某种运算得到，如an+1 = 2an + 1，是数字推理中变化最多的类型。",
     ["常见递推关系：an+1 = k×an + b（线性递推）",
      "an+1 = an + an-1（斐波那契型）",
      "an+1 = an × an-1（乘积递推）",
      "an+1 = an²（平方递推）",
      "递推关系可能涉及前两项、前三项甚至更多项"],
     ["尝试后项减前项、后项除前项，看是否有简单关系",
      "尝试后项与前两项的关系：如后项=前项×2+1",
      "尝试平方关系：后项是否等于前项的平方±常数",
      "从简单关系开始尝试，逐步增加复杂度"],
     ["只考虑相邻两项的关系，忽略可能涉及三项",
      "递推关系判断错误，如把加法关系看成乘法",
      "忽略递推关系中的常数项"],
     "递推数列题型灵活，没有固定套路。建议从简单的线性递推开始练习，逐步增加难度。"),

    ("kp_xingce_quantity_number_reasoning_grouping", "分组数列",
     "分组数列将原数列分成奇数项和偶数项两组，各自独立成规律，是数字推理的常见类型。",
     ["基本特征：奇数位置的数和偶数位置的数分别成规律",
      "分组方式：通常是奇偶分组（第1,3,5,...项和第2,4,6,...项）",
      "每组可以是等差、等比、平方等任意规律",
      "两组的规律可以相同也可以不同",
      "变体：三项一组（第1,4,7,...项、第2,5,8,...项、第3,6,9,...项）"],
     ["先尝试奇偶分组，分别列出奇数项和偶数项",
      "看每组内部是否有简单规律（等差、等比等）",
      "奇偶分组不行时，尝试三项分组或其他分组方式",
      "分组后每组的规律可能不同，要分别分析"],
     ["只尝试一种分组方式就放弃",
      "分组后只看一组的规律，忽略验证另一组",
      "把分组数列当成普通等差等比来处理"],
     '分组数列的关键是"分开看"。看到数列没有明显规律时，优先尝试奇偶分组。'),

    ("kp_xingce_quantity_number_reasoning_cross", "交叉数列",
     "交叉数列由两个独立数列交叉排列而成，如a1,b1,a2,b2,a3,b3,...，需要拆分后分别找规律。",
     ["基本特征：数列由两个子数列交替排列",
      '与分组数列的区别：交叉数列强调"两个数列交叉"，分组数列强调"分组后各自成规律"',
      "拆分方式：奇数位置一个数列，偶数位置另一个数列",
      "每个子数列可以是任意类型的规律",
      "变体：三个数列交叉排列"],
     ["将奇数位和偶数位的数分别提取出来",
      "对每个子数列独立分析规律",
      "注意交叉数列和分组数列本质相同，只是分析角度不同",
      "验证时要同时满足两个子数列的规律"],
     ["与分组数列混淆，分析方法其实相同",
      "拆分时漏掉某一项或多出一项",
      "只验证了一个子数列就下结论"],
     "交叉数列和分组数列本质相同，掌握一种即可。关键是拆分后独立分析每个子数列。"),

    ("kp_xingce_quantity_number_reasoning_combination", "组合数列",
     "组合数列由多个简单数列通过加减乘除等运算组合而成，需要拆解组合关系。",
     ["基本特征：每一项由两个或多个简单数列的对应项运算得到",
      "常见组合方式：等差+等比、等差+平方、两个等差相加等",
      "拆解方法：尝试将每一项分解为两个简单数列的和/差/积",
      "如2,5,10,17,26,... = 1+1, 4+1, 9+1, 16+1, 25+1（平方数+1）",
      "变体：一个数列的项作为另一个数列的参数"],
     ["尝试将每一项分解为两个简单部分",
      "常见分解：奇数+偶数、平方+常数、等差+等比",
      "从简单组合开始尝试，如+1、-1、×2",
      "观察数列的整体趋势，判断可能的组合类型"],
     ["分解方式太多无从下手时，优先尝试常见的组合",
      "忽略组合中的常数项",
      "分解后只验证一部分，没有完整验证"],
     "组合数列需要一定的数感。建议多做题积累经验，熟悉常见的组合模式。"),

    ("kp_xingce_quantity_number_reasoning_multi_level", "多级数列",
     "多级数列通过多次做差或做比来寻找规律，是数字推理中最系统化的解题方法。",
     ["基本方法：相邻项做差得到新数列，对新数列继续做差，直到发现规律",
      "二级差数列：原数列的差值成等差，即原数列为二级等差",
      "三级差数列：需要做三次差才能得到常数列",
      "做差法：适合增长平缓的数列",
      "做比法：适合增长较快的数列，相邻项做比"],
     ["第一步：相邻项做差，看差值是否有规律",
      "差值没规律时，对差值继续做差（二级差）",
      "增长很快的数列优先尝试做比法",
      "做差/做比后得到的新数列可能是等差、等比或其他类型"],
     ["做差时顺序搞反（应该是后项减前项）",
      "只做一次差就放弃，没有尝试二级差",
      "该用做比法的数列却用做差法"],
     '多级数列是最通用的方法，几乎所有数列都可以先尝试做差。建议养成"先做差"的习惯。'),

    ("kp_xingce_quantity_number_reasoning_fraction", "分数数列",
     "分数数列以分数形式呈现，需要分别观察分子和分母的规律，有时需要反约分。",
     ["基本思路：分子和分母分别找规律",
      "反约分：将分数化为非最简形式，使分子分母的规律更明显",
      "如1/2, 2/3, 3/4, 4/5,... 分子分母各自是等差数列",
      "交叉规律：分子的规律可能与分母相关",
      "整体规律：分数本身可能是等差或等比"],
     ["先分别列出分子和分母，各自找规律",
      "规律不明显时尝试反约分（同乘一个数）",
      "看分子分母之间是否有关系（如分子=分母-1）",
      "将分数化为小数后看是否有简单规律"],
     ["忘记反约分这一步",
      "只看分子或只看分母，忽略另一个",
      "约分后打乱了原有的分子分母规律"],
     '分数数列的核心是"分开看分子分母"。规律不明显时一定要尝试反约分。'),

    ("kp_xingce_quantity_number_reasoning_decimal", "小数数列",
     "小数数列需要将整数部分和小数部分分开观察，各自找规律。",
     ["基本思路：整数部分和小数部分分别找规律",
      "如1.1, 2.2, 3.3, 4.4,... 整数部分等差，小数部分也等差",
      "变体：整数部分和小数部分的规律不同",
      "小数位数可能有变化（如1.1, 2.01, 3.001,...）",
      "可能需要将小数部分看作独立的整数"],
     ["将整数部分和小数部分分别提取出来",
      "各自独立分析规律",
      "注意小数位数的变化",
      "如果分开看没规律，尝试整体看（如化为分数）"],
     ["忽略小数位数的变化",
      "把小数部分和整数部分混在一起分析",
      "小数部分的前导零被忽略"],
     '小数数列和分数数列类似，核心是"拆分"。分开看整数部分和小数部分各自的规律。'),

    ("kp_xingce_quantity_number_reasoning_digit_feature", "数位特征数列",
     "数位特征数列通过各位数字的运算（和、积等）来找规律，需要关注数字本身的结构。",
     ["常见规律：各位数字之和成规律",
      "各位数字之积成规律",
      "十位数和个位数分别成规律",
      "数字反转后成规律（如12, 21, 23, 32,...）",
      "数字的某种排列组合成规律"],
     ["先算各位数字之和，看是否成规律",
      "各位数字之和没规律时，尝试各位数字之积",
      "尝试将数字拆分为十位和个位分别分析",
      "尝试数字反转或重新排列"],
     ["只尝试一种数位运算就放弃",
      "多位数的数位拆分出错",
      "忽略数字本身的大小规律（可能是等差等比）"],
     "数位特征题需要对数字敏感。建议练习时多算几位数的和与积，培养数感。"),

    ("kp_xingce_quantity_number_reasoning_periodic", "周期循环数列",
     "周期循环数列的规律呈周期性重复，如a,b,c,a,b,c,...，需要找到循环节。",
     ["基本特征：数列中某一段规律不断重复",
      "循环节：重复出现的最短子序列",
      "如1,2,3,1,2,3,1,2,3,... 循环节为(1,2,3)",
      "变体：循环节长度不固定，但有递增趋势",
      "可能与分组数列结合"],
     ["观察是否有重复出现的子序列",
      "尝试不同的循环节长度（2,3,4,...）",
      "验证：用循环节长度整除项数，看余数对应的位置",
      "注意循环节可能是递增的（如1,2,3,2,3,4,3,4,5,...）"],
     ["循环节长度判断错误",
      "把非周期数列误判为周期数列",
      "忽略循环节中的递增变化"],
     "周期循环数列相对少见，但特征明显。看到重复出现的数字组合时优先考虑。"),

    ("kp_xingce_quantity_number_reasoning_special_pattern", "特殊规律数列",
     "特殊规律数列不遵循常见的等差、等比、幂次等模式，需要灵活分析和创造性思维。",
     ["常见特殊规律：质数数列（2,3,5,7,11,13,...）",
      "合数数列（4,6,8,9,10,12,...）",
      "斐波那契数列（1,1,2,3,5,8,13,...）",
      "自然数的某种运算（如n²+n, 2n+1等）",
      "数列项与项数的关系（第n项=f(n)）"],
     ["尝试将数列与自然数对应，看第n项与n的关系",
      "检查是否为质数、合数等特殊数列",
      "尝试简单的多项式：如n², n²+1, 2n²+n等",
      "实在找不到规律时，从选项反推"],
     ["忽略质数、合数等基础数列",
      "没有尝试将数列与项数对应",
      "过早放弃，没有尝试足够多的可能性"],
     "特殊规律题考查数感和灵活性。建议熟记质数表和常见数列公式，遇到难题时从项数关系入手。"),
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
for code, title, conclusion, knowledge_points, methods, mistakes, practice in l5_number:
    slug = "kp-xc-" + code.replace("kp_xingce_", "").replace("_", "-")
    summary = f"数量关系-数字推理-{title}的核心知识点和解题方法。"
    tags = json.dumps(["数量关系", "数字推理", title], ensure_ascii=False)
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
