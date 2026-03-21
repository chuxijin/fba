#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from collections.abc import Sequence

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.membership.model.plan import MembershipPlan


class CRUDMembershipPlan(CRUDPlus[MembershipPlan]):
    """会员计划数据库操作类"""

    async def get_select(
        self,
        *,
        name: str | None = None,
        status: int | None = None,
    ) -> Select:
        """
        获取会员计划分页查询语句

        :param name: 计划名称（模糊搜索）
        :param status: 状态
        :return:
        """
        filters = {}
        if name is not None:
            filters['name__like'] = name
        if status is not None:
            filters['status__eq'] = status
        return await self.select_order('sort', 'asc', **filters)

    async def get_by_name(self, db: AsyncSession, name: str) -> MembershipPlan | None:
        """
        根据名称获取计划

        :param db: 数据库会话
        :param name: 计划名称
        :return:
        """
        return await self.select_model_by_column(db, name__eq=name)

    async def get_active_plans(self, db: AsyncSession) -> Sequence[MembershipPlan]:
        """获取所有上架的计划"""
        stmt = (
            select(self.model)
            .where(self.model.status == 1)
            .order_by(self.model.sort.asc(), self.model.level.asc())
        )
        result = await db.execute(stmt)
        return result.scalars().all()


membership_plan_dao: CRUDMembershipPlan = CRUDMembershipPlan(MembershipPlan)
