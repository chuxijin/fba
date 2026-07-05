#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy import func, select as sa_select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.gongkao.crud.crud_hanyu_checkin import hanyu_checkin_dao
from backend.app.gongkao.crud.crud_hanyu_user_setting import hanyu_user_setting_dao
from backend.app.gongkao.model import GkHanyuCheckin
from backend.app.gongkao.schema.hanyu_checkin import (
    HanyuCheckinHistoryItem,
    HanyuCheckinInfo,
    HanyuCheckinToday,
    HanyuStreakInfo,
)
from backend.utils.timezone import timezone


class HanyuCheckinService:
    """汉语学习打卡服务类"""

    @staticmethod
    async def update_daily_progress(
        *,
        db: AsyncSession,
        user_id: int,
        is_new_word: bool,
        duration_ms: int,
    ) -> None:
        """
        更新每日学习进度

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param is_new_word: 是否为新词
        :param duration_ms: 本次耗时(毫秒)
        :return:
        """
        today = timezone.now().date()
        record = await hanyu_checkin_dao.get_by_user_and_date(db, user_id, today)

        if record:
            update_data: dict = {
                'duration_seconds': record.duration_seconds + max(0, duration_ms // 1000),
            }
            if is_new_word:
                update_data['new_words'] = record.new_words + 1
            else:
                update_data['review_words'] = record.review_words + 1

            setting = await hanyu_user_setting_dao.get_or_create(db, user_id)
            new_total = update_data.get('new_words', record.new_words)
            if new_total >= setting.daily_new_target and record.streak_days == 0:
                yesterday = await hanyu_checkin_dao.get_yesterday(db, user_id, today)
                update_data['streak_days'] = (yesterday.streak_days + 1) if yesterday else 1

            await hanyu_checkin_dao.update_model(db, record.id, update_data)
        else:
            await hanyu_checkin_dao.create_model(
                db,
                {
                    'user_id': user_id,
                    'checkin_date': today,
                    'new_words': 1 if is_new_word else 0,
                    'review_words': 0 if is_new_word else 1,
                    'duration_seconds': max(0, duration_ms // 1000),
                    'streak_days': 0,
                },
            )

    @staticmethod
    async def get_today_status(*, db: AsyncSession, user_id: int) -> HanyuCheckinToday:
        """
        获取今日打卡状态

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        now = timezone.now()
        today = now.date()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start.replace(hour=23, minute=59, second=59)

        setting = await hanyu_user_setting_dao.get_or_create(db, user_id)
        record = await hanyu_checkin_dao.get_by_user_and_date(db, user_id, today)

        from backend.app.gongkao.crud.crud_hanyu_review_log import hanyu_review_log_dao
        from backend.app.gongkao.crud.crud_hanyu_user_word import hanyu_user_word_dao

        real_stats = await hanyu_review_log_dao.count_today(db, user_id, today_start, today_end)
        real_new = await hanyu_user_word_dao.count_today_new(db, user_id, today_start, today_end)
        total_unique_words = real_stats.get('total_words', 0)
        real_review = max(0, total_unique_words - real_new)
        real_duration = real_stats.get('total_duration_ms', 0) // 1000

        progress = min(100.0, (real_new / max(1, setting.daily_new_target)) * 100)

        streak_days = record.streak_days if record else 0
        is_checked_in = streak_days > 0

        return HanyuCheckinToday(
            is_checked_in=is_checked_in,
            new_words=real_new,
            review_words=real_review,
            duration_seconds=real_duration,
            streak_days=streak_days,
            daily_target=setting.daily_new_target,
            progress_percent=round(progress, 1),
        )

    @staticmethod
    async def get_streak_info(*, db: AsyncSession, user_id: int) -> HanyuStreakInfo:
        """
        获取连续打卡信息

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        today = timezone.now().date()
        current_streak = await hanyu_checkin_dao.get_current_streak(db, user_id, today)

        count_stmt = sa_select(func.count()).where(
            GkHanyuCheckin.user_id == user_id,
            GkHanyuCheckin.streak_days > 0,
        )
        result = await db.execute(count_stmt)
        total_checkins = result.scalar() or 0

        return HanyuStreakInfo(current_streak=current_streak, total_checkins=total_checkins)

    @staticmethod
    async def get_checkin_history(
        *,
        db: AsyncSession,
        user_id: int,
        year: int,
        month: int,
    ) -> list[HanyuCheckinHistoryItem]:
        """
        获取打卡历史

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param year: 年份
        :param month: 月份
        :return:
        """
        stmt = await hanyu_checkin_dao.get_select_by_user(user_id, year, month)
        result = await db.execute(stmt)
        records = result.scalars().all()
        return [
            HanyuCheckinHistoryItem(
                checkin_date=r.checkin_date,
                new_words=r.new_words,
                review_words=r.review_words,
                duration_seconds=r.duration_seconds,
                streak_days=r.streak_days,
            )
            for r in records
        ]


hanyu_checkin_service: HanyuCheckinService = HanyuCheckinService()
