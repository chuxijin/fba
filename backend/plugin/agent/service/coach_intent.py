from __future__ import annotations

import re

from typing import Any

MODULES = {
    'summary': ('归纳概括', '提炼要点、分类归纳和材料表达'),
    'analysis': ('综合分析', '观点、原因、影响和逻辑论证'),
    'countermeasure': ('提出对策', '问题识别、原因分析和措施可行性'),
    'document': ('公文写作', '身份、格式、内容要素和语言'),
    'essay': ('综合写作', '立意、结构、论证和材料转化'),
    'top_loss': ('失分诊断', '最近作答中最影响得分的短板'),
    'improvement': ('改进训练', '把批改结论转成下一步训练动作'),
    'overview': ('综合训练', '整体表现、趋势和训练安排'),
}

QUESTION_TYPE_HINTS = {
    'document': ('简报', '短评', '公开信', '讲话稿', '倡议书', '宣传稿', '发言稿', '公文'),
    'essay': ('写一篇文章', '议论性文章', '讨论性文章', '大作文', '作文'),
    'summary': ('概括', '归纳'),
    'analysis': ('分析', '谈谈你的理解', '看法'),
    'countermeasure': ('对策', '建议', '措施', '问题'),
}


def classify_module(text: str = '', module_hint: str = '') -> str:
    if module_hint in MODULES:
        return module_hint
    text = (text or '').strip()
    for module, hints in QUESTION_TYPE_HINTS.items():
        if any(hint in text for hint in hints):
            return module
    if any(key in text for key in ('最大失分', '失分点', '最丢分', '短板', '弱项')):
        return 'top_loss'
    if any(key in text for key in ('怎么改', '怎么提高', '怎么改进', '提升', '改进')):
        return 'improvement'
    return 'overview'


def requested_recent_limit(text: str = '') -> int | None:
    match = re.search(r'最近\s*(\d+)\s*(?:道|题|次|篇|个)', text or '')
    if match:
        return max(1, min(int(match.group(1)), 20))
    numbers = {'一': 1, '两': 2, '二': 2, '三': 3, '四': 4, '五': 5, '六': 6, '七': 7, '八': 8, '九': 9, '十': 10}
    for word, value in numbers.items():
        if re.search(rf'最近[^，。！？\s]*{word}\s*(?:道|题|次|篇|个)', text or ''):
            return value
    return None


def infer_intent(text: str = '', entrypoint: str = 'chat', *, has_attempt: bool = True) -> str:
    text = (text or '').strip()
    if any(key in text for key in ('复盘', '最近一次作答', '本题答案', '这份答案', '刚才这题')):
        return 'recent_review' if has_attempt else 'next_question'
    if any(key in text for key in ('下一题', '推荐', '练什么', '安排')):
        return 'next_question'
    if any(key in text for key in ('诊断', '短板', '弱项', '计划', '整体', '全部历史')):
        return 'today'
    if entrypoint in {'recent_review', 'next_question', 'today'}:
        return entrypoint
    return 'today'


def build_intent_plan(
    *,
    text: str,
    entrypoint: str = 'chat',
    module_hint: str = '',
    has_attempt: bool = True,
    subject_ids: list[int] | None = None,
) -> dict[str, Any]:
    subject_ids = subject_ids or []
    resolved_entrypoint = infer_intent(text, entrypoint, has_attempt=has_attempt)
    module = classify_module(text, module_hint)
    if resolved_entrypoint == 'recent_review' and subject_ids:
        action = 'review'
        if any(key in text for key in ('结构', '框架', '分几段')):
            action = 'judge_structure'
        elif any(key in text for key in ('改写', '示范', '重写', '润色')):
            action = 'rewrite'
        return {
            'entrypoint': resolved_entrypoint,
            'action': action,
            'scope': 'current_attempt',
            'module': module,
            'module_label': MODULES[module][0],
            'sources': ['question', 'attempt', 'material', 'reference_answer', 'grading_report', 'memory'],
            'recent_limit': requested_recent_limit(text),
            'reason': 'current_attempt_review',
        }
    if resolved_entrypoint == 'next_question':
        return {
            'entrypoint': resolved_entrypoint,
            'action': 'recommend',
            'scope': 'candidate_questions',
            'module': module,
            'module_label': MODULES[module][0],
            'sources': ['candidate_question', 'weakness_profile', 'statistics', 'memory'],
            'recent_limit': requested_recent_limit(text),
            'reason': 'candidate_question_recommendation',
        }
    action = 'diagnose' if any(key in text for key in ('失分', '短板', '弱项', '问题在哪')) else 'explain'
    if any(key in text for key in ('是什么', '怎么写', '写法', '格式', '模板', '示例')):
        action = 'guide'
    return {
        'entrypoint': resolved_entrypoint,
        'action': action,
        'scope': 'module_history' if module != 'overview' else 'overall_history',
        'module': module,
        'module_label': MODULES[module][0],
        'sources': ['aggregate', 'weakness_profile', 'attempt', 'grading_report', 'memory'],
        'recent_limit': requested_recent_limit(text),
        'reason': 'history_diagnosis',
    }
