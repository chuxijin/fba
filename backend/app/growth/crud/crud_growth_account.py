#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.growth.model.account import GrowthAccount


class CRUDGrowthAccount(CRUDPlus[GrowthAccount]):
    """成长账户 CRUD"""

    async def get_by_user_and_family(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        family_code: str,
        for_update: bool = False,
    ) -> GrowthAccount | None:
        """
        获取用户在指定族群的账户

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param family_code: 族群
        :param for_update: 是否加行锁
        :return:
        """
        stmt = select(self.model).where(
            self.model.user_id == user_id,
            self.model.family_code == family_code,
        )
        if for_update:
            stmt = stmt.with_for_update()
        return (await db.execute(stmt)).scalars().first()

    async def list_by_user(self, db: AsyncSession, user_id: int) -> Sequence[GrowthAccount]:
        """
        列出用户所有族群的账户

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        stmt = select(self.model).where(self.model.user_id == user_id)
        return (await db.execute(stmt)).scalars().all()


growth_account_dao: CRUDGrowthAccount = CRUDGrowthAccount(GrowthAccount)
