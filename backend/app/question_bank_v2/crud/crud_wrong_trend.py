from collections.abc import Sequence
from datetime import datetime
from typing import Any

from sqlalchemy import Date, and_, cast, exists, func, or_, select, union_all
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.question_bank_v2.crud.crud_review import wrong_question_state_dao
from backend.app.question_bank_v2.model.practice import QbQuestionAttempt
from backend.app.question_bank_v2.model.question import QbQuestion
from backend.app.question_bank_v2.model.review import QbQuestionReview, QbWrongQuestionState
from backend.app.question_bank_v2.model.wrong_trend import QbWrongMasteryEvent, QbWrongTrendCoverage
from backend.core.conf import settings


class CRUDWrongTrend(CRUDPlus[QbWrongMasteryEvent]):
    @staticmethod
    def record_mastery(
        db: AsyncSession, *, state: QbWrongQuestionState, now: datetime, attempt_id: int | None = None
    ) -> None:
        """调用方持有用户/状态锁，仅在真实转换时追加，随原事务提交或回滚。"""
        db.add(
            QbWrongMasteryEvent(
                user_id=state.user_id,
                question_id=state.question_id,
                wrong_state_id=state.id,
                occurred_time=now,
                source='manual' if attempt_id is None else 'attempt',
                source_attempt_id=attempt_id,
                created_by=state.user_id,
            )
        )

    @staticmethod
    async def coverage_start(db: AsyncSession) -> datetime | None:
        return await db.scalar(
            select(QbWrongTrendCoverage.started_time).where(
                QbWrongTrendCoverage.id == 1,
                QbWrongTrendCoverage.deleted == 0,
            )
        )

    @staticmethod
    async def daily_counts(
        db: AsyncSession,
        *,
        user_id: int,
        start: datetime,
        end: datetime,
        today_start: datetime,
        today_end: datetime,
        domain_category_ids: Sequence[int] | None,
    ) -> dict[str, dict[str, int | None]]:
        state = QbWrongQuestionState

        def natural_day(column: Any) -> Any:
            # SQLite 保存配置时区的墙上时间；PostgreSQL 的 timestamptz 显式转配置时区。
            return (
                cast(func.timezone(settings.DATETIME_TIMEZONE, column), Date)
                if db.get_bind().dialect.name == 'postgresql'
                else func.date(column)
            )

        def facts(model: Any, time_column: Any, *conditions: Any) -> Select:
            stmt = (
                select(model.question_id.label('question_id'), time_column.label('occurred_time'))
                .join(state, and_(state.user_id == model.user_id, state.question_id == model.question_id))
                .join(QbQuestion, QbQuestion.id == model.question_id)
                .where(
                    model.user_id == user_id,
                    model.deleted == 0,
                    state.deleted == 0,
                    QbQuestion.deleted == 0,
                    or_(
                        and_(time_column >= start, time_column < end),
                        and_(time_column >= today_start, time_column < today_end),
                    ),
                    *conditions,
                )
            )
            if model is not QbQuestionAttempt:
                stmt = stmt.where(state.id == model.wrong_state_id)
            return wrong_question_state_dao._apply_domain_scope(stmt, domain_category_ids)

        wrong = union_all(
            facts(
                QbQuestionAttempt,
                QbQuestionAttempt.submitted_time,
                QbQuestionAttempt.is_correct.is_(False),
                func.coalesce(QbQuestionAttempt.response_data['mode'].as_string(), '') != 'memorize',
            ),
            facts(
                QbQuestionReview,
                QbQuestionReview.reviewed_time,
                QbQuestionReview.event_type == 'capture',
                func.coalesce(QbQuestionReview.review_data['external_wrong']['legacy_initial'].as_boolean(), False).is_(
                    False
                ),
            ),
        )
        sources = {
            'wrong': wrong,
            'reviewed': facts(
                QbQuestionReview, QbQuestionReview.reviewed_time, QbQuestionReview.event_type == 'review'
            ),
            'mastered': facts(QbWrongMasteryEvent, QbWrongMasteryEvent.occurred_time),
        }
        # 历史外部初次入本缺少事实时，不能把不完整的当日合计显示成已知的0。
        missing_initial = (
            select(state.question_id.label('question_id'), state.created_time.label('occurred_time'))
            .join(QbQuestion, QbQuestion.id == state.question_id)
            .where(
                state.user_id == user_id,
                state.deleted == 0,
                QbQuestion.deleted == 0,
                state.entry_source.in_(('manual', 'ocr', 'import')),
                or_(
                    and_(state.created_time >= start, state.created_time < end),
                    and_(state.created_time >= today_start, state.created_time < today_end),
                ),
                ~exists(
                    select(QbQuestionReview.id).where(
                        QbQuestionReview.wrong_state_id == state.id,
                        QbQuestionReview.user_id == user_id,
                        QbQuestionReview.deleted == 0,
                        QbQuestionReview.event_type == 'capture',
                        natural_day(QbQuestionReview.reviewed_time) == natural_day(state.created_time),
                    )
                ),
            )
        )
        sources['unknown_wrong'] = union_all(
            facts(
                QbQuestionReview,
                QbQuestionReview.reviewed_time,
                QbQuestionReview.event_type == 'capture',
                QbQuestionReview.review_data['external_wrong']['legacy_initial'].as_boolean().is_(True),
            ),
            wrong_question_state_dao._apply_domain_scope(missing_initial, domain_category_ids),
        )
        result = {}
        for metric, source in sources.items():
            rows = source.subquery()
            day = natural_day(rows.c.occurred_time)
            stmt = select(day, func.count(func.distinct(rows.c.question_id))).group_by(day)
            result[metric] = {str(day): int(count) for day, count in (await db.execute(stmt)).all()}
        for unknown_day in result.pop('unknown_wrong'):
            result['wrong'][unknown_day] = None
        return result


wrong_trend_dao = CRUDWrongTrend(QbWrongMasteryEvent)
