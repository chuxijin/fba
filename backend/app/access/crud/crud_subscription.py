#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import Row, Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.access.constants import SubscriptionSource, SubscriptionStatus
from backend.app.access.model.subscription import Subscription
from backend.utils.timezone import timezone


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
        分页查询语句 (联表查询，带关联信息)

        :param user_id: 用户 ID
        :param template_id: 模板 ID
        :param status: 状态
        :param source: 来源
        :return:
        """
        from backend.app.admin.model.user import User
        from backend.app.access.model.template import SubscriptionTemplate
        from sqlalchemy import func

        stmt = (
            select(
                Subscription.id,
                Subscription.user_id,
                Subscription.template_id,
                Subscription.valid_period,
                Subscription.status,
                Subscription.source,
                Subscription.source_ref,
                Subscription.parent_subscription_id,
                Subscription.cancel_reason,
                Subscription.created_time,
                Subscription.updated_time,
                User.username.label('username'),
                SubscriptionTemplate.code.label('template_code'),
                SubscriptionTemplate.name.label('template_name'),
                func.lower(Subscription.valid_period).label('valid_from'),
                func.upper(Subscription.valid_period).label('valid_to'),
            )
            .outerjoin(User, Subscription.user_id == User.id)
            .outerjoin(SubscriptionTemplate, Subscription.template_id == SubscriptionTemplate.id)
            .order_by(Subscription.id.desc())
        )

        if user_id is not None:
            stmt = stmt.where(Subscription.user_id == user_id)
        if template_id is not None:
            stmt = stmt.where(Subscription.template_id == template_id)
        if status is not None:
            stmt = stmt.where(Subscription.status == status)
        if source is not None:
            stmt = stmt.where(Subscription.source == source)

        return stmt

    async def get_detail(
        self,
        db: AsyncSession,
        pk: int,
    ) -> Row | None:
        """
        获取订阅详情 (带关联的用户名、模板和生效到期时间)

        :param db: 数据库会话
        :param pk: 订阅 ID
        :return:
        """
        from backend.app.admin.model.user import User
        from backend.app.access.model.template import SubscriptionTemplate
        from sqlalchemy import func

        stmt = (
            select(
                Subscription.id,
                Subscription.user_id,
                Subscription.template_id,
                Subscription.valid_period,
                Subscription.status,
                Subscription.source,
                Subscription.source_ref,
                Subscription.parent_subscription_id,
                Subscription.cancel_reason,
                Subscription.created_time,
                Subscription.updated_time,
                User.username.label('username'),
                SubscriptionTemplate.code.label('template_code'),
                SubscriptionTemplate.name.label('template_name'),
                func.lower(Subscription.valid_period).label('valid_from'),
                func.upper(Subscription.valid_period).label('valid_to'),
            )
            .outerjoin(User, Subscription.user_id == User.id)
            .outerjoin(SubscriptionTemplate, Subscription.template_id == SubscriptionTemplate.id)
            .where(Subscription.id == pk)
        )
        return (await db.execute(stmt)).first()


    async def expire_due(self, db: AsyncSession) -> int:
        """
        批量将已过期的 active 订阅标记为 expired

        :param db: 数据库会话
        :return: 受影响的行数
        """
        from sqlalchemy import func, update

        now = timezone.now()
        stmt = (
            update(self.model)
            .where(
                self.model.status == SubscriptionStatus.ACTIVE,
                func.upper(self.model.valid_period) <= now,
            )
            .values(status=SubscriptionStatus.EXPIRED)
        )
        result = await db.execute(stmt)
        return result.rowcount


subscription_dao: CRUDSubscription = CRUDSubscription(Subscription)
