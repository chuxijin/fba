#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.growth.model.account import GrowthAccount


class CRUDGrowthAccount(CRUDPlus[GrowthAccount]):
    """成长账户 CRUD"""

    async def get_by_user(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        for_update: bool = False,
    ) -> GrowthAccount | None:
        """
        获取用户的成长账户

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param for_update: 是否加行锁
        :return:
        """
        stmt = select(self.model).where(self.model.user_id == user_id)
        if for_update:
            stmt = stmt.with_for_update()
        return (await db.execute(stmt)).scalars().first()


growth_account_dao: CRUDGrowthAccount = CRUDGrowthAccount(GrowthAccount)
