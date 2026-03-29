#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from collections.abc import Sequence

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.membership.model.tier_entitlement import MembershipTierEntitlement


class CRUDMembershipTierEntitlement(CRUDPlus[MembershipTierEntitlement]):
    """等级权益映射数据库操作类"""

    async def get_by_tier(self, db: AsyncSession, tier_id: int) -> Sequence[MembershipTierEntitlement]:
        """
        获取等级映射权益

        :param db: 数据库会话
        :param tier_id: 等级 ID
        :return:
        """
        stmt = (
            select(self.model)
            .where(self.model.tier_id == tier_id, self.model.status == 1)
            .order_by(self.model.id.asc())
        )
        result = await db.execute(stmt)
        return result.scalars().all()

    async def get_by_tier_and_code(
        self,
        db: AsyncSession,
        *,
        tier_id: int,
        entitlement_code: str,
    ) -> MembershipTierEntitlement | None:
        """
        获取等级下单个权益映射

        :param db: 数据库会话
        :param tier_id: 等级 ID
        :param entitlement_code: 权益编码
        :return:
        """
        return await self.select_model_by_column(
            db,
            tier_id__eq=tier_id,
            entitlement_code__eq=entitlement_code,
            status__eq=1,
        )

    async def delete_by_tier(self, db: AsyncSession, tier_id: int) -> None:
        """
        删除等级下全部权益映射

        :param db: 数据库会话
        :param tier_id: 等级 ID
        :return:
        """
        stmt = delete(self.model).where(self.model.tier_id == tier_id)
        await db.execute(stmt)


membership_tier_entitlement_dao: CRUDMembershipTierEntitlement = CRUDMembershipTierEntitlement(MembershipTierEntitlement)
