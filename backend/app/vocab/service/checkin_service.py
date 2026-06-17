#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.vocab.crud.crud_checkin import checkin_dao
from backend.app.vocab.crud.crud_user_setting import user_setting_dao
from backend.app.vocab.schema.checkin import CreateCheckinParam, GetCheckinToday, GetStreakInfo
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
            checkin = CreateCheckinParam(
                user_id=user_id,
                checkin_date=today,
                new_words=1 if is_new_word else 0,
                review_words=0 if is_new_word else 1,
                duration_seconds=max(0, duration_ms // 1000),
                streak_days=0,
            )
            await checkin_dao.create_model(db, checkin)

    @staticmethod
    async def get_today_status(*, db: AsyncSession, user_id: int) -> GetCheckinToday:
        """
        获取今日打卡状态
        """
        now = timezone.now()
        today = now.date()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start.replace(hour=23, minute=59, second=59)

        setting = await user_setting_dao.get_or_create(db, user_id)
        record = await checkin_dao.get_by_user_and_date(db, user_id, today)

        from backend.app.vocab.crud.crud_review_log import review_log_dao
        from backend.app.vocab.crud.crud_user_word import user_word_dao

        real_stats = await review_log_dao.count_today(db, user_id, today_start, today_end)
        real_new = await user_word_dao.count_today_new(db, user_id, today_start, today_end)
        total_unique_words = real_stats.get('total_words', 0)
        # 复习数 = 今天学过的去重总词数 - 今天才创建的词数
        real_review = max(0, total_unique_words - real_new)
        real_duration = real_stats.get('total_duration_ms', 0) // 1000

        progress = min(100.0, (real_new / max(1, setting.daily_new_target)) * 100)

        # 尝试自动触发打卡记录修正 (防止事务回滚导致的打卡表不同步)
        streak_days = record.streak_days if record else 0
        is_checked_in = streak_days > 0

        return GetCheckinToday(
            is_checked_in=is_checked_in,
            new_words=real_new,
            review_words=real_review,
            duration_seconds=real_duration,
            streak_days=streak_days,
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
        await checkin_dao.get_select_by_user(user_id)
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
