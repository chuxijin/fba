#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.growth.model.event import GrowthEvent


class CRUDGrowthEvent(CRUDPlus[GrowthEvent]):
    """成长事件 CRUD"""

    async def get_by_idempotency_key(self, db: AsyncSession, idempotency_key: str) -> GrowthEvent | None:
        """
        通过幂等键查询事件

        :param db: 数据库会话
        :param idempotency_key: 幂等键
        :return:
        """
        stmt = select(self.model).where(self.model.idempotency_key == idempotency_key)
        return (await db.execute(stmt)).scalars().first()

    async def list_by_user(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        limit: int = 50,
    ) -> list[GrowthEvent]:
        """
        查询用户成长流水

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param limit: 数量上限
        :return:
        """
        stmt = (
            select(self.model)
            .where(self.model.user_id == user_id)
            .order_by(self.model.occurred_at.desc(), self.model.id.desc())
            .limit(limit)
        )
        return list((await db.execute(stmt)).scalars().all())

    async def get_select(
        self,
        *,
        user_id: int | None = None,
        operation: str | None = None,
        source: str | None = None,
    ) -> Select:
        """构建成长流水分页查询"""
        filters: dict[str, object] = {}
        if user_id is not None:
            filters['user_id__eq'] = user_id
        if operation is not None:
            filters['operation__eq'] = operation
        if source is not None:
            filters['source__eq'] = source
        return await self.select_order('occurred_at', 'desc', **filters)


growth_event_dao: CRUDGrowthEvent = CRUDGrowthEvent(GrowthEvent)
