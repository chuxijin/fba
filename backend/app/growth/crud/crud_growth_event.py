#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.growth.model.event import GrowthEvent


class CRUDGrowthEvent(CRUDPlus[GrowthEvent]):
    """成长事件 CRUD"""

    async def get_by_idempotency_key(
        self, db: AsyncSession, idempotency_key: str
    ) -> GrowthEvent | None:
        """
        通过幂等键查询事件

        :param db: 数据库会话
        :param idempotency_key: 幂等键
        :return:
        """
        stmt = select(self.model).where(self.model.idempotency_key == idempotency_key)
        return (await db.execute(stmt)).scalars().first()


growth_event_dao: CRUDGrowthEvent = CRUDGrowthEvent(GrowthEvent)
