from typing import Any

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.question_bank_v2.model.bank import QbBankItem, QbBankSection
from backend.app.question_bank_v2.model.practice import QbQuestionAttempt
from backend.app.question_bank_v2.model.question import QbQuestion
from backend.app.question_bank_v2.model.statistics import QbQuestionStatistics
from backend.app.question_bank_v2.utils.external_practice import online_attempt_condition


class CRUDBankHighError:
    """限定当前卷内可见题，批量读取全体用户统计，不读取其他用户答案。"""

    @staticmethod
    async def get_rows(db: AsyncSession, *, revision_id: int, user_id: int) -> list[dict[str, Any]]:
        scope = (
            select(
                QbBankItem.id.label('bank_item_id'),
                QbBankItem.question_id,
                QbBankItem.section_id,
                QbBankItem.score,
                QbBankItem.settings,
                QbBankItem.sort_order,
                QbQuestion.question_type,
                QbQuestionStatistics.graded_count,
                QbQuestionStatistics.correct_count,
            )
            .join(QbQuestion, QbQuestion.id == QbBankItem.question_id)
            .outerjoin(QbBankSection, QbBankSection.id == QbBankItem.section_id)
            .outerjoin(
                QbQuestionStatistics,
                and_(
                    QbQuestionStatistics.question_id == QbQuestion.id,
                    QbQuestionStatistics.deleted == 0,
                ),
            )
            .where(
                QbBankItem.bank_revision_id == revision_id,
                QbBankItem.deleted == 0,
                QbBankItem.is_active.is_(True),
                QbQuestion.deleted == 0,
                QbQuestion.status == 'active',
                or_(QbQuestion.visibility != 'private', QbQuestion.owner_id == user_id),
                or_(
                    QbBankItem.section_id.is_(None),
                    and_(QbBankSection.deleted == 0, QbBankSection.bank_revision_id == revision_id),
                ),
            )
        )
        rows = (
            (
                await db.execute(
                    scope.order_by(QbBankItem.section_id.nulls_first(), QbBankItem.sort_order, QbBankItem.id)
                )
            )
            .mappings()
            .all()
        )
        # 同题多次编排只取首次位置；统计基线和章节计数也使用相同去重口径。
        unique = {row['question_id']: dict(row) for row in reversed(rows)}
        if not unique:
            return []
        question_scope = scope.with_only_columns(QbBankItem.question_id).distinct().subquery()
        durations = (
            (
                await db.execute(
                    select(
                        QbQuestionAttempt.question_id,
                        func.count().label('duration_count'),
                        func.avg(QbQuestionAttempt.duration_ms).label('avg_duration_ms'),
                    )
                    .join(question_scope, question_scope.c.question_id == QbQuestionAttempt.question_id)
                    .where(
                        QbQuestionAttempt.deleted == 0,
                        QbQuestionAttempt.duration_ms > 0,
                        online_attempt_condition(),
                    )
                    .group_by(QbQuestionAttempt.question_id)
                )
            )
            .mappings()
            .all()
        )
        for duration in durations:
            unique[duration['question_id']].update(dict(duration))
        return [
            unique[row['question_id']]
            for row in rows
            if unique[row['question_id']]['bank_item_id'] == row['bank_item_id']
        ]


bank_high_error_dao = CRUDBankHighError()
