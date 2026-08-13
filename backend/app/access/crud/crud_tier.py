#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy import Select, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.access.constants import CommonStatus
from backend.app.access.model.tier import MembershipTier


class CRUDMembershipTier(CRUDPlus[MembershipTier]):
    """会员档位 CRUD"""

    async def get_by_code(self, db: AsyncSession, code: str) -> MembershipTier | None:
        """按编码获取会员档位"""
        stmt = select(self.model).where(self.model.code == code.upper())
        return (await db.execute(stmt)).scalars().first()

    async def get_select(
        self,
        *,
        keyword: str | None = None,
        status: CommonStatus | None = None,
    ) -> Select:
        """获取会员档位分页查询语句"""
        stmt = select(self.model)
        if keyword:
            pattern = f'%{keyword}%'
            stmt = stmt.where(or_(self.model.code.ilike(pattern), self.model.name.ilike(pattern)))
        if status is not None:
            stmt = stmt.where(self.model.status == status)
        return stmt.order_by(self.model.display_order.asc(), self.model.weight.asc(), self.model.id.asc())


membership_tier_dao: CRUDMembershipTier = CRUDMembershipTier(MembershipTier)
