#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy import Select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.plugin.webhook.model.webhook_event_type import WebhookEventType
from backend.plugin.webhook.schema.event_type import (
    CreateEventTypeParam,
    EventTypeListParam,
    UpdateEventTypeParam,
)


class CRUDEventType(CRUDPlus[WebhookEventType]):
    """事件类型注册数据库操作类"""

    async def get(self, db: AsyncSession, pk: int) -> WebhookEventType | None:
        """
        获取事件类型详情

        :param db: 数据库会话
        :param pk: 主键 ID
        :return:
        """
        return await self.select_model(db, pk)

    async def get_by_type_key(self, db: AsyncSession, type_key: str) -> WebhookEventType | None:
        """
        根据类型标识获取事件类型

        :param db: 数据库会话
        :param type_key: 事件类型标识
        :return:
        """
        return await self.select_model_by_column(db, type_key=type_key)

    async def get_list(self, params: EventTypeListParam | None = None) -> Select:
        """
        获取事件类型列表

        :param params: 查询参数
        :return:
        """
        filters = []

        if params:
            if params.category:
                filters.append(self.model.category == params.category)
            if params.is_active is not None:
                filters.append(self.model.is_active == params.is_active)

        if filters:
            return await self.select_order('created_time', 'desc', *filters)
        return await self.select_order('created_time', 'desc')

    async def create(self, db: AsyncSession, obj: CreateEventTypeParam) -> WebhookEventType:
        """
        创建事件类型

        :param db: 数据库会话
        :param obj: 创建参数
        :return:
        """
        return await self.create_model(db, obj)

    async def update(self, db: AsyncSession, pk: int, obj: UpdateEventTypeParam) -> int:
        """
        更新事件类型

        :param db: 数据库会话
        :param pk: 主键 ID
        :param obj: 更新参数
        :return:
        """
        return await self.update_model(db, pk, obj)

    async def delete(self, db: AsyncSession, pks: list[int]) -> int:
        """
        批量删除事件类型

        :param db: 数据库会话
        :param pks: 主键列表
        :return:
        """
        return await self.delete_model_by_column(db, allow_multiple=True, id__in=pks)

    async def get_active_types(self, db: AsyncSession) -> list[str]:
        """
        获取所有活跃的事件类型标识列表

        :param db: 数据库会话
        :return:
        """
        models = await self.select_models(db, self.model.is_active.is_(True))
        return [m.type_key for m in models]


crud_event_type: CRUDEventType = CRUDEventType(WebhookEventType)
