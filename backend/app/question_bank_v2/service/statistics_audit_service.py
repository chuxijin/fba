"""只读核对统计与作答事实，不在有歧义的旧数据上盲目回放增量。"""

from collections import Counter
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.question_bank_v2.crud.crud_statistics import question_statistics_dao
from backend.app.question_bank_v2.model.practice import QbPracticeSession, QbQuestionAttempt
from backend.app.question_bank_v2.utils.external_practice import is_external_practice


async def audit_question_statistics(*, db: AsyncSession, question_ids: Sequence[int]) -> list[dict]:
    """调用方显式限定题目；未知旧取消会话单列，不自动猜测曾否结算。"""
    reports = []
    for question_id in sorted(set(question_ids)):
        rows = (
            await db.execute(
                select(QbQuestionAttempt, QbPracticeSession)
                .outerjoin(QbPracticeSession, QbPracticeSession.id == QbQuestionAttempt.session_id)
                .where(QbQuestionAttempt.question_id == question_id, QbQuestionAttempt.deleted == 0)
                .order_by(QbQuestionAttempt.session_item_id, QbQuestionAttempt.attempt_no.desc())
            )
        ).all()
        eligible = []
        uncertain = []
        seen_items = set()
        for attempt, session in rows:
            if is_external_practice(attempt.grading_result):
                continue
            if session is not None and session.mode in {'exam', 'mock'}:
                if attempt.session_item_id in seen_items:
                    continue
                seen_items.add(attempt.session_item_id)
                marker = (attempt.grading_result or {}).get('_projection') or {}
                if session.status == 'cancelled' and not marker.get('submitted'):
                    uncertain.append(attempt.id)
                    continue
                if not marker.get('submitted') and session.status not in {'submitted', 'graded', 'expired'}:
                    continue
            eligible.append(attempt)
        distribution = Counter()
        for attempt in eligible:
            value = question_statistics_dao._extract_response_value(attempt.response_data)
            if value is not None:
                distribution[question_statistics_dao._response_distribution_key(value)] += 1
        actual = await question_statistics_dao.get_by_question(db, question_id)
        expected = {
            'attempt_count': len(eligible),
            'graded_count': sum(attempt.is_correct is not None for attempt in eligible),
            'correct_count': sum(attempt.is_correct is True for attempt in eligible),
            'response_distribution': dict(distribution),
        }
        observed = {
            'attempt_count': actual.attempt_count if actual else 0,
            'graded_count': actual.graded_count if actual else 0,
            'correct_count': actual.correct_count if actual else 0,
            'response_distribution': dict(actual.response_distribution or {}) if actual else {},
        }
        reports.append({
            'question_id': question_id,
            'expected': expected,
            'actual': observed,
            'matches': expected == observed and not uncertain,
            'uncertain_attempt_ids': uncertain,
        })
    return reports
