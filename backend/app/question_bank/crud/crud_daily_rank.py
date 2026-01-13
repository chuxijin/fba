#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.question_bank.model import UserDailyRank


class CRUDDailyRank(CRUDPlus[UserDailyRank]):
    """用户每日排名数据库操作类"""

    async def get_by_user_and_date(
        self, db: AsyncSession, user_id: int, rank_date: date
    ) -> UserDailyRank | None:
        """
        获取用户指定日期的排名记录

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param rank_date: 排名日期
        :return:
        """
        return await self.select_model_by_column(db, user_id=user_id, rank_date=rank_date)

    async def get_latest_rank(self, db: AsyncSession, user_id: int) -> UserDailyRank | None:
        """
        获取用户最近的排名记录

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        stmt = (
            select(UserDailyRank)
            .where(UserDailyRank.user_id == user_id)
            .order_by(UserDailyRank.rank_date.desc())
            .limit(1)
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def create_rank_record(
        self,
        db: AsyncSession,
        user_id: int,
        rank_date: date,
        rank: int,
        total_users: int,
        beat_percentage: Decimal,
        practice_count: int,
        correct_count: int,
        accuracy_rate: Decimal,
    ) -> UserDailyRank:
        """
        创建排名记录

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param rank_date: 排名日期
        :param rank: 排名
        :param total_users: 总用户数
        :param beat_percentage: 击败百分比
        :param practice_count: 练习数量
        :param correct_count: 答对数量
        :param accuracy_rate: 正确率
        :return:
        """
        new_rank = self.model(
            user_id=user_id,
            rank_date=rank_date,
            rank=rank,
            total_users=total_users,
            beat_percentage=beat_percentage,
            practice_count=practice_count,
            correct_count=correct_count,
            accuracy_rate=accuracy_rate,
        )
        db.add(new_rank)
        await db.flush()
        await db.refresh(new_rank)
        return new_rank


daily_rank_dao: CRUDDailyRank = CRUDDailyRank(UserDailyRank)
