import hashlib
import json
import re
from typing import Any

from sqlalchemy import func
from sqlalchemy.sql.elements import ColumnElement

from backend.app.question_bank_v2.model.practice import QbPracticeSession, QbQuestionAttempt

EXTERNAL_PRACTICE_ORIGIN = 'external_practice'
EXTERNAL_SESSION_PREFIX = 'external-'

_DIGEST_TAG_RE = re.compile(r'</?(?:b|strong|u)\b[^>]*>', re.IGNORECASE)
_DIGEST_SPACE_RE = re.compile(r'[\s\u00a0\xa0]+')


def normalize_content_for_digest(text: str) -> str:
    """对题干和选项文本进行归一化清洗，消除纯排版标签和空白符差异对题目指纹的影响"""
    if not text:
        return ''
    cleaned = _DIGEST_TAG_RE.sub('', text)
    cleaned = cleaned.replace('&nbsp;', ' ')
    cleaned = _DIGEST_SPACE_RE.sub(' ', cleaned).strip()
    return cleaned


def is_external_practice(snapshot: dict[str, Any] | None) -> bool:
    return bool(snapshot and snapshot.get('origin') == EXTERNAL_PRACTICE_ORIGIN)


def online_session_condition() -> ColumnElement[bool]:
    """导入历史不计入在线刷题查询、今日任务或奖励。"""
    return func.coalesce(QbPracticeSession.source_snapshot['origin'].as_string(), '') != EXTERNAL_PRACTICE_ORIGIN


def online_attempt_condition() -> ColumnElement[bool]:
    return func.coalesce(QbQuestionAttempt.grading_result['origin'].as_string(), '') != EXTERNAL_PRACTICE_ORIGIN


def import_digest(*values: Any) -> str:
    return hashlib.sha256(
        json.dumps(values, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()
    ).hexdigest()


def question_content_digest(
    *, stem: str, content_format: str, question_type: str, options: list[dict[str, Any]]
) -> str:
    """题目内容指纹：跨来源（错题录入 / 刷题记录导入）复用同一份题目时使用"""
    norm_stem = normalize_content_for_digest(stem)
    norm_options = []
    for opt in options:
        opt_dict = dict(opt)
        if 'content' in opt_dict:
            opt_dict['content'] = normalize_content_for_digest(str(opt_dict['content']))
        norm_options.append(opt_dict)

    return import_digest({
        'stem': norm_stem,
        'content_format': content_format,
        'question_type': question_type,
        'options': norm_options,
    })


def imported_session_key(user_id: int, platform: str, source_key: str) -> str:
    return EXTERNAL_SESSION_PREFIX + import_digest(user_id, platform, source_key)[:48]
