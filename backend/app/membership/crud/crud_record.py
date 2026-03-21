#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from collections.abc import Sequence

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.membership.model.record import MembershipRecord


class CRUDMembershipRecord(CRUDPlus[MembershipRecord]):
    """会员变动记录数据库操作类"""

    async def get_by_user(self, db: AsyncSession, user_id: int) -> Sequence[MembershipRecord]:
        """
        获取用户所有变动记录

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        stmt = (
            select(self.model)
            .where(self.model.user_id == user_id)
            .order_by(self.model.created_time.desc())
        )
        result = await db.execute(stmt)
        return result.scalars().all()

    async def get_by_user_and_plan(
        self, db: AsyncSession, user_id: int, plan_id: int
    ) -> Sequence[MembershipRecord]:
        """
        获取用户某个计划的变动记录

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param plan_id: 会员计划 ID
        :return:
        """
        stmt = (
            select(self.model)
            .where(self.model.user_id == user_id, self.model.plan_id == plan_id)
            .order_by(self.model.created_time.desc())
        )
        result = await db.execute(stmt)
        return result.scalars().all()

    async def get_select(
        self,
        *,
        user_id: int | None = None,
        plan_id: int | None = None,
        source: str | None = None,
    ) -> Select:
        """
        获取变动记录分页查询语句

        :param user_id: 用户 ID
        :param plan_id: 会员计划 ID
        :param source: 来源标识
        :return:
        """
        filters = {}
        if user_id is not None:
            filters['user_id__eq'] = user_id
        if plan_id is not None:
            filters['plan_id__eq'] = plan_id
        if source is not None:
            filters['source__eq'] = source
        return await self.select_order('created_time', 'desc', **filters)


membership_record_dao: CRUDMembershipRecord = CRUDMembershipRecord(MembershipRecord)
