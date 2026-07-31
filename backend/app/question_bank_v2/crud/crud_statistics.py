from collections.abc import Sequence
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.admin.model.user import User
from backend.app.question_bank_v2.model.bank import QbBankItem, QbBankSection
from backend.app.question_bank_v2.model.practice import QbQuestionAttempt
from backend.app.question_bank_v2.model.question import QbQuestion
from backend.app.question_bank_v2.model.review import QbWrongQuestionState
from backend.app.question_bank_v2.model.statistics import (
    QbQuestionStatistics,
    QbUserBankItemProgress,
    QbUserDailyStatistics,
    QbUserPracticeStatistics,
)


class CRUDUserBankItemProgress(CRUDPlus[QbUserBankItemProgress]):
    """用户题库题项进度投影数据库操作类"""

    async def apply_attempt(
        self,
        db: AsyncSession,
        *,
        attempt: QbQuestionAttempt,
        bank_item_id: int | None,
    ) -> QbUserBankItemProgress | None:
        """在作答事务内增量维护可重建的题项进度投影"""
        if bank_item_id is None:
            return None
        item = (
            await db.execute(
                select(QbBankItem).where(
                    QbBankItem.id == bank_item_id,
                    QbBankItem.question_id == attempt.question_id,
                    QbBankItem.deleted == 0,
                )
            )
        ).scalars().first()
        if item is None:
            return None

        progress = (
            await db.execute(
                select(QbUserBankItemProgress)
                .where(
                    QbUserBankItemProgress.user_id == attempt.user_id,
                    QbUserBankItemProgress.bank_item_id == item.id,
                    QbUserBankItemProgress.deleted == 0,
                )
                .with_for_update()
            )
        ).scalars().first()
        if progress is None:
            progress = QbUserBankItemProgress(
                user_id=attempt.user_id,
                bank_revision_id=item.bank_revision_id,
                bank_item_id=item.id,
                question_id=item.question_id,
                attempt_count=1,
                correct_count=int(attempt.is_correct is True),
                last_is_correct=attempt.is_correct,
                best_score=attempt.score,
                last_attempt_id=attempt.id,
                first_answered_time=attempt.submitted_time,
                last_answered_time=attempt.submitted_time,
            )
            db.add(progress)
        else:
            progress.attempt_count += 1
            progress.correct_count += int(attempt.is_correct is True)
            progress.last_is_correct = attempt.is_correct
            if attempt.score is not None:
                progress.best_score = max(progress.best_score or Decimal(0), attempt.score)
            progress.last_attempt_id = attempt.id
            progress.last_answered_time = attempt.submitted_time
        await db.flush()
        return progress

    async def apply_delayed_grade(
        self,
        db: AsyncSession,
        *,
        attempt: QbQuestionAttempt,
        bank_item_id: int | None,
    ) -> QbUserBankItemProgress | None:
        """补写先提交后判分的题项进度，不重复累计提交次数"""
        if bank_item_id is None:
            return None
        progress = (
            await db.execute(
                select(QbUserBankItemProgress)
                .where(
                    QbUserBankItemProgress.user_id == attempt.user_id,
                    QbUserBankItemProgress.bank_item_id == bank_item_id,
                    QbUserBankItemProgress.deleted == 0,
                )
                .with_for_update()
            )
        ).scalars().first()
        if progress is None:
            return await self.apply_attempt(db, attempt=attempt, bank_item_id=bank_item_id)
        progress.correct_count += int(attempt.is_correct is True)
        if progress.last_attempt_id == attempt.id:
            progress.last_is_correct = attempt.is_correct
        if attempt.score is not None:
            progress.best_score = max(progress.best_score or Decimal(0), attempt.score)
        await db.flush()
        return progress


class CRUDQuestionStatistics(CRUDPlus[QbQuestionStatistics]):
    """题目统计投影数据库操作类"""

    async def apply_attempt(
        self,
        db: AsyncSession,
        *,
        attempt: QbQuestionAttempt,
        max_score: Decimal,
    ) -> QbQuestionStatistics:
        """按不可变作答事实增量维护题目统计"""
        statistics = (
            await db.execute(
                select(QbQuestionStatistics)
                .where(
                    QbQuestionStatistics.question_id == attempt.question_id,
                    QbQuestionStatistics.deleted == 0,
                )
                .with_for_update()
            )
        ).scalars().first()
        if statistics is None:
            statistics = QbQuestionStatistics(
                question_id=attempt.question_id,
            )
            db.add(statistics)
        previous_attempt_count = statistics.attempt_count
        previous_graded_count = statistics.graded_count
        statistics.attempt_count += 1
        if attempt.is_correct is not None:
            statistics.graded_count += 1
            statistics.correct_count += int(attempt.is_correct)
            statistics.correct_rate = Decimal(statistics.correct_count) / Decimal(statistics.graded_count)
            if attempt.score is not None and max_score > 0:
                score_rate = min(Decimal(1), attempt.score / max_score)
                statistics.avg_score_rate = (
                    ((statistics.avg_score_rate or Decimal(0)) * previous_graded_count + score_rate)
                    / statistics.graded_count
                )
        if attempt.duration_ms is not None:
            statistics.avg_duration_ms = (
                (statistics.avg_duration_ms or Decimal(0)) * previous_attempt_count + attempt.duration_ms
            ) / statistics.attempt_count
        statistics.calculated_time = attempt.submitted_time
        await db.flush()
        return statistics

    async def apply_delayed_grade(
        self,
        db: AsyncSession,
        *,
        attempt: QbQuestionAttempt,
        max_score: Decimal,
    ) -> QbQuestionStatistics:
        """把延迟判分结果补入题目统计，不重复累计提交次数"""
        statistics = (
            await db.execute(
                select(QbQuestionStatistics)
                .where(
                    QbQuestionStatistics.question_id == attempt.question_id,
                    QbQuestionStatistics.deleted == 0,
                )
                .with_for_update()
            )
        ).scalars().first()
        if statistics is None:
            statistics = QbQuestionStatistics(
                question_id=attempt.question_id,
                attempt_count=1,
            )
            db.add(statistics)
        previous_graded_count = statistics.graded_count
        statistics.graded_count += 1
        statistics.correct_count += int(attempt.is_correct is True)
        statistics.correct_rate = Decimal(statistics.correct_count) / Decimal(statistics.graded_count)
        if attempt.score is not None and max_score > 0:
            score_rate = min(Decimal(1), attempt.score / max_score)
            statistics.avg_score_rate = (
                ((statistics.avg_score_rate or Decimal(0)) * previous_graded_count + score_rate)
                / statistics.graded_count
            )
        statistics.calculated_time = attempt.submitted_time
        await db.flush()
        return statistics


class CRUDUserPracticeStatistics(CRUDPlus[QbUserPracticeStatistics]):
    """用户累计刷题统计投影数据库操作类"""

    async def get(self, db: AsyncSession, *, user_id: int, for_update: bool = False) -> QbUserPracticeStatistics | None:
        """获取用户累计刷题统计"""
        stmt = select(QbUserPracticeStatistics).where(
            QbUserPracticeStatistics.user_id == user_id,
            QbUserPracticeStatistics.deleted == 0,
        )
        if for_update:
            stmt = stmt.with_for_update()
        return (await db.execute(stmt)).scalars().first()

    async def apply_attempt(
        self,
        db: AsyncSession,
        *,
        attempt: QbQuestionAttempt,
        is_first_practice_today: bool,
    ) -> QbUserPracticeStatistics:
        """按作答事实维护累计次数、正确率和连续练习天数"""
        statistics = await self.get(db, user_id=attempt.user_id, for_update=True)
        activity_date = attempt.submitted_time.date()
        if statistics is None:
            statistics = QbUserPracticeStatistics(
                user_id=attempt.user_id,
                attempt_count=1,
                graded_count=int(attempt.is_correct is not None),
                correct_count=int(attempt.is_correct is True),
                total_duration_ms=attempt.duration_ms or 0,
                practice_days=1,
                streak_days=1,
                last_practice_date=activity_date,
                calculated_time=attempt.submitted_time,
            )
            db.add(statistics)
        else:
            statistics.attempt_count += 1
            statistics.graded_count += int(attempt.is_correct is not None)
            statistics.correct_count += int(attempt.is_correct is True)
            statistics.total_duration_ms += attempt.duration_ms or 0
            if is_first_practice_today:
                previous_date = statistics.last_practice_date
                statistics.practice_days += 1
                statistics.streak_days = (
                    statistics.streak_days + 1
                    if previous_date == activity_date - timedelta(days=1)
                    else 1
                )
                statistics.last_practice_date = activity_date
            statistics.calculated_time = attempt.submitted_time
        await db.flush()
        return statistics

    async def increment_session(self, db: AsyncSession, *, user_id: int) -> None:
        """在会话首次交卷时累计有效会话数"""
        statistics = await self.get(db, user_id=user_id, for_update=True)
        if statistics is None:
            statistics = QbUserPracticeStatistics(user_id=user_id, session_count=1)
            db.add(statistics)
        else:
            statistics.session_count += 1
        await db.flush()

    async def apply_delayed_grade(self, db: AsyncSession, *, attempt: QbQuestionAttempt) -> None:
        """补写用户累计统计中的已判分数和正确数"""
        statistics = await self.get(db, user_id=attempt.user_id, for_update=True)
        if statistics is None:
            statistics = QbUserPracticeStatistics(
                user_id=attempt.user_id,
                attempt_count=1,
                graded_count=1,
                correct_count=int(attempt.is_correct is True),
                total_duration_ms=attempt.duration_ms or 0,
                practice_days=1,
                streak_days=1,
                last_practice_date=attempt.submitted_time.date(),
                calculated_time=attempt.submitted_time,
            )
            db.add(statistics)
        else:
            statistics.graded_count += 1
            statistics.correct_count += int(attempt.is_correct is True)
            statistics.calculated_time = attempt.submitted_time
        await db.flush()

    async def get_site_summary(self, db: AsyncSession) -> dict[str, int]:
        """获取全站答题量汇总"""
        row = (
            await db.execute(
                select(
                    func.coalesce(func.sum(QbUserPracticeStatistics.attempt_count), 0).label('total_attempt_count'),
                    func.coalesce(func.max(QbUserPracticeStatistics.attempt_count), 0).label('max_attempt_count'),
                ).where(QbUserPracticeStatistics.deleted == 0)
            )
        ).mappings().one()
        return {key: int(value) for key, value in row.items()}

    async def get_rank_rows(
        self,
        db: AsyncSession,
        *,
        rank_type: str,
        current_user_id: int,
        offset: int,
        limit: int,
    ) -> tuple[int, list[dict[str, Any]], dict[str, Any] | None]:
        """直接排序读取榜单页，并通过领先人数计算当前用户排名"""
        if rank_type == 'practice_count':
            value = QbUserPracticeStatistics.attempt_count
        elif rank_type == 'accuracy_rate':
            value = case(
                (
                    QbUserPracticeStatistics.graded_count > 0,
                    QbUserPracticeStatistics.correct_count * 1.0 / QbUserPracticeStatistics.graded_count,
                ),
                else_=0,
            )
        else:
            value = QbUserPracticeStatistics.streak_days
        conditions: tuple[Any, ...] = (
            QbUserPracticeStatistics.attempt_count > 0,
            QbUserPracticeStatistics.deleted == 0,
            User.deleted == 0,
            User.status == 1,
        )
        if rank_type == 'accuracy_rate':
            conditions = (*conditions, QbUserPracticeStatistics.graded_count >= 50)
        base = (
            select(
                QbUserPracticeStatistics.user_id,
                User.nickname,
                User.avatar,
                value.label('value'),
            )
            .join(User, User.id == QbUserPracticeStatistics.user_id)
            .where(*conditions)
        )
        total = int(
            (
                await db.execute(
                    select(func.count())
                    .select_from(QbUserPracticeStatistics)
                    .join(User, User.id == QbUserPracticeStatistics.user_id)
                    .where(*conditions)
                )
            ).scalar_one()
        )
        page_rows = (
            await db.execute(base.order_by(value.desc(), QbUserPracticeStatistics.user_id).offset(offset).limit(limit))
        ).mappings().all()
        rows = [dict(row, rank=offset + index) for index, row in enumerate(page_rows, start=1)]

        current_row = (
            await db.execute(base.where(QbUserPracticeStatistics.user_id == current_user_id))
        ).mappings().first()
        if current_row is None:
            return total, rows, None
        current_value = current_row['value']
        ahead = int(
            (
                await db.execute(
                    select(func.count())
                    .select_from(QbUserPracticeStatistics)
                    .join(User, User.id == QbUserPracticeStatistics.user_id)
                    .where(
                        *conditions,
                        or_(
                            value > current_value,
                            and_(value == current_value, QbUserPracticeStatistics.user_id < current_user_id),
                        ),
                    )
                )
            ).scalar_one()
        )
        return total, rows, dict(current_row, rank=ahead + 1)


class CRUDUserDailyStatistics(CRUDPlus[QbUserDailyStatistics]):
    """用户每日刷题统计投影数据库操作类"""

    async def apply_attempt(self, db: AsyncSession, *, attempt: QbQuestionAttempt) -> bool:
        """维护每日统计并返回是否为当日首条作答"""
        activity_date = attempt.submitted_time.date()
        statistics = (
            await db.execute(
                select(QbUserDailyStatistics)
                .where(
                    QbUserDailyStatistics.user_id == attempt.user_id,
                    QbUserDailyStatistics.activity_date == activity_date,
                    QbUserDailyStatistics.deleted == 0,
                )
                .with_for_update()
            )
        ).scalars().first()
        is_first = statistics is None
        if statistics is None:
            statistics = QbUserDailyStatistics(
                user_id=attempt.user_id,
                activity_date=activity_date,
                attempt_count=1,
                graded_count=int(attempt.is_correct is not None),
                correct_count=int(attempt.is_correct is True),
                duration_ms=attempt.duration_ms or 0,
                first_practice_time=attempt.submitted_time,
                last_practice_time=attempt.submitted_time,
                calculated_time=attempt.submitted_time,
            )
            db.add(statistics)
        else:
            statistics.attempt_count += 1
            statistics.graded_count += int(attempt.is_correct is not None)
            statistics.correct_count += int(attempt.is_correct is True)
            statistics.duration_ms += attempt.duration_ms or 0
            statistics.last_practice_time = attempt.submitted_time
            statistics.calculated_time = attempt.submitted_time
        await db.flush()
        return is_first

    async def get_range(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        start_date: date,
        end_date: date,
    ) -> list[QbUserDailyStatistics]:
        """获取用户日期范围内的每日统计"""
        stmt = (
            select(QbUserDailyStatistics)
            .where(
                QbUserDailyStatistics.user_id == user_id,
                QbUserDailyStatistics.activity_date.between(start_date, end_date),
                QbUserDailyStatistics.deleted == 0,
            )
            .order_by(QbUserDailyStatistics.activity_date)
        )
        return list((await db.execute(stmt)).scalars().all())

    async def apply_delayed_grade(self, db: AsyncSession, *, attempt: QbQuestionAttempt) -> None:
        """补写提交发生日的已判分数和正确数"""
        activity_date = attempt.submitted_time.date()
        statistics = (
            await db.execute(
                select(QbUserDailyStatistics)
                .where(
                    QbUserDailyStatistics.user_id == attempt.user_id,
                    QbUserDailyStatistics.activity_date == activity_date,
                    QbUserDailyStatistics.deleted == 0,
                )
                .with_for_update()
            )
        ).scalars().first()
        if statistics is None:
            statistics = QbUserDailyStatistics(
                user_id=attempt.user_id,
                activity_date=activity_date,
                attempt_count=1,
                graded_count=1,
                correct_count=int(attempt.is_correct is True),
                duration_ms=attempt.duration_ms or 0,
                first_practice_time=attempt.submitted_time,
                last_practice_time=attempt.submitted_time,
                calculated_time=attempt.submitted_time,
            )
            db.add(statistics)
        else:
            statistics.graded_count += 1
            statistics.correct_count += int(attempt.is_correct is True)
            statistics.calculated_time = attempt.submitted_time
        await db.flush()


class CRUDLearningAnalytics:
    """题库进度与错题分组读取操作类"""

    async def get_bank_progress_summary_rows(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        revision_pairs: Sequence[tuple[int, int]],  # [(bank_id, bank_revision_id), ...]
    ) -> list[dict[str, Any]]:
        """按指定 (题库, 版本) 组合批量聚合用户进度，一条 SQL 覆盖全部题库"""
        if not revision_pairs:
            return []
        revision_ids = [revision_id for _, revision_id in revision_pairs]
        stmt = (
            select(
                QbBankItem.bank_revision_id,
                func.count(QbBankItem.id).label('total_count'),
                func.count(QbUserBankItemProgress.id).label('answered_count'),
                func.sum(case((QbUserBankItemProgress.last_is_correct.is_(True), 1), else_=0)).label('correct_count'),
                func.sum(case((QbUserBankItemProgress.last_is_correct.is_(False), 1), else_=0)).label('wrong_count'),
            )
            .outerjoin(
                QbUserBankItemProgress,
                and_(
                    QbUserBankItemProgress.bank_item_id == QbBankItem.id,
                    QbUserBankItemProgress.user_id == user_id,
                    QbUserBankItemProgress.deleted == 0,
                ),
            )
            .where(
                QbBankItem.bank_revision_id.in_(revision_ids),
                QbBankItem.is_active.is_(True),
                QbBankItem.deleted == 0,
            )
            .group_by(QbBankItem.bank_revision_id)
        )
        return [dict(row) for row in (await db.execute(stmt)).mappings().all()]

    async def get_bank_progress_rows(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        bank_revision_id: int,
    ) -> tuple[list[QbBankSection], list[dict[str, Any]], list[dict[str, Any]]]:
        """获取题库篇章统计、分节进度和按题型细分的进度"""
        sections = list(
            (
                await db.execute(
                    select(QbBankSection)
                    .where(
                        QbBankSection.bank_revision_id == bank_revision_id,
                        QbBankSection.deleted == 0,
                    )
                    .order_by(QbBankSection.depth, QbBankSection.sort_order, QbBankSection.id)
                )
            )
            .scalars()
            .all()
        )
        # 按 section 聚合
        stmt = (
            select(
                QbBankItem.section_id,
                func.count(QbBankItem.id).label('total_count'),
                func.count(QbUserBankItemProgress.id).label('answered_count'),
                func.sum(case((QbUserBankItemProgress.last_is_correct.is_(True), 1), else_=0)).label('correct_count'),
                func.sum(case((QbUserBankItemProgress.last_is_correct.is_(False), 1), else_=0)).label('wrong_count'),
            )
            .outerjoin(
                QbUserBankItemProgress,
                and_(
                    QbUserBankItemProgress.bank_item_id == QbBankItem.id,
                    QbUserBankItemProgress.user_id == user_id,
                    QbUserBankItemProgress.deleted == 0,
                ),
            )
            .where(
                QbBankItem.bank_revision_id == bank_revision_id,
                QbBankItem.is_active.is_(True),
                QbBankItem.deleted == 0,
            )
            .group_by(QbBankItem.section_id)
        )
        # 按 section + question_type 聚合
        type_stmt = (
            select(
                QbBankItem.section_id,
                QbQuestion.question_type,
                func.count(QbBankItem.id).label('total_count'),
                func.count(QbUserBankItemProgress.id).label('answered_count'),
                func.sum(case((QbUserBankItemProgress.last_is_correct.is_(True), 1), else_=0)).label('correct_count'),
                func.sum(case((QbUserBankItemProgress.last_is_correct.is_(False), 1), else_=0)).label('wrong_count'),
            )
            .join(QbQuestion, QbQuestion.id == QbBankItem.question_id)
            .outerjoin(
                QbUserBankItemProgress,
                and_(
                    QbUserBankItemProgress.bank_item_id == QbBankItem.id,
                    QbUserBankItemProgress.user_id == user_id,
                    QbUserBankItemProgress.deleted == 0,
                ),
            )
            .where(
                QbBankItem.bank_revision_id == bank_revision_id,
                QbBankItem.is_active.is_(True),
                QbBankItem.deleted == 0,
            )
            .group_by(QbBankItem.section_id, QbQuestion.question_type)
        )
        return (
            sections,
            [dict(row) for row in (await db.execute(stmt)).mappings().all()],
            [dict(row) for row in (await db.execute(type_stmt)).mappings().all()],
        )

    async def get_wrong_section_counts(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        bank_revision_id: int,
    ) -> list[dict[str, Any]]:
        """按当前题库版本篇章统计用户活跃错题"""
        stmt = (
            select(
                QbBankItem.section_id,
                func.count(func.distinct(QbWrongQuestionState.id)).label('wrong_count'),
            )
            .join(
                QbWrongQuestionState,
                and_(
                    QbWrongQuestionState.source_bank_item_id == QbBankItem.id,
                    QbWrongQuestionState.user_id == user_id,
                    QbWrongQuestionState.status == 'active',
                    QbWrongQuestionState.deleted == 0,
                ),
            )
            .where(
                QbBankItem.bank_revision_id == bank_revision_id,
                QbBankItem.is_active.is_(True),
                QbBankItem.deleted == 0,
            )
            .group_by(QbBankItem.section_id)
        )
        return [dict(row) for row in (await db.execute(stmt)).mappings().all()]


user_bank_item_progress_dao: CRUDUserBankItemProgress = CRUDUserBankItemProgress(QbUserBankItemProgress)
question_statistics_dao: CRUDQuestionStatistics = CRUDQuestionStatistics(
    QbQuestionStatistics
)
user_practice_statistics_dao: CRUDUserPracticeStatistics = CRUDUserPracticeStatistics(QbUserPracticeStatistics)
user_daily_statistics_dao: CRUDUserDailyStatistics = CRUDUserDailyStatistics(QbUserDailyStatistics)
learning_analytics_dao: CRUDLearningAnalytics = CRUDLearningAnalytics()
