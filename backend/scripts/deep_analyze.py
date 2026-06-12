"""
逐题深度拆解国考言语理解真题。
按标准格式输出：字数、题型、结构、逐句拆解、论证逻辑、正确选项思路、错误选项思路。
"""

from __future__ import annotations

import re
from pathlib import Path

INPUT_FILE = Path(__file__).parent.parent / "output" / "gk_yuyan_2019_2026.md"
OUTPUT_FILE = Path(__file__).parent.parent / "output" / "真题逐题拆解.md"

# ── 逻辑标记词 ──
MARKERS = {
    '转折': r'然而|但是|但[^是]|不过|却|可是',
    '因果': r'因此|所以|由此可见|故[^事]|正因|因而',
    '递进': r'不仅[^是].*?[而且更还]|不但.*?而且|而且|更[^是]|甚至|乃至',
    '并列': r'一方面.*?另一方面|同时|与此同时|此外|另外',
    '对比': r'相比|相较于|与此不同|相反|而[^是]',
    '举例': r'例如|比如|以[^之].*?为例|正如',
    '让步': r'虽然|尽管|固然|诚然|客观来说|诚然',
    '枚举': r'首先.*?其次|第一.*?第二|首先|其次|最后',
    '背景': r'随着|近年来|当前|如今|目前',
    '定义': r'叫作|称为|指的是|就是|即',
}

ROLE_KEYWORDS = {
    '背景': r'^当前|^随着|^近年来|^如今|^目前|^[一-鿿]{2,6}是',
    '转折论点': r'^但[^是]|^然而|^不过|^可是',
    '因果结论': r'^因此|^所以|^由此可见|^故[^事]|^因而',
    '举例': r'^例如|^比如|^以[^之].*?为例',
    '递进': r'^不仅|^不但|^而且|^更[^是]|^甚至',
    '补充': r'^同时|^与此同时|^此外|^另外',
    '权威引用': r'习近平|总书记|指出|强调|曾[在说写]',
    '数据': r'\d+[%％]|\d+倍|\d+年|\d+万|\d+亿|\d+个',
    '定义': r'叫作|称为|指的是',
}


def strip_html(text: str) -> str:
    """去除HTML标签。"""
    text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'</p>\s*<p[^>]*>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'&nbsp;', ' ', text)
    text = re.sub(r'&amp;', '&', text)
    text = re.sub(r'&lt;', '<', text)
    text = re.sub(r'&gt;', '>', text)
    return text.strip()


def split_sentences(text: str) -> list[str]:
    """按句号、问号、感叹号拆分句子。"""
    text = re.sub(r'________+', '________', text)
    parts = re.split(r'(?<=[。！？；])\s*', text)
    sentences = []
    for p in parts:
        p = p.strip()
        if p and len(p) > 5:
            sentences.append(p)
    return sentences


def classify_question(question: str, stem: str, options: list) -> str:
    """判断题型。"""
    if '填入画横线' in question or '填入横线' in question or '依次填入' in question:
        if '一句' in question:
            return '语句填空'
        blanks = stem.count('________')
        if blanks >= 2:
            return '逻辑填空-多空'
        return '逻辑填空-单空'
    if '将以上' in question and '重新排列' in question:
        return '语句排序'
    if '接下来最可能' in question:
        return '下文推断'
    if '最适合做' in question and '标题' in question:
        return '标题选择'
    if '下列说法正确' in question or '与原文相符' in question or '与文章相符' in question:
        return '细节理解-正向'
    if '没有提及' in question or '没有提到' in question or '无法解释' in question or '未对哪' in question or '没有解释' in question:
        return '细节理解-反向'
    if '意在说明' in question or '意在强调' in question or '想说的是' in question:
        return '意图判断'
    if '主要介绍' in question or '主要说明' in question or '主要解释' in question or '主要谈论' in question or '主要讲' in question:
        return '主旨概括'
    if '概括为' in question:
        return '主旨概括'
    if '针对的主要问题' in question or '讨论的问题' in question:
        return '问题识别'
    if '认为' in question and '应该' in question:
        return '对策判断'
    if '理解准确' in question:
        return '细节理解-正向'
    if '策略' in question and '指的是' in question:
        return '词句理解'
    if '为了说明' in question:
        return '例证作用'
    if '强调要' in question:
        return '意图判断'
    if '批评了' in question:
        return '问题识别'
    if '支持下列' in question:
        return '细节理解-正向'
    if '填入文中哪个位置' in question:
        return '语句衔接'
    if '最恰当的一句' in question:
        return '语句填空'
    return '其他'


def detect_structure(stem: str) -> str:
    """检测素材的逻辑结构。"""
    found = []
    for name, pattern in MARKERS.items():
        if re.search(pattern, stem):
            found.append(name)
    if not found:
        if re.search(r'由于|因为', stem):
            found.append('因果链')
        else:
            found.append('顺承')
    return ' → '.join(found)


def detect_sentence_role(sentence: str) -> str:
    """检测单句的角色。"""
    for role, pattern in ROLE_KEYWORDS.items():
        if re.search(pattern, sentence):
            return role
    return '论述'


def detect_argument_logic(stem: str) -> str:
    """检测论证逻辑。"""
    sentences = split_sentences(stem)
    if len(sentences) <= 1:
        return '单句'

    roles = []
    for s in sentences:
        role = detect_sentence_role(s)
        roles.append(role)

    # 简化：只保留角色变化的节点
    simplified = [roles[0]]
    for r in roles[1:]:
        if r != simplified[-1]:
            simplified.append(r)

    return ' → '.join(simplified[:5])


def find_core_sentence(stem: str) -> str:
    """找到核心论点句。"""
    sentences = split_sentences(stem)

    # 优先找"因此/所以"后的句子
    for i, s in enumerate(sentences):
        if re.search(r'^因此|^所以|^由此可见', s):
            return s[:80]

    # 找转折后的句子
    for i, s in enumerate(sentences):
        if re.search(r'^但[^是]|^然而|^不过', s):
            return s[:80]

    # 找最后一句
    if sentences:
        return sentences[-1][:80]

    return ''


def analyze_correct_answer(option_text: str, stem: str, core: str) -> str:
    """分析正确选项的设计思路。"""
    opt = strip_html(option_text).strip()
    core_clean = strip_html(core).strip() if core else ''

    if not core_clean:
        return '核心论点改写'

    # 计算关键词重叠
    opt_words = set(re.findall(r'[一-鿿]{2,4}', opt))
    core_words = set(re.findall(r'[一-鿿]{2,4}', core_clean))
    overlap = len(opt_words & core_words)

    if overlap >= len(opt_words) * 0.6:
        return '同义替换（与核心论点高度重叠）'
    if overlap >= len(opt_words) * 0.3:
        return '概括提炼（提取核心论点的关键词重组）'
    return '视角转换（从不同角度改写核心论点）'


def analyze_distractor(option_text: str, stem: str, core: str, answer_text: str) -> tuple[str, str]:
    """分析干扰项的设计思路。"""
    opt = strip_html(option_text).strip()
    stem_clean = strip_html(stem).strip()
    core_clean = strip_html(core).strip() if core else ''
    ans_clean = strip_html(answer_text).strip()

    opt_words = set(re.findall(r'[一-鿿]{2,4}', opt))
    stem_words = set(re.findall(r'[一-鿿]{2,4}', stem_clean))
    core_words = set(re.findall(r'[一-鿿]{2,4}', core_clean))
    ans_words = set(re.findall(r'[一-鿿]{2,4}', ans_clean))

    # 1. 无中生有：选项关键词在原文中大部分不存在
    overlap_with_stem = len(opt_words & stem_words)
    if overlap_with_stem < len(opt_words) * 0.25:
        return '无中生有', '选项关键词在原文中找不到对应'

    # 2. 偷换范围：绝对化词语
    if re.search(r'所有|全部|任何|一定|完全|均[^衡]|都是|都能|都会', opt):
        return '偷换范围', '使用绝对化词语扩大了原文范围'

    # 3. 偷换时态
    if re.search(r'已经|已完成|已实现|已成为|均已', opt) and not re.search(r'已经|已完成|已实现|已成为|均已', stem_clean):
        return '偷换时态', '将原文的将来/可能说成已经/完成'

    # 4. 偷换否定
    if re.search(r'不再|未能|没有|并非', stem_clean) and not re.search(r'不再|未能|没有|并非', opt):
        if re.search(r'仍然|依然|仍|还', opt):
            return '偷换否定', '把原文的否定说成肯定'

    # 5. 非重点偷位：选项内容在原文中存在但不是核心
    overlap_with_core = len(opt_words & core_words)
    if overlap_with_core < len(opt_words) * 0.3 and overlap_with_stem >= len(opt_words) * 0.4:
        return '非重点偷位', '选项内容在原文中存在，但不是核心论点'

    # 6. 细节干扰
    overlap_with_ans = len(opt_words & ans_words)
    if overlap_with_ans < len(opt_words) * 0.3:
        return '细节干扰', '选项是原文的细节/论据，不是核心论点'

    # 7. 与正确选项接近
    if overlap_with_ans >= len(opt_words) * 0.3:
        return '偷换概念', '与正确选项语义相近但有微妙差异'

    return '待分析', '需要人工判断具体错因'


def build_question_analysis(q: dict, idx: int) -> str:
    """生成单道题的深度分析。"""
    lines = []

    lines.append(f"### Q{idx} ({q['year']}{q['paper_short']} 第{q['num']}题)")
    lines.append("")
    lines.append(f"**字数：** {q['char_count']}字")
    lines.append(f"**题型：** {q['type']}")
    lines.append(f"**结构：** {q['structure']}")
    lines.append("")

    # 逐句拆解
    sentences = split_sentences(q['stem'])
    if len(sentences) > 1:
        lines.append("**逐句拆解：**")
        lines.append("")
        lines.append("| # | 句子 | 角色 |")
        lines.append("|---|------|------|")
        for i, s in enumerate(sentences, 1):
            role = detect_sentence_role(s)
            s_short = s[:50] + ('...' if len(s) > 50 else '')
            lines.append(f"| S{i} | {s_short} | {role} |")
        lines.append("")

    # 论证逻辑
    logic = detect_argument_logic(q['stem'])
    lines.append(f"**论证逻辑：** {logic}")
    lines.append("")

    # 核心论点
    core = find_core_sentence(q['stem'])
    if core:
        lines.append(f"**核心论点：** {core}")
        lines.append("")

    # 正确选项
    correct_text = ''
    for opt in q['option_analysis']:
        if opt['is_correct']:
            correct_text = opt['text']
            break

    correct_reason = analyze_correct_answer(correct_text, q['stem'], core)
    lines.append(f"**正确选项 {q['answer']}：** {strip_html(correct_text)[:80]}")
    lines.append(f"- 设计思路：{correct_reason}")
    lines.append("")

    # 错误选项
    lines.append("**错误选项：**")
    lines.append("")
    for opt in q['option_analysis']:
        if opt['is_correct']:
            continue
        pattern, reason = analyze_distractor(opt['text'], q['stem'], core, correct_text)
        opt_short = strip_html(opt['text'])[:60]
        lines.append(f"- {opt['code']}. {opt_short}{'...' if len(strip_html(opt['text'])) > 60 else ''}")
        lines.append(f"  ❌ {pattern}：{reason}")
    lines.append("")
    lines.append("---")
    lines.append("")

    return '\n'.join(lines)


def parse_questions(text: str) -> list[dict]:
    """解析所有题目。"""
    questions = []
    blocks = re.split(r'\n---\n', text)

    current_year = None
    current_paper = None

    for block in blocks:
        year_match = re.search(r'^## (\d{4}) 年', block, re.MULTILINE)
        if year_match:
            current_year = int(year_match.group(1))

        paper_match = re.search(r'^### (.+)$', block, re.MULTILINE)
        if paper_match:
            current_paper = paper_match.group(1).strip()

        q_match = re.search(r'\*\*(\d+)\.\*\*\s*(.*?)(?=\n\n- [A-D]\.|$)', block, re.DOTALL)
        if not q_match:
            continue

        q_num = q_match.group(1)
        q_body = q_match.group(2).strip()

        options = re.findall(r'- ([A-D])\.\s*(.+?)(?=\n\n- [A-D]\.|\n\n\*\*答案|$)',
                           block, re.DOTALL)

        answer_match = re.search(r'\*\*答案：([A-D])\*\*', block)
        answer = answer_match.group(1) if answer_match else None

        if not answer:
            continue

        stem = q_body
        question = ""

        # 提取提问句
        q_patterns = [
            (r'(填入画横线部分最恰当的.*?是[：:]?\s*)', 'fill'),
            (r'(依次填入画横线部分最恰当的.*?是[：;]?\s*)', 'fill'),
            (r'(依次填入横线处的词语最恰当的.*?是[：:]?\s*)', 'fill'),
            (r'(填入横线处的词语最恰当的.*?是[：:]?\s*)', 'fill'),
            (r'(将以上\d+个句子重新排列.*?是[：:]?\s*)', 'sort'),
            (r'(这段文字意在说明[：:]?\s*)', 'main'),
            (r'(这段文字主要介绍[：:]?\s*)', 'main'),
            (r'(这段文字主要说明[：:]?\s*)', 'main'),
            (r'(这段文字主要解释了[：:]?\s*)', 'main'),
            (r'(这段文字主要谈论[：:]?\s*)', 'main'),
            (r'(这段文字主要讲的是[：:]?\s*)', 'main'),
            (r'(这段文字所描述的.*?可以概括为[：:]?\s*)', 'main'),
            (r'(最适合做这段文字标题的是[：:]?\s*)', 'title'),
            (r'(这段文字接下来最可能.*?[：:]?\s*)', 'next'),
            (r'(根据这段文字，下列说法正确的是[：:]?\s*)', 'detail'),
            (r'(下列说法与这段文字.*?相符的是[：:]?\s*)', 'detail'),
            (r'(这段文字没有提及[：:]?\s*)', 'detail_neg'),
            (r'(这段文字没有提到.*?[：:]?\s*)', 'detail_neg'),
            (r'(这段文字未对哪.*?做出解释[：:]?\s*)', 'detail_neg'),
            (r'(这段文字无法解释下列哪.*?[？?]\s*)', 'detail_neg'),
            (r'(文中没有提及下列哪.*?[？?]\s*)', 'detail_neg'),
            (r'(这段文字认为.*?应该[：:]?\s*)', 'opinion'),
            (r'(这段文字意在强调[：:]?\s*)', 'main'),
            (r'(这段文字针对的主要问题是[：:]?\s*)', 'problem'),
            (r'(这段文字讨论的问题是[：:]?\s*)', 'problem'),
            (r'(这段文字是一篇文章的开头.*?标题.*?是[：:]?\s*)', 'title'),
            (r'(作者引用.*?是为了说明[：:]?\s*)', 'purpose'),
            (r'(作者通过这段文字想说的是[：:]?\s*)', 'main'),
            (r'(这段文字强调要[：:]?\s*)', 'main'),
            (r'(这段文字主要批评了.*?[：:]?\s*)', 'problem'),
            (r'(这段文字主要介绍了定向能武器[：:]?\s*)', 'main'),
            (r'(对这段文字理解准确的是[：:]?\s*)', 'detail'),
            (r'("[^"]*"策略)指的是', 'word'),
            (r'(根据这段文字，下列说法正确的是[：:]?\s*)', 'detail'),
            (r'(根据这段文字可知[，,]\s*)', 'detail'),
            (r'(关于.*?下列说法正确的是[：:]?\s*)', 'detail'),
            (r'(下列说法与这篇文章相符的是[：:]?\s*)', 'detail'),
            (r'(这篇文章支持下列哪.*?[？?]\s*)', 'detail'),
            (r'(下面这段文字，最适合填入文中哪个位置[？?]\s*)', 'position'),
            (r'(最适合做这篇文章标题的是[：:]?\s*)', 'title'),
            (r'(填入画横线部分最恰当的一句是[：:]?\s*)', 'fill_sentence'),
            (r'(填入画横线部分最恰当的一项是[：:]?\s*)', 'fill'),
        ]

        for pattern, _ in q_patterns:
            m = re.search(pattern, stem)
            if m:
                question = m.group(1).strip()
                stem = stem[:m.start()].strip()
                break

        stem_text = strip_html(stem)
        char_count = len(re.sub(r'\s+', '', stem_text))

        q_type = classify_question(question, q_body, options)
        structure = detect_structure(stem_text)

        option_analysis = []
        for code, text in options:
            text_clean = strip_html(text).strip()
            is_correct = (code == answer)
            option_analysis.append({
                'code': code,
                'text': text_clean,
                'is_correct': is_correct,
            })

        paper_short = ''
        if current_paper:
            if '副省级' in current_paper:
                paper_short = '副省'
            elif '市地级' in current_paper:
                paper_short = '市地'
            elif '行政执法' in current_paper:
                paper_short = '执法'

        questions.append({
            'num': q_num,
            'year': current_year,
            'paper': current_paper,
            'paper_short': paper_short,
            'stem': stem_text,
            'char_count': char_count,
            'question': question,
            'type': q_type,
            'structure': structure,
            'option_analysis': option_analysis,
            'answer': answer,
        })

    return questions


def build_output(questions: list[dict]) -> str:
    """生成完整文档。"""
    lines = []

    lines.append("# 国考言语理解真题逐题拆解")
    lines.append("")
    lines.append(f"> 总题数：{len(questions)} 道")
    lines.append(f"> 基于 2019-2026 年真题")
    lines.append("")

    # 统计
    lines.append("---")
    lines.append("")
    lines.append("## 统计概览")
    lines.append("")

    type_counts = {}
    for q in questions:
        t = q['type']
        type_counts[t] = type_counts.get(t, 0) + 1
    lines.append("### 题型分布")
    lines.append("")
    lines.append("| 题型 | 题量 | 占比 |")
    lines.append("|------|------|------|")
    for t, c in sorted(type_counts.items(), key=lambda x: -x[1]):
        pct = round(c / len(questions) * 100, 1)
        lines.append(f"| {t} | {c} | {pct}% |")
    lines.append("")

    struct_counts = {}
    for q in questions:
        s = q['structure']
        struct_counts[s] = struct_counts.get(s, 0) + 1
    lines.append("### 结构分布")
    lines.append("")
    lines.append("| 结构 | 题量 | 占比 |")
    lines.append("|------|------|------|")
    for s, c in sorted(struct_counts.items(), key=lambda x: -x[1])[:15]:
        pct = round(c / len(questions) * 100, 1)
        lines.append(f"| {s} | {c} | {pct}% |")
    lines.append("")

    chars = [q['char_count'] for q in questions if q['char_count'] > 50]
    if chars:
        lines.append("### 字数分布")
        lines.append("")
        lines.append(f"- 最小：{min(chars)}字")
        lines.append(f"- 最大：{max(chars)}字")
        lines.append(f"- 中位数：{sorted(chars)[len(chars)//2]}字")
        lines.append(f"- 平均：{sum(chars)//len(chars)}字")
    lines.append("")
    lines.append("---")
    lines.append("")

    # 逐题拆解
    lines.append("## 逐题拆解")
    lines.append("")

    for idx, q in enumerate(questions, 1):
        lines.append(build_question_analysis(q, idx))

    return '\n'.join(lines)


def main() -> None:
    print(f"读取: {INPUT_FILE}")
    text = INPUT_FILE.read_text(encoding='utf-8')

    print("解析题目...")
    questions = parse_questions(text)
    print(f"解析到 {len(questions)} 道题目")

    print("生成拆解文档...")
    output = build_output(questions)

    OUTPUT_FILE.write_text(output, encoding='utf-8')
    print(f"已输出到: {OUTPUT_FILE}")


if __name__ == '__main__':
    main()
