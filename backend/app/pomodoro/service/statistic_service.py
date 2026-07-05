#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from calendar import monthrange
from datetime import date, datetime, timedelta

from sqlalchemy import distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.pomodoro.enums import PomodoroFocusStatus, PomodoroTaskStatus
from backend.app.pomodoro.model.focus import PomodoroFocusSession
from backend.app.pomodoro.model.habit import PomodoroHabitCheckin
from backend.app.pomodoro.model.task import PomodoroTask
from backend.app.pomodoro.schema.statistic import (
    GetPomodoroCalendarStatistic,
    GetPomodoroRangeStatistic,
    GetPomodoroSummaryStatistic,
    GetPomodoroTodayStatistic,
    PomodoroDailyStatisticItem,
    PomodoroDistributionItem,
    PomodoroStatisticPoint,
)
from backend.app.pomodoro.service.setting_service import pomodoro_setting_service
from backend.utils.timezone import timezone


class PomodoroStatisticService:
    """番茄统计服务类"""

    @staticmethod
    async def get_summary(
        *,
        db: AsyncSession,
        user_id: int,
        start_date: date,
        end_date: date,
        granularity: str,
        distribution: str,
    ) -> GetPomodoroSummaryStatistic:
        """
        获取通用汇总统计

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param start_date: 开始日期
        :param end_date: 结束日期
        :param granularity: 统计粒度
        :param distribution: 分布维度
        :return:
        """
        if end_date < start_date:
            end_date = start_date

        if granularity == 'month':
            points = await PomodoroStatisticService._get_month_points(
                db=db,
                user_id=user_id,
                start_date=start_date,
                end_date=end_date,
            )
        else:
            points = await PomodoroStatisticService._get_day_points(
                db=db,
                user_id=user_id,
                start_date=start_date,
                end_date=end_date,
            )

        focused_seconds = sum(item.focused_seconds for item in points)
        completed_task_count = sum(item.completed_task_count for item in points)
        finished_session_count = sum(item.finished_session_count for item in points)
        avg_task_seconds = focused_seconds // completed_task_count if completed_task_count > 0 else 0
        distribution_items = await PomodoroStatisticService._get_range_distribution(
            db=db,
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
            dimension=distribution,
        )

        return GetPomodoroSummaryStatistic(
            start_date=start_date,
            end_date=end_date,
            focused_seconds=focused_seconds,
            completed_task_count=completed_task_count,
            finished_session_count=finished_session_count,
            avg_task_seconds=avg_task_seconds,
            points=points,
            distribution=distribution_items,
        )

    @staticmethod
    async def get_total(*, db: AsyncSession, user_id: int) -> dict[str, int]:
        """
        获取历史累计专注统计

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        stmt = select(
            func.count(PomodoroFocusSession.id).label("total_count"),
            func.sum(PomodoroFocusSession.focused_seconds).label("total_seconds")
        ).where(
            PomodoroFocusSession.user_id == user_id,
            PomodoroFocusSession.status == PomodoroFocusStatus.completed
        )
        res = await db.execute(stmt)
        row = res.first()
        total_count = int(row.total_count or 0) if row else 0
        total_seconds = int(row.total_seconds or 0) if row else 0

        # 计算日均时长
        first_stmt = select(PomodoroFocusSession.created_time).where(
            PomodoroFocusSession.user_id == user_id
        ).order_by(PomodoroFocusSession.created_time.asc()).limit(1)
        first_res = await db.execute(first_stmt)
        first_time = first_res.scalar()
        if first_time:
            days = max(1, (timezone.now() - first_time).days + 1)
        else:
            days = 1
        avg_seconds = total_seconds // days
        return {
            "total_count": total_count,
            "total_seconds": total_seconds,
            "avg_seconds": avg_seconds
        }

    @staticmethod
    async def get_today(*, db: AsyncSession, user_id: int) -> GetPomodoroTodayStatistic:
        """
        获取今日统计

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        now = timezone.now()
        start_at = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_at = start_at + timedelta(days=1)

        focused_seconds = await PomodoroStatisticService._sum_today_focused_seconds(
            db=db,
            user_id=user_id,
            start_at=start_at,
            end_at=end_at,
        )
        completed_task_count = await PomodoroStatisticService._count_today_completed_tasks(
            db=db,
            user_id=user_id,
            start_at=start_at,
            end_at=end_at,
        )
        finished_session_count = await PomodoroStatisticService._count_today_finished_sessions(
            db=db,
            user_id=user_id,
            start_at=start_at,
            end_at=end_at,
        )
        habit_checkin_count = await PomodoroStatisticService._sum_today_habit_checkins(
            db=db,
            user_id=user_id,
            statistic_date=now.date(),
        )
        current_streak_days = await PomodoroStatisticService._count_current_streak_days(db=db, user_id=user_id)
        setting = await pomodoro_setting_service.get_or_create(db=db, user_id=user_id)

        return GetPomodoroTodayStatistic(
            statistic_date=now.date(),
            focused_seconds=focused_seconds,
            completed_task_count=completed_task_count,
            finished_session_count=finished_session_count,
            habit_checkin_count=habit_checkin_count,
            daily_focus_goal_minutes=setting.daily_focus_minutes,
            daily_focus_progress_percent=PomodoroStatisticService._calc_progress_percent(
                current_seconds=focused_seconds,
                goal_minutes=setting.daily_focus_minutes,
            ),
            current_streak_days=current_streak_days,
        )

    @staticmethod
    async def get_weekly(
        *,
        db: AsyncSession,
        user_id: int,
        base_date: date | None = None,
    ) -> GetPomodoroRangeStatistic:
        """
        获取周统计

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param base_date: 基准日期
        :return:
        """
        current_date = base_date or timezone.now().date()
        start_date = current_date - timedelta(days=current_date.weekday())
        end_date = start_date + timedelta(days=6)
        return await PomodoroStatisticService._get_range_statistic(
            db=db,
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
        )

    @staticmethod
    async def get_monthly(
        *,
        db: AsyncSession,
        user_id: int,
        year: int | None = None,
        month: int | None = None,
    ) -> GetPomodoroRangeStatistic:
        """
        获取月统计

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param year: 年份
        :param month: 月份
        :return:
        """
        now = timezone.now()
        statistic_year = year or now.year
        statistic_month = month or now.month
        start_date = date(statistic_year, statistic_month, 1)
        end_date = date(statistic_year, statistic_month, monthrange(statistic_year, statistic_month)[1])
        return await PomodoroStatisticService._get_range_statistic(
            db=db,
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
        )

    @staticmethod
    async def get_calendar(
        *,
        db: AsyncSession,
        user_id: int,
        year: int,
        month: int,
    ) -> GetPomodoroCalendarStatistic:
        """
        获取日历统计

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param year: 年份
        :param month: 月份
        :return:
        """
        range_statistic = await PomodoroStatisticService.get_monthly(
            db=db,
            user_id=user_id,
            year=year,
            month=month,
        )
        return GetPomodoroCalendarStatistic(
            year=year,
            month=month,
            **range_statistic.model_dump(),
        )

    @staticmethod
    async def _sum_today_focused_seconds(
        *,
        db: AsyncSession,
        user_id: int,
        start_at: datetime,
        end_at: datetime,
    ) -> int:
        """
        汇总今日专注秒数

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param start_at: 开始时间
        :param end_at: 结束时间
        :return:
        """
        stmt = select(func.coalesce(func.sum(PomodoroFocusSession.focused_seconds), 0)).where(
            PomodoroFocusSession.user_id == user_id,
            PomodoroFocusSession.status == PomodoroFocusStatus.completed.value,
            PomodoroFocusSession.ended_at >= start_at,
            PomodoroFocusSession.ended_at < end_at,
        )
        result = await db.execute(stmt)
        return int(result.scalar() or 0)

    @staticmethod
    async def _count_today_completed_tasks(
        *,
        db: AsyncSession,
        user_id: int,
        start_at: datetime,
        end_at: datetime,
    ) -> int:
        """
        统计今日完成任务数

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param start_at: 开始时间
        :param end_at: 结束时间
        :return:
        """
        stmt = select(func.count(PomodoroTask.id)).where(
            PomodoroTask.user_id == user_id,
            PomodoroTask.status == PomodoroTaskStatus.completed.value,
            PomodoroTask.completed_at >= start_at,
            PomodoroTask.completed_at < end_at,
        )
        result = await db.execute(stmt)
        return int(result.scalar() or 0)

    @staticmethod
    async def _count_today_finished_sessions(
        *,
        db: AsyncSession,
        user_id: int,
        start_at: datetime,
        end_at: datetime,
    ) -> int:
        """
        统计今日完成专注次数

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param start_at: 开始时间
        :param end_at: 结束时间
        :return:
        """
        stmt = select(func.count(PomodoroFocusSession.id)).where(
            PomodoroFocusSession.user_id == user_id,
            PomodoroFocusSession.status == PomodoroFocusStatus.completed.value,
            PomodoroFocusSession.ended_at >= start_at,
            PomodoroFocusSession.ended_at < end_at,
        )
        result = await db.execute(stmt)
        return int(result.scalar() or 0)

    @staticmethod
    async def _sum_today_habit_checkins(*, db: AsyncSession, user_id: int, statistic_date: date) -> int:
        """
        汇总今日习惯打卡次数

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param statistic_date: 统计日期
        :return:
        """
        stmt = select(func.coalesce(func.sum(PomodoroHabitCheckin.count), 0)).where(
            PomodoroHabitCheckin.user_id == user_id,
            PomodoroHabitCheckin.checkin_date == statistic_date,
        )
        result = await db.execute(stmt)
        return int(result.scalar() or 0)

    @staticmethod
    async def _get_range_statistic(
        *,
        db: AsyncSession,
        user_id: int,
        start_date: date,
        end_date: date,
    ) -> GetPomodoroRangeStatistic:
        """
        获取日期范围统计

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param start_date: 开始日期
        :param end_date: 结束日期
        :return:
        """
        days = PomodoroStatisticService._build_empty_days(start_date=start_date, end_date=end_date)
        start_at = PomodoroStatisticService._date_start(start_date)
        end_at = PomodoroStatisticService._date_start(end_date + timedelta(days=1))

        await PomodoroStatisticService._fill_focus_daily_stats(
            db=db,
            user_id=user_id,
            start_at=start_at,
            end_at=end_at,
            days=days,
        )
        await PomodoroStatisticService._fill_task_daily_stats(
            db=db,
            user_id=user_id,
            start_at=start_at,
            end_at=end_at,
            days=days,
        )
        await PomodoroStatisticService._fill_habit_daily_stats(
            db=db,
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
            days=days,
        )

        day_items = list(days.values())
        setting = await pomodoro_setting_service.get_or_create(db=db, user_id=user_id)
        focus_goal_minutes = PomodoroStatisticService._resolve_range_goal_minutes(
            setting_daily_minutes=setting.daily_focus_minutes,
            setting_weekly_minutes=setting.weekly_focus_minutes,
            start_date=start_date,
            end_date=end_date,
        )
        focused_seconds = sum(item.focused_seconds for item in day_items)
        return GetPomodoroRangeStatistic(
            start_date=start_date,
            end_date=end_date,
            focused_seconds=focused_seconds,
            completed_task_count=sum(item.completed_task_count for item in day_items),
            finished_session_count=sum(item.finished_session_count for item in day_items),
            habit_checkin_count=sum(item.habit_checkin_count for item in day_items),
            focus_goal_minutes=focus_goal_minutes,
            focus_progress_percent=PomodoroStatisticService._calc_progress_percent(
                current_seconds=focused_seconds,
                goal_minutes=focus_goal_minutes,
            ),
            days=day_items,
        )

    @staticmethod
    async def _get_day_points(
        *,
        db: AsyncSession,
        user_id: int,
        start_date: date,
        end_date: date,
    ) -> list[PomodoroStatisticPoint]:
        """
        获取每日统计点

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param start_date: 开始日期
        :param end_date: 结束日期
        :return:
        """
        days = PomodoroStatisticService._build_empty_days(start_date=start_date, end_date=end_date)
        start_at = PomodoroStatisticService._date_start(start_date)
        end_at = PomodoroStatisticService._date_start(end_date + timedelta(days=1))

        await PomodoroStatisticService._fill_focus_daily_stats(
            db=db,
            user_id=user_id,
            start_at=start_at,
            end_at=end_at,
            days=days,
        )
        await PomodoroStatisticService._fill_task_daily_stats(
            db=db,
            user_id=user_id,
            start_at=start_at,
            end_at=end_at,
            days=days,
        )

        return [
            PomodoroStatisticPoint(
                period=item.statistic_date.isoformat(),
                start_date=item.statistic_date,
                end_date=item.statistic_date,
                focused_seconds=item.focused_seconds,
                completed_task_count=item.completed_task_count,
                finished_session_count=item.finished_session_count,
            )
            for item in days.values()
        ]

    @staticmethod
    async def _get_month_points(
        *,
        db: AsyncSession,
        user_id: int,
        start_date: date,
        end_date: date,
    ) -> list[PomodoroStatisticPoint]:
        """
        获取每月统计点

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param start_date: 开始日期
        :param end_date: 结束日期
        :return:
        """
        day_points = await PomodoroStatisticService._get_day_points(
            db=db,
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
        )
        month_map: dict[str, PomodoroStatisticPoint] = {}

        for item in day_points:
            period = item.start_date.strftime('%Y-%m')
            month_start = item.start_date.replace(day=1)
            month_end = date(item.start_date.year, item.start_date.month, monthrange(item.start_date.year, item.start_date.month)[1])
            if period not in month_map:
                month_map[period] = PomodoroStatisticPoint(
                    period=period,
                    start_date=month_start,
                    end_date=month_end,
                    focused_seconds=0,
                    completed_task_count=0,
                    finished_session_count=0,
                )
            month_map[period].focused_seconds += item.focused_seconds
            month_map[period].completed_task_count += item.completed_task_count
            month_map[period].finished_session_count += item.finished_session_count

        return list(month_map.values())

    @staticmethod
    def _build_empty_days(*, start_date: date, end_date: date) -> dict[date, PomodoroDailyStatisticItem]:
        """
        构建空日期统计

        :param start_date: 开始日期
        :param end_date: 结束日期
        :return:
        """
        days: dict[date, PomodoroDailyStatisticItem] = {}
        current_date = start_date
        while current_date <= end_date:
            days[current_date] = PomodoroDailyStatisticItem(
                statistic_date=current_date,
                focused_seconds=0,
                completed_task_count=0,
                finished_session_count=0,
                habit_checkin_count=0,
            )
            current_date = current_date + timedelta(days=1)
        return days

    @staticmethod
    async def _fill_focus_daily_stats(
        *,
        db: AsyncSession,
        user_id: int,
        start_at: datetime,
        end_at: datetime,
        days: dict[date, PomodoroDailyStatisticItem],
    ) -> None:
        """
        填充每日专注统计

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param start_at: 开始时间
        :param end_at: 结束时间
        :param days: 每日统计
        :return:
        """
        statistic_day = func.date(PomodoroFocusSession.ended_at)
        stmt = (
            select(
                statistic_day,
                func.coalesce(func.sum(PomodoroFocusSession.focused_seconds), 0),
                func.count(PomodoroFocusSession.id),
            )
            .where(
                PomodoroFocusSession.user_id == user_id,
                PomodoroFocusSession.status == PomodoroFocusStatus.completed.value,
                PomodoroFocusSession.ended_at >= start_at,
                PomodoroFocusSession.ended_at < end_at,
            )
            .group_by(statistic_day)
        )
        result = await db.execute(stmt)
        for statistic_date, focused_seconds, session_count in result.all():
            normalized_date = PomodoroStatisticService._normalize_date(statistic_date)
            if normalized_date in days:
                days[normalized_date].focused_seconds = int(focused_seconds or 0)
                days[normalized_date].finished_session_count = int(session_count or 0)

    @staticmethod
    async def _fill_task_daily_stats(
        *,
        db: AsyncSession,
        user_id: int,
        start_at: datetime,
        end_at: datetime,
        days: dict[date, PomodoroDailyStatisticItem],
    ) -> None:
        """
        填充每日任务统计

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param start_at: 开始时间
        :param end_at: 结束时间
        :param days: 每日统计
        :return:
        """
        statistic_day = func.date(PomodoroTask.completed_at)
        stmt = (
            select(statistic_day, func.count(PomodoroTask.id))
            .where(
                PomodoroTask.user_id == user_id,
                PomodoroTask.status == PomodoroTaskStatus.completed.value,
                PomodoroTask.completed_at >= start_at,
                PomodoroTask.completed_at < end_at,
            )
            .group_by(statistic_day)
        )
        result = await db.execute(stmt)
        for statistic_date, task_count in result.all():
            normalized_date = PomodoroStatisticService._normalize_date(statistic_date)
            if normalized_date in days:
                days[normalized_date].completed_task_count = int(task_count or 0)

    @staticmethod
    async def _fill_habit_daily_stats(
        *,
        db: AsyncSession,
        user_id: int,
        start_date: date,
        end_date: date,
        days: dict[date, PomodoroDailyStatisticItem],
    ) -> None:
        """
        填充每日习惯打卡统计

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param start_date: 开始日期
        :param end_date: 结束日期
        :param days: 每日统计
        :return:
        """
        stmt = (
            select(PomodoroHabitCheckin.checkin_date, func.coalesce(func.sum(PomodoroHabitCheckin.count), 0))
            .where(
                PomodoroHabitCheckin.user_id == user_id,
                PomodoroHabitCheckin.checkin_date >= start_date,
                PomodoroHabitCheckin.checkin_date <= end_date,
            )
            .group_by(PomodoroHabitCheckin.checkin_date)
        )
        result = await db.execute(stmt)
        for statistic_date, checkin_count in result.all():
            normalized_date = PomodoroStatisticService._normalize_date(statistic_date)
            if normalized_date in days:
                days[normalized_date].habit_checkin_count = int(checkin_count or 0)

    @staticmethod
    def _date_start(value: date) -> datetime:
        """
        获取日期开始时间

        :param value: 日期
        :return:
        """
        return timezone.now().replace(
            year=value.year,
            month=value.month,
            day=value.day,
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        )

    @staticmethod
    def _resolve_range_goal_minutes(
        *,
        setting_daily_minutes: int,
        setting_weekly_minutes: int,
        start_date: date,
        end_date: date,
    ) -> int:
        """
        获取日期范围目标分钟数

        :param setting_daily_minutes: 每日目标分钟数
        :param setting_weekly_minutes: 每周目标分钟数
        :param start_date: 开始日期
        :param end_date: 结束日期
        :return:
        """
        day_count = (end_date - start_date).days + 1
        if day_count == 7:
            return setting_weekly_minutes
        return setting_daily_minutes * day_count

    @staticmethod
    def _calc_progress_percent(*, current_seconds: int, goal_minutes: int) -> float:
        """
        计算目标进度

        :param current_seconds: 当前秒数
        :param goal_minutes: 目标分钟数
        :return:
        """
        if goal_minutes <= 0:
            return 0.0
        progress = current_seconds / max(1, goal_minutes * 60) * 100
        return round(min(100.0, progress), 1)

    @staticmethod
    async def _count_current_streak_days(*, db: AsyncSession, user_id: int) -> int:
        """
        统计连续专注天数

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        stmt = (
            select(distinct(func.date(PomodoroFocusSession.ended_at)))
            .where(
                PomodoroFocusSession.user_id == user_id,
                PomodoroFocusSession.status == PomodoroFocusStatus.completed.value,
                PomodoroFocusSession.ended_at.isnot(None),
            )
            .order_by(func.date(PomodoroFocusSession.ended_at).desc())
            .limit(366)
        )
        result = await db.execute(stmt)
        focus_dates = [item for item in result.scalars().all() if item]
        if not focus_dates:
            return 0

        current_date = timezone.now().date()
        normalized_dates = {PomodoroStatisticService._normalize_date(item) for item in focus_dates}
        if current_date not in normalized_dates:
            current_date = current_date - timedelta(days=1)
            if current_date not in normalized_dates:
                return 0

        streak_days = 0
        while current_date in normalized_dates:
            streak_days += 1
            current_date = current_date - timedelta(days=1)

        return streak_days

    @staticmethod
    def _normalize_date(value: date | datetime | str) -> date:
        """
        规范化日期

        :param value: 日期值
        :return:
        """
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, str):
            return date.fromisoformat(value[:10])
        return value

    @staticmethod
    async def get_today_distribution(
        *,
        db: AsyncSession,
        user_id: int,
        dimension: str,
    ) -> list[PomodoroDistributionItem]:
        """
        获取今日专注分布

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param dimension: 维度 (category / tag)
        :return:
        """
        now = timezone.now()
        return await PomodoroStatisticService._get_range_distribution(
            db=db,
            user_id=user_id,
            start_date=now.date(),
            end_date=now.date(),
            dimension=dimension,
        )

    @staticmethod
    async def _get_range_distribution(
        *,
        db: AsyncSession,
        user_id: int,
        start_date: date,
        end_date: date,
        dimension: str,
    ) -> list[PomodoroDistributionItem]:
        """
        获取日期范围专注分布

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param start_date: 开始日期
        :param end_date: 结束日期
        :param dimension: 维度
        :return:
        """
        from backend.app.admin.model.cat import SysCat, SysCatTarget
        from backend.app.admin.model.tag import SysTag, SysTagTarget

        start_at = PomodoroStatisticService._date_start(start_date)
        end_at = PomodoroStatisticService._date_start(end_date + timedelta(days=1))

        if dimension == 'tag':
            name_col = SysTag.name
            color_col = SysTag.color
            stmt = (
                select(
                    name_col,
                    color_col,
                    func.coalesce(func.sum(PomodoroFocusSession.focused_seconds), 0).label('total'),
                )
                .join(SysTagTarget, (SysTagTarget.target_type == 'pomodoro_task') & (SysTagTarget.target_id == PomodoroFocusSession.task_id))
                .join(SysTag, SysTag.id == SysTagTarget.tag_id)
                .where(
                    PomodoroFocusSession.user_id == user_id,
                    PomodoroFocusSession.status == PomodoroFocusStatus.completed.value,
                    PomodoroFocusSession.ended_at >= start_at,
                    PomodoroFocusSession.ended_at < end_at,
                    PomodoroFocusSession.task_id.isnot(None),
                )
                .group_by(SysTag.id, name_col, color_col)
                .order_by(func.sum(PomodoroFocusSession.focused_seconds).desc())
            )
        else:
            name_col = SysCat.name
            color_col = SysCat.color
            stmt = (
                select(
                    name_col,
                    color_col,
                    func.coalesce(func.sum(PomodoroFocusSession.focused_seconds), 0).label('total'),
                )
                .join(SysCatTarget, (SysCatTarget.target_type == 'pomodoro_task') & (SysCatTarget.target_id == PomodoroFocusSession.task_id))
                .join(SysCat, SysCat.id == SysCatTarget.cat_id)
                .where(
                    PomodoroFocusSession.user_id == user_id,
                    PomodoroFocusSession.status == PomodoroFocusStatus.completed.value,
                    PomodoroFocusSession.ended_at >= start_at,
                    PomodoroFocusSession.ended_at < end_at,
                    PomodoroFocusSession.task_id.isnot(None),
                )
                .group_by(SysCat.id, name_col, color_col)
                .order_by(func.sum(PomodoroFocusSession.focused_seconds).desc())
            )

        result = await db.execute(stmt)
        rows = result.all()

        grand_total = sum(int(row.total or 0) for row in rows)

        # 计算无分类/标签的专注时间
        total_range_stmt = select(
            func.coalesce(func.sum(PomodoroFocusSession.focused_seconds), 0)
        ).where(
            PomodoroFocusSession.user_id == user_id,
            PomodoroFocusSession.status == PomodoroFocusStatus.completed.value,
            PomodoroFocusSession.ended_at >= start_at,
            PomodoroFocusSession.ended_at < end_at,
        )
        total_range_seconds = int((await db.execute(total_range_stmt)).scalar() or 0)
        uncategorized_seconds = total_range_seconds - grand_total
        if uncategorized_seconds < 0:
            uncategorized_seconds = 0
        percentage_total = grand_total + uncategorized_seconds

        items: list[PomodoroDistributionItem] = []
        for row in rows:
            seconds = int(row.total or 0)
            pct = round(seconds / percentage_total * 100, 1) if percentage_total > 0 else 0.0
            items.append(PomodoroDistributionItem(
                name=row[0],
                color=row[1],
                focused_seconds=seconds,
                percentage=pct,
            ))

        if uncategorized_seconds > 0:
            pct = round(uncategorized_seconds / percentage_total * 100, 1) if percentage_total > 0 else 0.0
            items.append(PomodoroDistributionItem(
                name='未分类',
                color='#94A3B8',
                focused_seconds=uncategorized_seconds,
                percentage=pct,
            ))

        return items


pomodoro_statistic_service: PomodoroStatisticService = PomodoroStatisticService()
