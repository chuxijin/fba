import math

from decimal import Decimal

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.question_bank_v2.model.practice import QbQuestionAttempt
from backend.app.question_bank_v2.model.question import QbQuestion

MIN_VALID_ATTEMPTS = 50
RECALCULATE_INTERVAL = 10
MIN_VALID_DURATION_MS = 3_000
SIGMOID_K = 8.0


def compute_difficulty(
    *,
    valid_attempts: int,
    valid_correct: int,
    valid_avg_duration_ms: Decimal | None,
    median_duration_ms: Decimal | None,
) -> Decimal | None:
    """根据有效作答正确率和相对耗时计算 1.0-5.0 难度。"""
    if valid_attempts < MIN_VALID_ATTEMPTS:
        return None

    correct_rate = valid_correct / valid_attempts
    base = 1.0 + 4.0 / (1.0 + math.exp(-SIGMOID_K * (0.5 - correct_rate)))
    if (
        valid_avg_duration_ms is not None
        and valid_avg_duration_ms > 0
        and median_duration_ms is not None
        and median_duration_ms > 0
    ):
        time_factor = float(
            max(
                Decimal('0.5'),
                min(Decimal('2.0'), valid_avg_duration_ms / median_duration_ms),
            )
        )
    else:
        time_factor = 1.0

    value = base * (0.7 + 0.3 * time_factor)
    return Decimal(str(round(max(1.0, min(5.0, value)), 1)))


def should_recalculate_difficulty(graded_count: int) -> bool:
    """达到最低样本量后按固定增量重算，避免每次作答执行分位数聚合。"""
    return graded_count == MIN_VALID_ATTEMPTS or (
        graded_count > MIN_VALID_ATTEMPTS and graded_count % RECALCULATE_INTERVAL == 0
    )


class DifficultyService:
    """从不可变作答事实重建题目难度缓存。"""

    @staticmethod
    async def recalculate(*, db: AsyncSession, question_id: int) -> Decimal | None:
        valid_scope = (
            QbQuestionAttempt.question_id == question_id,
            QbQuestionAttempt.is_correct.is_not(None),
            QbQuestionAttempt.duration_ms.is_not(None),
            QbQuestionAttempt.duration_ms >= MIN_VALID_DURATION_MS,
            QbQuestionAttempt.deleted == 0,
        )
        row = (
            await db.execute(
                select(
                    func.count(QbQuestionAttempt.id).label('valid_attempts'),
                    func.sum(case((QbQuestionAttempt.is_correct.is_(True), 1), else_=0)).label(
                        'valid_correct'
                    ),
                    func.avg(QbQuestionAttempt.duration_ms).label('avg_duration_ms'),
                    func.percentile_cont(0.5)
                    .within_group(QbQuestionAttempt.duration_ms)
                    .label('median_duration_ms'),
                ).where(*valid_scope)
            )
        ).mappings().one()
        difficulty = compute_difficulty(
            valid_attempts=int(row['valid_attempts'] or 0),
            valid_correct=int(row['valid_correct'] or 0),
            valid_avg_duration_ms=Decimal(str(row['avg_duration_ms']))
            if row['avg_duration_ms'] is not None
            else None,
            median_duration_ms=Decimal(str(row['median_duration_ms']))
            if row['median_duration_ms'] is not None
            else None,
        )
        question = (
            await db.execute(
                select(QbQuestion)
                .where(QbQuestion.id == question_id, QbQuestion.deleted == 0)
                .with_for_update()
            )
        ).scalars().first()
        if question is not None:
            question.difficulty = difficulty
            await db.flush()
        return difficulty


difficulty_service: DifficultyService = DifficultyService()
