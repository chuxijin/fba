from __future__ import annotations

import json
import re

from hashlib import sha256
from typing import Any

RUBRIC_VERSION = 'shenlun-rubric-v4'
RESULT_VERSION = 'shenlun-grading-result-v4'
PIPELINE_VERSION = 'shenlun-smart-grading-v4'
MAX_MODEL_CALLS = 3

QUESTION_TYPE_PROFILES: dict[str, dict[str, float]] = {
    '归纳概括': {'content': 70, 'structure': 15, 'expression': 10, 'format': 5},
    '综合分析': {'content': 55, 'reasoning': 25, 'structure': 10, 'expression': 10},
    '提出对策': {'content': 60, 'feasibility': 20, 'structure': 10, 'expression': 10},
    '公文写作': {'content': 50, 'format': 20, 'structure': 20, 'expression': 10},
    '综合写作': {'content': 40, 'reasoning': 25, 'structure': 20, 'expression': 10, 'format': 5},
}

CRITERION_LABELS = {
    'content': '围绕题目任务准确、完整地使用材料信息，重点突出且无明显事实偏差',
    'structure': '结构层次符合题目任务，分点或段落组织清楚',
    'expression': '表达准确、规范、简洁，避免歧义和重复',
    'format': '文种、身份、称谓、落款和字数格式符合要求',
    'reasoning': '论点、论据与论证关系完整，材料转化合理',
    'feasibility': '对策回应问题，主体、对象和措施明确，具有针对性与可执行性',
}

ANSWER_GRID_RULES = """考试答题纸占格规则：
- 汉字、全角标点每个占1格。
- 连续英文、半角数字每2个字符占1格，奇数个向上取整。
- 标准破折号“——”、省略号“……”整体占2格。
- 空格占1格；手动换行会结算当前行剩余格。"""


def clean(value: Any, limit: int = 0) -> str:
    text = re.sub(r'<br\s*/?>', '\n', str(value or ''), flags=re.IGNORECASE)
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    if limit and len(text) > limit:
        return text[:limit].rstrip() + '...'
    return text


def stable_hash(value: Any) -> str:
    data = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), default=str)
    return sha256(data.encode()).hexdigest()


def infer_question_type(stem: str, reference_context: dict[str, Any]) -> str:
    configured = clean(reference_context.get('grading_config', {}).get('shenlun_question_type'))
    if configured in QUESTION_TYPE_PROFILES:
        return configured
    text = clean(stem)
    rules = (
        ('综合写作', r'文章|议论文|自拟题目|自选角度|写一篇'),
        ('公文写作', r'讲话稿|倡议书|公开信|通知|简报|发言稿|宣传稿|调研报告|工作建议'),
        ('提出对策', r'提出.*(?:对策|措施|建议)|解决.*问题|如何改进'),
        ('综合分析', r'谈谈.*理解|进行分析|加以评析|看法|认识|启示'),
    )
    for question_type, pattern in rules:
        if re.search(pattern, text):
            return question_type
    return '归纳概括'


def extract_word_limit(stem: str, grading_config: dict[str, Any]) -> str:
    configured = clean(grading_config.get('word_limit'))
    if configured:
        return configured
    patterns = (
        r'\d+\s*[～~—至到-]\s*\d+\s*(?:字|格)(?:以内|左右|之间)?',
        r'(?:不少于|不低于|不超过|不多于|控制在|约)\s*\d+\s*(?:字|格)(?:以内|左右)?',
        r'\d+\s*(?:字|格)(?:以内|左右)',
    )
    for pattern in patterns:
        match = re.search(pattern, clean(stem))
        if match:
            return match.group(0)
    return ''


def default_dimensions(question_type: str, max_score: float) -> list[dict[str, Any]]:
    profile = QUESTION_TYPE_PROFILES.get(question_type, QUESTION_TYPE_PROFILES['归纳概括'])
    return [
        {
            'criterion_id': f'{dimension}-1',
            'dimension': dimension,
            'label': CRITERION_LABELS[dimension],
            'weight': round(max_score * weight / 100, 3),
        }
        for dimension, weight in profile.items()
    ]


def content_weight(question_type: str, max_score: float) -> float:
    profile = QUESTION_TYPE_PROFILES.get(question_type, QUESTION_TYPE_PROFILES['归纳概括'])
    return round(max_score * profile['content'] / 100, 3)


def coverage_factor(value: Any, status: str) -> float:
    if status == 'hit':
        return 1.0
    if status == 'miss':
        return 0.0
    try:
        number = float(str(value).rstrip('%'))
        if str(value).strip().endswith('%') or number > 1:
            number /= 100
    except (TypeError, ValueError):
        number = 0.5
    return round(max(0.1, min(0.9, number)) * 20) / 20


def grade_label(score: float, max_score: float) -> str:
    ratio = score / max_score if max_score else 0
    if ratio >= 0.8:
        return '优秀'
    if ratio >= 0.65:
        return '良好'
    if ratio >= 0.5:
        return '一般'
    return '较弱'
