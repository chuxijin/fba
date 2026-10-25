import hashlib
import json

from typing import Any

from sqlalchemy import func
from sqlalchemy.sql.elements import ColumnElement

from backend.app.question_bank_v2.model.practice import QbPracticeSession, QbQuestionAttempt

EXTERNAL_PRACTICE_ORIGIN = 'external_practice'
EXTERNAL_SESSION_PREFIX = 'external-'


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
    return import_digest({
        'stem': stem,
        'content_format': content_format,
        'question_type': question_type,
        'options': options,
    })


def imported_session_key(user_id: int, platform: str, source_key: str) -> str:
    return EXTERNAL_SESSION_PREFIX + import_digest(user_id, platform, source_key)[:48]
