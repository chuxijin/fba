#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import date, datetime, timedelta

from sqlalchemy import distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.pomodoro.crud.crud_achievement import (
    pomodoro_achievement_rule_dao,
    pomodoro_user_achievement_dao,
)
from backend.app.pomodoro.enums import (
    PomodoroAchievementMetric,
    PomodoroAchievementStatus,
    PomodoroFocusMode,
    PomodoroFocusStatus,
)
from backend.app.pomodoro.model.achievement import PomodoroAchievementRule, PomodoroUserAchievement
from backend.app.pomodoro.model.focus import PomodoroFocusSession
from backend.app.pomodoro.model.habit import PomodoroHabitCheckin
from backend.app.pomodoro.schema.achievement import (
    CreatePomodoroAchievementRuleInternal,
    CreatePomodoroUserAchievementInternal,
    GetPomodoroAchievementList,
    PomodoroAchievementItem,
)
from backend.common.exception import errors
from backend.utils.timezone import timezone


class PomodoroAchievementService:
    """番茄成就服务类"""

    _default_rules = [
        {
            'code': 'focus_hour_1',
            'name': '初次沉浸',
            'description': '累计专注 1 小时',
            'metric': PomodoroAchievementMetric.total_focus_hours,
            'threshold_value': 1,
            'badge_level': 'bronze',
            'icon': 'clock',
            'sort': 10,
        },
        {
            'code': 'focus_hour_10',
            'name': '稳定投入',
            'description': '累计专注 10 小时',
            'metric': PomodoroAchievementMetric.total_focus_hours,
            'threshold_value': 10,
            'badge_level': 'silver',
            'icon': 'clock',
            'sort': 11,
        },
        {
            'code': 'focus_hour_50',
            'name': '长期专注',
            'description': '累计专注 50 小时',
            'metric': PomodoroAchievementMetric.total_focus_hours,
            'threshold_value': 50,
            'badge_level': 'gold',
            'icon': 'clock',
            'sort': 12,
        },
        {
            'code': 'focus_streak_3',
            'name': '连续三天',
            'description': '连续专注 3 天',
            'metric': PomodoroAchievementMetric.focus_streak_days,
            'threshold_value': 3,
            'badge_level': 'bronze',
            'icon': 'calendar',
            'sort': 20,
        },
        {
            'code': 'focus_streak_7',
            'name': '一周不断',
            'description': '连续专注 7 天',
            'metric': PomodoroAchievementMetric.focus_streak_days,
            'threshold_value': 7,
            'badge_level': 'silver',
            'icon': 'calendar',
            'sort': 21,
        },
        {
            'code': 'focus_streak_30',
            'name': '月度坚持',
            'description': '连续专注 30 天',
            'metric': PomodoroAchievementMetric.focus_streak_days,
            'threshold_value': 30,
            'badge_level': 'gold',
            'icon': 'calendar',
            'sort': 22,
        },
        {
            'code': 'habit_streak_3',
            'name': '习惯起步',
            'description': '连续习惯打卡 3 天',
            'metric': PomodoroAchievementMetric.habit_streak_days,
            'threshold_value': 3,
            'badge_level': 'bronze',
            'icon': 'check',
            'sort': 30,
        },
        {
            'code': 'habit_streak_7',
            'name': '习惯成形',
            'description': '连续习惯打卡 7 天',
            'metric': PomodoroAchievementMetric.habit_streak_days,
            'threshold_value': 7,
            'badge_level': 'silver',
            'icon': 'check',
            'sort': 31,
        },
        {
            'code': 'habit_streak_21',
            'name': '习惯稳定',
            'description': '连续习惯打卡 21 天',
            'metric': PomodoroAchievementMetric.habit_streak_days,
            'threshold_value': 21,
            'badge_level': 'gold',
            'icon': 'check',
            'sort': 32,
        },
        {
            'code': 'pomodoro_count_10',
            'name': '十个番茄',
            'description': '完成 10 个番茄',
            'metric': PomodoroAchievementMetric.completed_pomodoro_count,
            'threshold_value': 10,
            'badge_level': 'bronze',
            'icon': 'timer',
            'sort': 40,
        },
        {
            'code': 'pomodoro_count_50',
            'name': '五十个番茄',
            'description': '完成 50 个番茄',
            'metric': PomodoroAchievementMetric.completed_pomodoro_count,
            'threshold_value': 50,
            'badge_level': 'silver',
            'icon': 'timer',
            'sort': 41,
        },
        {
            'code': 'pomodoro_count_100',
            'name': '百轮专注',
            'description': '完成 100 个番茄',
            'metric': PomodoroAchievementMetric.completed_pomodoro_count,
            'threshold_value': 100,
            'badge_level': 'gold',
            'icon': 'timer',
            'sort': 42,
        },
    ]

    @staticmethod
    async def get_list(*, db: AsyncSession, user_id: int) -> GetPomodoroAchievementList:
        """
        获取用户成就列表

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        rules = await PomodoroAchievementService._ensure_default_rules(db=db)
        metric_values = await PomodoroAchievementService._get_metric_values(db=db, user_id=user_id)
        user_achievements = await pomodoro_user_achievement_dao.get_by_user(db, user_id)
        achievement_map = {item.rule_id: item for item in user_achievements}
        items = [
            PomodoroAchievementService._build_item(
                rule=rule,
                user_achievement=achievement_map.get(rule.id),
                current_value=metric_values[PomodoroAchievementMetric(rule.metric)],
            )
            for rule in rules
        ]

        return GetPomodoroAchievementList(
            total_focus_hours=metric_values[PomodoroAchievementMetric.total_focus_hours],
            focus_streak_days=metric_values[PomodoroAchievementMetric.focus_streak_days],
            habit_streak_days=metric_values[PomodoroAchievementMetric.habit_streak_days],
            completed_pomodoro_count=metric_values[PomodoroAchievementMetric.completed_pomodoro_count],
            items=items,
        )

    @staticmethod
    async def evaluate(*, db: AsyncSession, user_id: int) -> GetPomodoroAchievementList:
        """
        评估用户成就

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        rules = await PomodoroAchievementService._ensure_default_rules(db=db)
        metric_values = await PomodoroAchievementService._get_metric_values(db=db, user_id=user_id)
        now = timezone.now()

        for rule in rules:
            current_value = metric_values[PomodoroAchievementMetric(rule.metric)]
            if current_value < rule.threshold_value:
                continue

            user_achievement = await pomodoro_user_achievement_dao.get_by_user_and_rule(db, user_id, rule.id)
            if user_achievement:
                await PomodoroAchievementService._update_progress(
                    db=db,
                    user_achievement=user_achievement,
                    current_value=current_value,
                )
                continue

            await pomodoro_user_achievement_dao.create_model(
                db,
                CreatePomodoroUserAchievementInternal(
                    user_id=user_id,
                    rule_id=rule.id,
                    progress_value=current_value,
                    achieved_at=now,
                ),
                commit=False,
            )

        await db.flush()
        return await PomodoroAchievementService.get_list(db=db, user_id=user_id)

    @staticmethod
    async def claim(*, db: AsyncSession, user_id: int, achievement_id: int) -> PomodoroUserAchievement:
        """
        领取用户成就

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param achievement_id: 用户成就 ID
        :return:
        """
        user_achievement = await pomodoro_user_achievement_dao.select_model(db, achievement_id)
        if not user_achievement or user_achievement.user_id != user_id:
            raise errors.NotFoundError(msg='成就记录不存在或无权访问')

        if user_achievement.status == PomodoroAchievementStatus.claimed.value:
            return user_achievement

        now = timezone.now()
        await pomodoro_user_achievement_dao.update_model(
            db,
            user_achievement.id,
            {
                'status': PomodoroAchievementStatus.claimed.value,
                'claimed_at': now,
            },
            commit=False,
        )
        await db.flush()
        await db.refresh(user_achievement)
        return user_achievement

    @staticmethod
    async def _ensure_default_rules(*, db: AsyncSession) -> list[PomodoroAchievementRule]:
        """
        确保默认成就规则存在

        :param db: 数据库会话
        :return:
        """
        changed = False
        for rule_data in PomodoroAchievementService._default_rules:
            rule = await pomodoro_achievement_rule_dao.get_by_code(db, str(rule_data['code']))
            if rule:
                continue

            await pomodoro_achievement_rule_dao.create_model(
                db,
                CreatePomodoroAchievementRuleInternal(**rule_data),
                commit=False,
            )
            changed = True

        if changed:
            await db.flush()

        return await pomodoro_achievement_rule_dao.get_enabled_rules(db)

    @staticmethod
    async def _get_metric_values(
        *,
        db: AsyncSession,
        user_id: int,
    ) -> dict[PomodoroAchievementMetric, int]:
        """
        获取用户成就指标值

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        return {
            PomodoroAchievementMetric.total_focus_hours: await PomodoroAchievementService._sum_focus_hours(
                db=db,
                user_id=user_id,
            ),
            PomodoroAchievementMetric.focus_streak_days: await PomodoroAchievementService._count_focus_streak_days(
                db=db,
                user_id=user_id,
            ),
            PomodoroAchievementMetric.habit_streak_days: await PomodoroAchievementService._count_habit_streak_days(
                db=db,
                user_id=user_id,
            ),
            PomodoroAchievementMetric.completed_pomodoro_count: (
                await PomodoroAchievementService._count_completed_pomodoro(db=db, user_id=user_id)
            ),
        }

    @staticmethod
    async def _sum_focus_hours(*, db: AsyncSession, user_id: int) -> int:
        """
        统计累计专注小时数

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        stmt = select(func.coalesce(func.sum(PomodoroFocusSession.focused_seconds), 0)).where(
            PomodoroFocusSession.user_id == user_id,
            PomodoroFocusSession.status == PomodoroFocusStatus.completed.value,
        )
        result = await db.execute(stmt)
        focused_seconds = int(result.scalar() or 0)
        return focused_seconds // 3600

    @staticmethod
    async def _count_completed_pomodoro(*, db: AsyncSession, user_id: int) -> int:
        """
        统计完成番茄数

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        stmt = select(func.count(PomodoroFocusSession.id)).where(
            PomodoroFocusSession.user_id == user_id,
            PomodoroFocusSession.status == PomodoroFocusStatus.completed.value,
            PomodoroFocusSession.mode == PomodoroFocusMode.pomodoro.value,
        )
        result = await db.execute(stmt)
        return int(result.scalar() or 0)

    @staticmethod
    async def _count_focus_streak_days(*, db: AsyncSession, user_id: int) -> int:
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
        return PomodoroAchievementService._count_streak_days(focus_dates)

    @staticmethod
    async def _count_habit_streak_days(*, db: AsyncSession, user_id: int) -> int:
        """
        统计连续习惯打卡天数

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        stmt = (
            select(distinct(PomodoroHabitCheckin.checkin_date))
            .where(PomodoroHabitCheckin.user_id == user_id)
            .order_by(PomodoroHabitCheckin.checkin_date.desc())
            .limit(366)
        )
        result = await db.execute(stmt)
        checkin_dates = [item for item in result.scalars().all() if item]
        return PomodoroAchievementService._count_streak_days(checkin_dates)

    @staticmethod
    def _count_streak_days(values: list[date | datetime | str]) -> int:
        """
        统计连续天数

        :param values: 日期列表
        :return:
        """
        if not values:
            return 0

        current_date = timezone.now().date()
        normalized_dates = {PomodoroAchievementService._normalize_date(item) for item in values}
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
    async def _update_progress(
        *,
        db: AsyncSession,
        user_achievement: PomodoroUserAchievement,
        current_value: int,
    ) -> None:
        """
        更新成就进度快照

        :param db: 数据库会话
        :param user_achievement: 用户成就
        :param current_value: 当前进度值
        :return:
        """
        if current_value <= user_achievement.progress_value:
            return

        await pomodoro_user_achievement_dao.update_model(
            db,
            user_achievement.id,
            {'progress_value': current_value},
            commit=False,
        )

    @staticmethod
    def _build_item(
        *,
        rule: PomodoroAchievementRule,
        user_achievement: PomodoroUserAchievement | None,
        current_value: int,
    ) -> PomodoroAchievementItem:
        """
        构建成就列表项

        :param rule: 成就规则
        :param user_achievement: 用户成就
        :param current_value: 当前进度值
        :return:
        """
        progress_percent = 0.0
        if rule.threshold_value > 0:
            progress_percent = round(min(100.0, current_value / rule.threshold_value * 100), 1)

        claimed = False
        if user_achievement:
            claimed = user_achievement.status == PomodoroAchievementStatus.claimed.value

        return PomodoroAchievementItem(
            rule=rule,
            user_achievement=user_achievement,
            current_value=current_value,
            progress_percent=progress_percent,
            achieved=user_achievement is not None,
            claimed=claimed,
        )

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


pomodoro_achievement_service: PomodoroAchievementService = PomodoroAchievementService()
