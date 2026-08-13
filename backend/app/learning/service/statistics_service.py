from calendar import monthrange
from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.learning.enums import LearningFocusStatus
from backend.app.learning.model.execution import LearningCompletionRecord, LearningFocusSession
from backend.app.learning.model.task import LearningTask, LearningTaskKnowledgePoint
from backend.app.learning.schema.statistics import (
    GetLearningSummaryStatistic,
    LearningStatisticDistributionItem,
    LearningStatisticPoint,
)
from backend.app.question_bank_v2.model.knowledge import QbKnowledgePoint, QbKnowledgeSystem
from backend.utils.timezone import timezone


class LearningStatisticsService:
    """学习专注统计服务。"""

    _FREE_FOCUS_LABEL = '自由专注'
    _FREE_FOCUS_COLOR = '#94A3B8'

    _TASK_TYPE_LABELS = {
        'learn': '学习',
        'read': '阅读',
        'practice': '刷题',
        'wrong_review': '错题复习',
        'ability': '能力练习',
        'review': '复习',
        'custom': '自定义',
    }

    _TASK_TYPE_COLORS = {
        'learn': '#8B5CF6',
        'read': '#3B82F6',
        'practice': '#EF4444',
        'wrong_review': '#F59E0B',
        'ability': '#10B981',
        'review': '#6366F1',
        'custom': '#64748B',
    }

    async def get_summary(
        self,
        *,
        db: AsyncSession,
        user_id: int,
        start_date: date,
        end_date: date,
        granularity: str,
        distribution: str,
    ) -> GetLearningSummaryStatistic:
        if end_date < start_date:
            end_date = start_date

        start_at = self._date_start(start_date)
        end_at = self._date_start(end_date + timedelta(days=1))
        daily_values = defaultdict(self._empty_daily_value)

        focus_result = await db.execute(
            select(
                func.date(LearningFocusSession.ended_at).label('stat_date'),
                func.coalesce(func.sum(LearningFocusSession.focused_seconds), 0).label('focused_seconds'),
                func.count(LearningFocusSession.id).label('finished_session_count'),
            )
            .where(
                LearningFocusSession.user_id == user_id,
                LearningFocusSession.status == LearningFocusStatus.completed.value,
                LearningFocusSession.ended_at >= start_at,
                LearningFocusSession.ended_at < end_at,
                LearningFocusSession.deleted == 0,
            )
            .group_by(func.date(LearningFocusSession.ended_at))
        )
        for row in focus_result.all():
            stat_date = self._normalize_date(row.stat_date)
            if stat_date is None:
                continue
            daily_values[stat_date]['focused_seconds'] += int(row.focused_seconds or 0)
            daily_values[stat_date]['finished_session_count'] += int(row.finished_session_count or 0)

        completion_result = await db.execute(
            select(
                func.date(LearningCompletionRecord.completed_at).label('stat_date'),
                func.count(LearningCompletionRecord.id).label('completed_task_count'),
            )
            .where(
                LearningCompletionRecord.user_id == user_id,
                LearningCompletionRecord.completed_at >= start_at,
                LearningCompletionRecord.completed_at < end_at,
                LearningCompletionRecord.deleted == 0,
            )
            .group_by(func.date(LearningCompletionRecord.completed_at))
        )
        for row in completion_result.all():
            stat_date = self._normalize_date(row.stat_date)
            if stat_date is None:
                continue
            daily_values[stat_date]['completed_task_count'] += int(row.completed_task_count or 0)

        points = self._build_month_points(daily_values) if granularity == 'month' else self._build_day_points(
            daily_values,
            start_date,
            end_date,
        )
        focused_seconds = sum(item.focused_seconds for item in points)
        completed_task_count = sum(item.completed_task_count for item in points)
        finished_session_count = sum(item.finished_session_count for item in points)
        distribution_items = await self._build_distribution(
            db=db,
            user_id=user_id,
            start_at=start_at,
            end_at=end_at,
            distribution=distribution,
            focused_seconds=focused_seconds,
        )

        return GetLearningSummaryStatistic(
            start_date=start_date,
            end_date=end_date,
            focused_seconds=focused_seconds,
            completed_task_count=completed_task_count,
            finished_session_count=finished_session_count,
            avg_task_seconds=focused_seconds // completed_task_count if completed_task_count else 0,
            points=points,
            distribution=distribution_items,
        )

    async def _build_distribution(
        self,
        *,
        db: AsyncSession,
        user_id: int,
        start_at: datetime,
        end_at: datetime,
        distribution: str,
        focused_seconds: int,
    ) -> list[LearningStatisticDistributionItem]:
        if focused_seconds <= 0:
            return []

        sessions = await self._get_focus_sessions(
            db=db,
            user_id=user_id,
            start_at=start_at,
            end_at=end_at,
        )
        if not sessions:
            return []

        task_ids = {task_id for task_id, _ in sessions if task_id is not None}
        if distribution == 'task_type':
            task_types = await self._get_task_types(db=db, user_id=user_id, task_ids=task_ids)
            totals, colors = self._build_task_type_totals(sessions=sessions, task_types=task_types)
            return self._to_distribution_items(totals, colors, focused_seconds)

        totals = await self._build_knowledge_point_totals(db=db, task_ids=task_ids, sessions=sessions)
        return self._to_distribution_items(totals, {self._FREE_FOCUS_LABEL: self._FREE_FOCUS_COLOR}, focused_seconds)

    @staticmethod
    async def _get_focus_sessions(
        *,
        db: AsyncSession,
        user_id: int,
        start_at: datetime,
        end_at: datetime,
    ) -> list[tuple[int | None, int]]:
        result = await db.execute(
            select(LearningFocusSession.task_id, LearningFocusSession.focused_seconds)
            .where(
                LearningFocusSession.user_id == user_id,
                LearningFocusSession.status == LearningFocusStatus.completed.value,
                LearningFocusSession.ended_at >= start_at,
                LearningFocusSession.ended_at < end_at,
                LearningFocusSession.deleted == 0,
                LearningFocusSession.focused_seconds > 0,
            )
        )
        return [(int(task_id) if task_id is not None else None, int(seconds or 0)) for task_id, seconds in result.all()]

    @staticmethod
    async def _get_task_types(
        *,
        db: AsyncSession,
        user_id: int,
        task_ids: set[int],
    ) -> dict[int, str]:
        if not task_ids:
            return {}
        result = await db.execute(
            select(LearningTask.id, LearningTask.action_type).where(
                LearningTask.id.in_(task_ids),
                LearningTask.user_id == user_id,
                LearningTask.deleted == 0,
            )
        )
        return {int(task_id): action_type for task_id, action_type in result.all()}

    def _build_task_type_totals(
        self,
        *,
        sessions: list[tuple[int | None, int]],
        task_types: dict[int, str],
    ) -> tuple[dict[str, int], dict[str, str | None]]:
        totals: dict[str, int] = defaultdict(int)
        colors: dict[str, str | None] = {}
        for task_id, seconds in sessions:
            if task_id is None:
                totals[self._FREE_FOCUS_LABEL] += seconds
                colors[self._FREE_FOCUS_LABEL] = self._FREE_FOCUS_COLOR
                continue
            action_type = task_types.get(task_id, 'custom')
            name = self._TASK_TYPE_LABELS.get(action_type, '其他')
            totals[name] += seconds
            colors[name] = self._TASK_TYPE_COLORS.get(action_type)
        return totals, colors

    @staticmethod
    async def _build_knowledge_point_totals(
        *,
        db: AsyncSession,
        task_ids: set[int],
        sessions: list[tuple[int | None, int]],
    ) -> dict[str, int]:
        links_by_task: dict[int, list[tuple[str, Decimal]]] = defaultdict(list)
        if task_ids:
            knowledge_result = await db.execute(
                select(
                    LearningTaskKnowledgePoint.task_id,
                    LearningTaskKnowledgePoint.knowledge_point_id,
                    LearningTaskKnowledgePoint.weight,
                    QbKnowledgePoint.name,
                    QbKnowledgeSystem.name,
                )
                .join(
                    QbKnowledgePoint,
                    QbKnowledgePoint.id == LearningTaskKnowledgePoint.knowledge_point_id,
                )
                .join(QbKnowledgeSystem, QbKnowledgeSystem.id == LearningTaskKnowledgePoint.knowledge_system_id)
                .where(
                    LearningTaskKnowledgePoint.task_id.in_(task_ids),
                    LearningTaskKnowledgePoint.deleted == 0,
                    QbKnowledgePoint.deleted == 0,
                    QbKnowledgeSystem.deleted == 0,
                )
            )
            for task_id, _point_id, weight, point_name, system_name in knowledge_result.all():
                display_name = f'{system_name} · {point_name}' if system_name else str(point_name)
                links_by_task[int(task_id)].append((display_name, Decimal(str(weight or 1))))

        totals: dict[str, int] = defaultdict(int)
        for task_id, seconds in sessions:
            if task_id is None:
                totals[LearningStatisticsService._FREE_FOCUS_LABEL] += seconds
                continue
            links = links_by_task.get(task_id)
            if not links:
                totals['未关联知识点'] += seconds
                continue
            for name, part in LearningStatisticsService._allocate_seconds(seconds, links):
                totals[name] += part
        return totals

    @staticmethod
    def _allocate_seconds(
        seconds: int,
        links: list[tuple[str, Decimal]],
    ) -> list[tuple[str, int]]:
        weight_total = sum((weight for _, weight in links), Decimal(0))
        if weight_total <= 0:
            return [('未关联知识点', seconds)]
        allocations = []
        allocated = 0
        for index, (name, weight) in enumerate(links):
            if index == len(links) - 1:
                part = seconds - allocated
            else:
                part = int((Decimal(seconds) * weight / weight_total).quantize(Decimal(1)))
                part = min(part, seconds - allocated)
            allocations.append((name, part))
            allocated += part
        return allocations

    @staticmethod
    def _to_distribution_items(
        totals: dict[str, int],
        colors: dict[str, str | None],
        focused_seconds: int,
    ) -> list[LearningStatisticDistributionItem]:
        items = []
        for name, seconds in sorted(totals.items(), key=lambda item: (-item[1], item[0])):
            if seconds <= 0:
                continue
            items.append(
                LearningStatisticDistributionItem(
                    name=name,
                    color=colors.get(name),
                    focused_seconds=seconds,
                    percentage=round(seconds * 100 / focused_seconds, 1),
                )
            )
        return items

    @staticmethod
    def _empty_daily_value() -> dict[str, int]:
        return {
            'focused_seconds': 0,
            'completed_task_count': 0,
            'finished_session_count': 0,
        }

    @classmethod
    def _build_day_points(
        cls,
        daily_values: dict[date, dict[str, int]],
        start_date: date,
        end_date: date,
    ) -> list[LearningStatisticPoint]:
        points = []
        current_date = start_date
        while current_date <= end_date:
            value = daily_values[current_date]
            points.append(
                LearningStatisticPoint(
                    period=current_date.isoformat(),
                    start_date=current_date,
                    end_date=current_date,
                    **value,
                )
            )
            current_date += timedelta(days=1)
        return points

    @classmethod
    def _build_month_points(
        cls,
        daily_values: dict[date, dict[str, int]],
    ) -> list[LearningStatisticPoint]:
        month_values: dict[str, dict[str, int]] = defaultdict(cls._empty_daily_value)
        for stat_date, value in daily_values.items():
            month_values[stat_date.strftime('%Y-%m')]['focused_seconds'] += value['focused_seconds']
            month_values[stat_date.strftime('%Y-%m')]['completed_task_count'] += value['completed_task_count']
            month_values[stat_date.strftime('%Y-%m')]['finished_session_count'] += value['finished_session_count']

        points = []
        for period in sorted(month_values):
            year, month = (int(item) for item in period.split('-'))
            month_start = date(year, month, 1)
            month_end = date(year, month, monthrange(year, month)[1])
            points.append(
                LearningStatisticPoint(
                    period=period,
                    start_date=month_start,
                    end_date=month_end,
                    **month_values[period],
                )
            )
        return points

    @staticmethod
    def _date_start(value: date) -> datetime:
        now = timezone.now()
        return now.replace(
            year=value.year,
            month=value.month,
            day=value.day,
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        )

    @staticmethod
    def _normalize_date(value: date | datetime | str | None) -> date | None:
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        if isinstance(value, str):
            return date.fromisoformat(value[:10])
        return None


learning_statistics_service = LearningStatisticsService()
