"""
逐题拆解国考言语理解真题。
从 markdown 文件中读取所有题目，自动分析每道题的字数、题型、结构、选项设计。
"""

from __future__ import annotations

import re
from pathlib import Path

INPUT_FILE = Path(__file__).parent.parent / "output" / "gk_yuyan_2019_2026.md"
OUTPUT_FILE = Path(__file__).parent.parent / "output" / "真题逐题拆解.md"


def parse_questions(text: str) -> list[dict]:
    """从 markdown 文本中解析所有题目。"""
    questions = []
    # 按 --- 分割题目
    blocks = re.split(r'\n---\n', text)

    current_year = None
    current_paper = None

    for block in blocks:
        # 检测年份标题
        year_match = re.search(r'^## (\d{4}) 年', block, re.MULTILINE)
        if year_match:
            current_year = int(year_match.group(1))

        # 检测试卷标题
        paper_match = re.search(r'^### (.+)$', block, re.MULTILINE)
        if paper_match:
            current_paper = paper_match.group(1).strip()

        # 检测题目
        q_match = re.search(
            r'\*\*(\d+)\.\*\*\s*(.*?)(?=\n\n- [A-D]\.|$)',
            block, re.DOTALL
        )
        if not q_match:
            continue

        q_num = q_match.group(1)
        q_body = q_match.group(2).strip()

        # 提取选项
        options = re.findall(r'- ([A-D])\.\s*(.+?)(?=\n\n- [A-D]\.|\n\n\*\*答案|$)',
                           block, re.DOTALL)

        # 提取答案
        answer_match = re.search(r'\*\*答案：([A-D])\*\*', block)
        answer = answer_match.group(1) if answer_match else None

        if not answer:
            continue

        # 分离题干和提问
        stem = q_body
        question = ""

        # 提取提问句
        q_patterns = [
            r'(这段文字意在说明[：:]?\s*)',
            r'(这段文字主要介绍[：:]?\s*)',
            r'(这段文字主要说明[：:]?\s*)',
            r'(这段文字主要解释了[：:]?\s*)',
            r'(这段文字主要谈论[：:]?\s*)',
            r'(这段文字主要讲的是[：:]?\s*)',
            r'(这段文字所描述的.*?可以概括为[：:]?\s*)',
            r'(最适合做这段文字标题的是[：:]?\s*)',
            r'(这段文字接下来最可能介绍[：:]?\s*)',
            r'(这段文字接下来最可能讲的是[：:]?\s*)',
            r'(根据这段文字，下列说法正确的是[：:]?\s*)',
            r'(下列说法与这段文字.*?相符的是[：:]?\s*)',
            r'(这段文字没有提及[：:]?\s*)',
            r'(这段文字没有提到.*?[：:]?\s*)',
            r'(这段文字未对哪.*?做出解释[：:]?\s*)',
            r'(这段文字无法解释下列哪.*?[？?]\s*)',
            r'(这段文字认为.*?应该[：:]?\s*)',
            r'(这段文字意在强调[：:]?\s*)',
            r'(这段文字针对的主要问题是[：:]?\s*)',
            r'(这段文字讨论的问题是[：:]?\s*)',
            r'(这段文字是一篇文章的开头，最适合做文章标题的是[：:]?\s*)',
            r'(作者引用古代诗文，是为了说明[：:]?\s*)',
            r'(作者通过这段文字想说的是[：:]?\s*)',
            r'(这段文字强调要[：:]?\s*)',
            r'(这段文字主要批评了.*?[：:]?\s*)',
            r'(这段文字主要介绍了定向能武器[：:]?\s*)',
            r'(对这段文字理解准确的是[：:]?\s*)',
            r'(填入画横线部分最恰当的.*?是[：:]?\s*)',
            r'(依次填入画横线部分最恰当的.*?是[：;]?\s*)',
            r'(依次填入横线处的词语最恰当的.*?是[：:]?\s*)',
            r'(填入横线处的词语最恰当的.*?是[：:]?\s*)',
            r'(填入画横线部分最恰当的一句是[：:]?\s*)',
            r'(填入画横线部分最恰当的一项是[：:]?\s*)',
            r'(将以上\d+个句子重新排列.*?是[：:]?\s*)',
            r'("[^"]*"策略)指的是',
            r'(根据这段文字，下列说法正确的是[：:]?\s*)',
            r'(根据这段文字可知[，,]\s*)',
            r'(根据这段文字，高秆水稻种植[：:]?\s*)',
            r'(关于.*?文中没有提及[：:]?\s*)',
            r'(关于.*?下列说法与文章相符的是[：:]?\s*)',
            r'(文中没有提及下列哪.*?[？?]\s*)',
            r'(下列说法与这篇文章相符的是[：:]?\s*)',
            r'(这篇文章支持下列哪.*?[？?]\s*)',
            r'(关于.*?下列说法正确的是[：:]?\s*)',
            r'(下面这段文字，最适合填入文中哪个位置[？?]\s*)',
            r'(最适合做这篇文章标题的是[：:]?\s*)',
        ]

        for pattern in q_patterns:
            m = re.search(pattern, stem)
            if m:
                question = m.group(1).strip()
                stem = stem[:m.start()].strip()
                break

        # 计算纯文本字数（去除HTML标签）
        stem_text = re.sub(r'<[^>]+>', '', stem)
        char_count = len(re.sub(r'\s+', '', stem_text))

        # 判断题型
        q_type = classify_question_type(question, q_body, options)

        # 判断结构
        structure = analyze_structure(stem_text)

        # 分析选项
        option_analysis = analyze_options(options, answer, stem_text)

        questions.append({
            'num': q_num,
            'year': current_year,
            'paper': current_paper,
            'stem': stem_text,
            'char_count': char_count,
            'question': question,
            'type': q_type,
            'structure': structure,
            'options': options,
            'answer': answer,
            'option_analysis': option_analysis,
        })

    return questions


def classify_question_type(question: str, body: str, options: list) -> str:
    """判断题型。"""
    if '填入画横线' in question or '填入横线' in question or '依次填入' in question:
        if '一句' in question:
            return '语句填空'
        # 检查是单空还是多空
        blank_count = body.count('________')
        if blank_count >= 2:
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
    if '没有提及' in question or '没有提到' in question or '无法解释' in question or '未对哪' in question:
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


def analyze_structure(stem: str) -> str:
    """分析素材的逻辑结构。"""
    markers = []

    if re.search(r'然而|但是|但|不过|却', stem):
        markers.append('转折')
    if re.search(r'因此|所以|由此可见|故', stem):
        markers.append('因果')
    if re.search(r'不仅.*?而且|不仅.*?更|不仅.*?还', stem):
        markers.append('递进')
    if re.search(r'一方面.*?另一方面', stem):
        markers.append('并列')
    if re.search(r'首先.*?其次|第一.*?第二', stem):
        markers.append('枚举')
    if re.search(r'相比|相较于|与此不同', stem):
        markers.append('对比')
    if re.search(r'例如|比如|以.*?为例', stem):
        markers.append('举例')
    if re.search(r'虽然.*?但|尽管.*?但|固然.*?但', stem):
        markers.append('让步转折')
    if re.search(r'随着', stem):
        markers.append('背景引入')
    if re.search(r'客观来说|诚然', stem):
        markers.append('让步')

    if not markers:
        # 检查是否有因果链（无明确标记词）
        if re.search(r'由于|因为', stem):
            markers.append('因果链')
        else:
            markers.append('顺承')

    return '+'.join(markers)


def analyze_options(options: list, answer: str, stem: str) -> list[dict]:
    """分析每个选项的设计思路。"""
    analysis = []

    for code, text in options:
        text = text.strip()
        is_correct = (code == answer)

        if is_correct:
            reason = "正确选项"
            pattern = "核心论点改写"
        else:
            # 分析错误原因
            pattern, reason = analyze_distractor(text, stem, answer)

        analysis.append({
            'code': code,
            'text': text,
            'is_correct': is_correct,
            'pattern': pattern,
            'reason': reason,
        })

    return analysis


def analyze_distractor(option_text: str, stem: str, correct_code: str) -> tuple[str, str]:
    """分析干扰项的设计套路。"""
    option_clean = re.sub(r'<[^>]+>', '', option_text).strip()
    stem_clean = re.sub(r'<[^>]+>', '', stem).strip()

    # 检查是否无中生有（选项关键词在原文中不存在）
    key_words = re.findall(r'[一-鿿]{2,4}', option_clean)
    found_count = sum(1 for w in key_words if w in stem_clean)
    if found_count < len(key_words) * 0.3:
        return '无中生有', '选项内容在原文中找不到对应'

    # 检查是否偷换范围（绝对化词语）
    if re.search(r'所有|全部|任何|一定|完全|均|都', option_clean):
        return '偷换范围', '使用绝对化词语，扩大了原文范围'

    # 检查是否偷换时态
    if re.search(r'已经|已完成|已实现|已成为', option_clean) and not re.search(r'已经|已完成|已实现|已成为', stem_clean):
        return '偷换时态', '将未发生的事说成已发生'

    # 检查是否细节干扰（选项是原文的细节而非核心）
    if found_count >= len(key_words) * 0.5:
        return '细节干扰', '选项内容在原文中存在，但不是核心论点'

    return '待人工判断', '需要人工分析具体错因'


def format_question(q: dict, idx: int) -> str:
    """格式化单道题目的拆解分析。"""
    lines = []

    lines.append(f"## Q{idx} (年份:{q['year']} 第{q['num']}题)")
    lines.append("")
    lines.append(f"**字数：** {q['char_count']}字")
    lines.append(f"**题型：** {q['type']}")
    lines.append(f"**结构：** {q['structure']}")
    lines.append("")

    # 素材（截取前200字）
    stem_preview = q['stem'][:200]
    if len(q['stem']) > 200:
        stem_preview += '...'
    lines.append(f"**素材：** {stem_preview}")
    lines.append("")

    # 提问
    if q['question']:
        lines.append(f"**提问：** {q['question']}")
        lines.append("")

    # 正确选项
    lines.append(f"**正确选项：** {q['answer']}")
    lines.append("")

    # 选项分析
    lines.append("**选项分析：**")
    lines.append("")
    for opt in q['option_analysis']:
        marker = "✅" if opt['is_correct'] else "❌"
        lines.append(f"- {opt['code']}. {opt['text'][:60]}{'...' if len(opt['text']) > 60 else ''}")
        if not opt['is_correct']:
            lines.append(f"  {marker} 套路：{opt['pattern']} | {opt['reason']}")
        else:
            lines.append(f"  {marker} {opt['reason']}")

    lines.append("")
    lines.append("---")
    lines.append("")

    return '\n'.join(lines)


def build_output(questions: list[dict]) -> str:
    """生成完整的拆解文档。"""
    lines = []

    lines.append("# 国考言语理解真题逐题拆解")
    lines.append("")
    lines.append(f"> 总题数：{len(questions)} 道")
    lines.append(f"> 自动生成，基于 2019-2026 年真题")
    lines.append("")
    lines.append("---")
    lines.append("")

    # 统计概览
    lines.append("## 统计概览")
    lines.append("")
    lines.append("### 题型分布")
    lines.append("")
    type_counts = {}
    for q in questions:
        t = q['type']
        type_counts[t] = type_counts.get(t, 0) + 1
    lines.append("| 题型 | 题量 | 占比 |")
    lines.append("|------|------|------|")
    for t, c in sorted(type_counts.items(), key=lambda x: -x[1]):
        pct = round(c / len(questions) * 100, 1)
        lines.append(f"| {t} | {c} | {pct}% |")
    lines.append("")

    lines.append("### 结构分布")
    lines.append("")
    struct_counts = {}
    for q in questions:
        s = q['structure']
        struct_counts[s] = struct_counts.get(s, 0) + 1
    lines.append("| 结构 | 题量 | 占比 |")
    lines.append("|------|------|------|")
    for s, c in sorted(struct_counts.items(), key=lambda x: -x[1])[:15]:
        pct = round(c / len(questions) * 100, 1)
        lines.append(f"| {s} | {c} | {pct}% |")
    lines.append("")

    lines.append("### 字数分布")
    lines.append("")
    chars = [q['char_count'] for q in questions if q['char_count'] > 50]
    if chars:
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
        lines.append(format_question(q, idx))

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
