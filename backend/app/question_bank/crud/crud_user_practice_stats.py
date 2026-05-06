#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import date

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.question_bank.model.statistics import UserPracticeStats
from backend.utils.timezone import timezone


class CRUDUserPracticeStats(CRUDPlus[UserPracticeStats]):
    """用户刷题统计快照数据库操作类"""

    async def get_by_user(self, db: AsyncSession, user_id: int) -> UserPracticeStats | None:
        """获取用户统计快照"""
        return await self.select_model_by_column(db, user_id=user_id)

    async def get_or_create(self, db: AsyncSession, user_id: int) -> UserPracticeStats:
        """
        获取或创建用户统计快照

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        stats = await self.get_by_user(db, user_id)
        if stats:
            return stats

        new_stats = UserPracticeStats(user_id=user_id)
        db.add(new_stats)
        await db.flush()
        await db.refresh(new_stats)
        return new_stats

    async def increment(
        self,
        db: AsyncSession,
        user_id: int,
        *,
        answered: int = 0,
        correct: int = 0,
        duration: int = 0,
    ) -> None:
        """
        增量更新用户统计快照

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param answered: 新增答题数
        :param correct: 新增正确数
        :param duration: 新增答题时长（秒）
        """
        stats = await self.get_or_create(db, user_id)
        today = timezone.now().date()

        update_data: dict = {
            'total_count': UserPracticeStats.total_count + answered,
            'correct_count': UserPracticeStats.correct_count + correct,
            'total_duration': UserPracticeStats.total_duration + duration,
        }

        # 如果今天还没有练习记录，练习天数 +1
        if stats.last_practice_date != today:
            update_data['practice_days'] = UserPracticeStats.practice_days + 1
            update_data['last_practice_date'] = today

        stmt = (
            update(UserPracticeStats)
            .where(UserPracticeStats.id == stats.id)
            .values(**update_data)
        )
        await db.execute(stmt)
        await db.flush()

    async def rebuild(
        self,
        db: AsyncSession,
        user_id: int,
        *,
        total_count: int,
        correct_count: int,
        total_duration: int,
        practice_days: int,
        last_practice_date: date | None,
    ) -> None:
        """
        全量重建用户统计快照

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param total_count: 累计答题数
        :param correct_count: 累计答对数
        :param total_duration: 累计答题时长
        :param practice_days: 练习天数
        :param last_practice_date: 最后练习日期
        """
        stats = await self.get_or_create(db, user_id)
        stmt = (
            update(UserPracticeStats)
            .where(UserPracticeStats.id == stats.id)
            .values(
                total_count=total_count,
                correct_count=correct_count,
                total_duration=total_duration,
                practice_days=practice_days,
                last_practice_date=last_practice_date,
            )
        )
        await db.execute(stmt)
        await db.flush()


user_practice_stats_dao: CRUDUserPracticeStats = CRUDUserPracticeStats(UserPracticeStats)
