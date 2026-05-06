#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.membership.model.usage_counter import MembershipUsageCounter


class CRUDMembershipUsageCounter(CRUDPlus[MembershipUsageCounter]):
    """会员权益用量计数数据库操作类"""

    async def get_select(
        self,
        *,
        user_id: int | None = None,
        entitlement_code: str | None = None,
        scope_key: str | None = None,
        cycle_type: str | None = None,
        cycle_key: str | None = None,
    ) -> Select:
        """
        获取用量计数分页查询语句

        :param user_id: 用户 ID
        :param entitlement_code: 权益编码
        :param scope_key: 业务范围键
        :param cycle_type: 周期类型
        :param cycle_key: 周期键
        :return:
        """
        filters = {}
        if user_id is not None:
            filters['user_id__eq'] = user_id
        if entitlement_code is not None:
            filters['entitlement_code__eq'] = entitlement_code
        if scope_key is not None:
            filters['scope_key__eq'] = scope_key
        if cycle_type is not None:
            filters['cycle_type__eq'] = cycle_type
        if cycle_key is not None:
            filters['cycle_key__eq'] = cycle_key
        return await self.select_order('created_time', 'desc', **filters)

    async def get_by_scope(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        entitlement_code: str,
        scope_key: str,
        cycle_type: str,
        cycle_key: str,
        for_update: bool = False,
    ) -> MembershipUsageCounter | None:
        """
        按计数范围获取用量

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param entitlement_code: 权益编码
        :param scope_key: 业务范围键
        :param cycle_type: 周期类型
        :param cycle_key: 周期键
        :param for_update: 是否锁定行
        :return:
        """
        stmt = select(self.model).where(
            self.model.user_id == user_id,
            self.model.entitlement_code == entitlement_code,
            self.model.scope_key == scope_key,
            self.model.cycle_type == cycle_type,
            self.model.cycle_key == cycle_key,
        )
        if for_update:
            stmt = stmt.with_for_update()

        result = await db.execute(stmt)
        return result.scalars().first()


membership_usage_counter_dao: CRUDMembershipUsageCounter = CRUDMembershipUsageCounter(MembershipUsageCounter)
