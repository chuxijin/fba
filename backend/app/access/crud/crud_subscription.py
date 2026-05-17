#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.access.constants import SubscriptionSource, SubscriptionStatus
from backend.app.access.model.subscription import Subscription


class CRUDSubscription(CRUDPlus[Subscription]):
    """用户订阅 CRUD"""

    async def list_active_for_user(
        self,
        db: AsyncSession,
        user_id: int,
        ts: datetime,
    ) -> Sequence[Subscription]:
        """
        列出用户在指定时刻有效的订阅

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param ts: 时间点
        :return:
        """
        stmt = (
            select(self.model)
            .where(
                self.model.user_id == user_id,
                self.model.status == SubscriptionStatus.ACTIVE,
                self.model.valid_period.contains(ts),
            )
        )
        return (await db.execute(stmt)).scalars().all()

    async def list_for_user(
        self,
        db: AsyncSession,
        user_id: int,
        *,
        status: SubscriptionStatus | None = None,
    ) -> Sequence[Subscription]:
        """
        列出用户的所有订阅

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param status: 状态过滤
        :return:
        """
        stmt = select(self.model).where(self.model.user_id == user_id)
        if status is not None:
            stmt = stmt.where(self.model.status == status)
        stmt = stmt.order_by(self.model.id.desc())
        return (await db.execute(stmt)).scalars().all()

    async def get_select(
        self,
        *,
        user_id: int | None = None,
        template_id: int | None = None,
        status: SubscriptionStatus | None = None,
        source: SubscriptionSource | None = None,
    ) -> Select:
        """
        分页查询语句

        :param user_id: 用户 ID
        :param template_id: 模板 ID
        :param status: 状态
        :param source: 来源
        :return:
        """
        filters: dict[str, object] = {}
        if user_id is not None:
            filters['user_id__eq'] = user_id
        if template_id is not None:
            filters['template_id__eq'] = template_id
        if status is not None:
            filters['status__eq'] = status
        if source is not None:
            filters['source__eq'] = source
        return await self.select_order('id', 'desc', **filters)


subscription_dao: CRUDSubscription = CRUDSubscription(Subscription)
