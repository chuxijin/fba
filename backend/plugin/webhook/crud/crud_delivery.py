#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Sequence

from sqlalchemy import Select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.plugin.webhook.model.webhook_delivery import WebhookDelivery
from backend.plugin.webhook.schema.delivery import DeliveryListParam


class CRUDDelivery(CRUDPlus[WebhookDelivery]):
    """投递记录数据库操作类"""

    async def get(self, db: AsyncSession, pk: int) -> WebhookDelivery | None:
        """
        获取投递记录详情

        :param db: 数据库会话
        :param pk: 主键 ID
        :return:
        """
        return await self.select_model(db, pk)

    async def get_by_uid(self, db: AsyncSession, uid: str) -> WebhookDelivery | None:
        """
        根据 UID 获取投递记录

        :param db: 数据库会话
        :param uid: 投递唯一标识
        :return:
        """
        return await self.select_model_by_column(db, uid=uid)

    async def get_list(self, params: DeliveryListParam | None = None) -> Select:
        """
        获取投递记录列表

        :param params: 查询参数
        :return:
        """
        filters = []

        if params:
            if params.endpoint_id is not None:
                filters.append(self.model.endpoint_id == params.endpoint_id)
            if params.event_type:
                filters.append(self.model.event_type.like(f'%{params.event_type}%'))
            if params.status is not None:
                filters.append(self.model.status == params.status)
            if params.start_time:
                filters.append(self.model.created_time >= params.start_time)
            if params.end_time:
                filters.append(self.model.created_time <= params.end_time)

        if filters:
            return await self.select_order('created_time', 'desc', *filters)
        return await self.select_order('created_time', 'desc')

    async def get_pending(self, db: AsyncSession, limit: int = 50) -> Sequence[WebhookDelivery]:
        """
        获取待投递的记录

        :param db: 数据库会话
        :param limit: 限制数量
        :return:
        """
        from backend.plugin.webhook.constant import DeliveryStatus

        filters = and_(
            self.model.status == DeliveryStatus.PENDING,
        )
        return await self.select_models(db, filters, limit=limit)

    async def get_retryable(self, db: AsyncSession, limit: int = 50) -> Sequence[WebhookDelivery]:
        """
        获取可重试的记录 (状态为 RETRYING 且已到重试时间)

        :param db: 数据库会话
        :param limit: 限制数量
        :return:
        """
        from backend.plugin.webhook.constant import DeliveryStatus
        from backend.utils.timezone import timezone

        now = timezone.now()
        filters = and_(
            self.model.status == DeliveryStatus.RETRYING,
            self.model.next_retry_at <= now,
        )
        return await self.select_models(db, filters, limit=limit)

    async def exists_by_event_id(self, db: AsyncSession, event_id: str) -> bool:
        """
        检查事件 ID 是否已存在

        :param db: 数据库会话
        :param event_id: 事件 ID
        :return:
        """
        from sqlalchemy import exists, select

        stmt = select(exists().where(self.model.event_id == event_id))
        result = await db.execute(stmt)
        return result.scalar()


crud_delivery: CRUDDelivery = CRUDDelivery(WebhookDelivery)
