#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import date, timedelta

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.vocab.model import VocabCheckin


class CRUDCheckin(CRUDPlus[VocabCheckin]):
    """打卡记录数据库操作类"""

    async def get_by_user_and_date(self, db: AsyncSession, user_id: int, checkin_date: date) -> VocabCheckin | None:
        """
        获取用户某天的打卡记录

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param checkin_date: 日期
        :return:
        """
        return await self.select_model_by_column(db, user_id__eq=user_id, checkin_date__eq=checkin_date)

    async def get_yesterday(self, db: AsyncSession, user_id: int, today: date) -> VocabCheckin | None:
        """
        获取用户昨天的打卡记录

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param today: 今天日期
        :return:
        """
        yesterday = today - timedelta(days=1)
        return await self.get_by_user_and_date(db, user_id, yesterday)

    async def get_current_streak(self, db: AsyncSession, user_id: int, today: date) -> int:
        """
        获取用户当前连续打卡天数

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param today: 今天日期
        :return:
        """
        today_record = await self.get_by_user_and_date(db, user_id, today)
        if today_record:
            return today_record.streak_days
        yesterday_record = await self.get_yesterday(db, user_id, today)
        if yesterday_record:
            return yesterday_record.streak_days
        return 0

    async def get_select_by_user(
        self,
        user_id: int,
        year: int | None = None,
        month: int | None = None,
    ) -> Select:
        """
        获取用户打卡记录列表

        :param user_id: 用户 ID
        :param year: 年份过滤
        :param month: 月份过滤
        :return:
        """
        stmt = select(VocabCheckin).where(VocabCheckin.user_id == user_id)
        if year and month:
            start_date = date(year, month, 1)
            if month == 12:
                end_date = date(year + 1, 1, 1)
            else:
                end_date = date(year, month + 1, 1)
            stmt = stmt.where(VocabCheckin.checkin_date >= start_date, VocabCheckin.checkin_date < end_date)
        return stmt.order_by(VocabCheckin.checkin_date.desc())


checkin_dao: CRUDCheckin = CRUDCheckin(VocabCheckin)
