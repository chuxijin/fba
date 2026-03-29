#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from collections.abc import Sequence

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.membership.model.entitlement import MembershipEntitlement


class CRUDMembershipEntitlement(CRUDPlus[MembershipEntitlement]):
    """会员权益数据库操作类"""

    async def get_select(
        self,
        *,
        name: str | None = None,
        status: int | None = None,
    ) -> Select:
        """
        获取权益分页查询语句

        :param name: 权益名称
        :param status: 状态
        :return:
        """
        filters = {}
        if name is not None:
            filters['name__like'] = name
        if status is not None:
            filters['status__eq'] = status
        return await self.select_order('sort', 'asc', **filters)

    async def get_by_code(self, db: AsyncSession, code: str) -> MembershipEntitlement | None:
        """
        根据编码获取权益

        :param db: 数据库会话
        :param code: 权益编码
        :return:
        """
        return await self.select_model_by_column(db, code__eq=code)

    async def get_active_list(self, db: AsyncSession) -> Sequence[MembershipEntitlement]:
        """
        获取启用权益

        :param db: 数据库会话
        :return:
        """
        stmt = (
            select(self.model)
            .where(self.model.status == 1)
            .order_by(self.model.sort.asc(), self.model.id.asc())
        )
        result = await db.execute(stmt)
        return result.scalars().all()


membership_entitlement_dao: CRUDMembershipEntitlement = CRUDMembershipEntitlement(MembershipEntitlement)
