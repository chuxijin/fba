#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.vocab.crud.crud_checkin import checkin_dao
from backend.app.vocab.crud.crud_user_setting import user_setting_dao
from backend.app.vocab.schema.checkin import GetCheckinToday, GetStreakInfo
from backend.utils.timezone import timezone


class CheckinService:
    """打卡服务类"""

    @staticmethod
    async def update_daily_progress(
        *,
        db: AsyncSession,
        user_id: int,
        is_new_word: bool,
        duration_ms: int,
    ) -> None:
        """
        更新每日学习进度（由 review_service 调用）

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param is_new_word: 是否为新词
        :param duration_ms: 本次耗时(毫秒)
        :return:
        """
        today = timezone.now().date()
        record = await checkin_dao.get_by_user_and_date(db, user_id, today)

        if record:
            update_data: dict = {
                'duration_seconds': record.duration_seconds + max(0, duration_ms // 1000),
            }
            if is_new_word:
                update_data['new_words'] = record.new_words + 1
            else:
                update_data['review_words'] = record.review_words + 1

            # 检查是否达到打卡条件
            setting = await user_setting_dao.get_or_create(db, user_id)
            new_total = update_data.get('new_words', record.new_words)
            if new_total >= setting.daily_new_target and record.streak_days == 0:
                yesterday = await checkin_dao.get_yesterday(db, user_id, today)
                update_data['streak_days'] = (yesterday.streak_days + 1) if yesterday else 1

            await checkin_dao.update_model(db, record.id, update_data)
        else:
            # 首次学习，创建记录
            checkin_data = {
                'user_id': user_id,
                'checkin_date': today,
                'new_words': 1 if is_new_word else 0,
                'review_words': 0 if is_new_word else 1,
                'duration_seconds': max(0, duration_ms // 1000),
                'streak_days': 0,
            }
            await checkin_dao.create_model(db, checkin_data)

    @staticmethod
    async def get_today_status(*, db: AsyncSession, user_id: int) -> GetCheckinToday:
        """
        获取今日打卡状态

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        today = timezone.now().date()
        setting = await user_setting_dao.get_or_create(db, user_id)
        record = await checkin_dao.get_by_user_and_date(db, user_id, today)

        if not record:
            return GetCheckinToday(
                is_checked_in=False,
                daily_target=setting.daily_new_target,
            )

        progress = min(100.0, (record.new_words / max(1, setting.daily_new_target)) * 100)
        return GetCheckinToday(
            is_checked_in=record.streak_days > 0,
            new_words=record.new_words,
            review_words=record.review_words,
            duration_seconds=record.duration_seconds,
            streak_days=record.streak_days,
            daily_target=setting.daily_new_target,
            progress_percent=round(progress, 1),
        )

    @staticmethod
    async def get_streak_info(*, db: AsyncSession, user_id: int) -> GetStreakInfo:
        """
        获取连续打卡信息

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        today = timezone.now().date()
        current_streak = await checkin_dao.get_current_streak(db, user_id, today)
        # 简单统计总打卡天数
        stmt = await checkin_dao.get_select_by_user(user_id)
        from sqlalchemy import func, select as sa_select
        from backend.app.vocab.model import VocabCheckin
        count_stmt = sa_select(func.count()).where(
            VocabCheckin.user_id == user_id,
            VocabCheckin.streak_days > 0,
        )
        result = await db.execute(count_stmt)
        total_checkins = result.scalar() or 0

        return GetStreakInfo(current_streak=current_streak, total_checkins=total_checkins)


checkin_service: CheckinService = CheckinService()
