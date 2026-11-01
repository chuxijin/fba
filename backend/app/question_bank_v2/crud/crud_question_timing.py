"""选择题用时的只读统计，不覆盖原始用时或已有增量投影。"""

from decimal import Decimal

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from backend.app.question_bank_v2.model.practice import QbPracticeSession, QbQuestionAttempt
from backend.app.question_bank_v2.utils.external_practice import online_attempt_condition, online_session_condition

CHOICE_DURATION_MIN_MS = 1_000
CHOICE_DURATION_MAX_MS = 300_000


async def get_question_timing(db: AsyncSession, *, question_id: int) -> tuple[Decimal | None, int]:
    """仅在线有效作答；考试只纳入已结算的最终答案，隐藏会话仍保留样本。"""
    newer = aliased(QbQuestionAttempt)
    has_newer = (
        select(newer.id)
        .where(
            newer.session_item_id == QbQuestionAttempt.session_item_id,
            newer.attempt_no > QbQuestionAttempt.attempt_no,
        )
        .correlate(QbQuestionAttempt)
        .exists()
    )
    stmt = (
        select(func.avg(QbQuestionAttempt.duration_ms), func.count(QbQuestionAttempt.id))
        .outerjoin(QbPracticeSession, QbPracticeSession.id == QbQuestionAttempt.session_id)
        .where(
            QbQuestionAttempt.question_id == question_id,
            QbQuestionAttempt.deleted == 0,
            QbQuestionAttempt.duration_ms.between(CHOICE_DURATION_MIN_MS, CHOICE_DURATION_MAX_MS),
            online_attempt_condition(),
            online_session_condition(),
            or_(
                QbPracticeSession.id.is_(None),
                QbPracticeSession.mode.in_({'practice', 'review', 'adaptive'}),
                and_(
                    QbPracticeSession.mode.in_({'exam', 'mock'}),
                    QbPracticeSession.status.in_({'submitted', 'graded', 'expired'}),
                    ~has_newer,
                ),
            ),
        )
    )
    average, count = (await db.execute(stmt)).one()
    return (Decimal(str(average)).quantize(Decimal('0.01')) if average is not None else None, int(count))
