#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Sequence

from sqlalchemy import Select, and_, desc, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.plugin.webhook.model import Webhook
from backend.plugin.webhook.model.webhook_config import WebhookConfig
from backend.plugin.webhook.schema.webhook import (
    CreateWebhookParam,
    UpdateWebhookParam,
    WebhookListParam,
    CreateWebhookConfigParam,
    UpdateWebhookConfigParam,
    WebhookConfigListParam,
)


class CRUDWebhook(CRUDPlus[Webhook]):
    """Webhook事件数据库操作类"""

    async def get(self, db: AsyncSession, pk: int) -> Webhook | None:
        """
        获取Webhook事件

        :param db: 数据库会话
        :param pk: Webhook事件 ID
        :return:
        """
        return await self.select_model(db, pk)

    async def get_list(self, params: WebhookListParam | None = None) -> Select:
        """
        获取Webhook事件列表

        :param params: 查询参数
        :return:
        """
        filters = []
        
        if params:
            if params.event_type:
                filters.append(self.model.event_type.like(f'%{params.event_type}%'))
            if params.source:
                filters.append(self.model.source.like(f'%{params.source}%'))
            if params.status is not None:
                filters.append(self.model.status == params.status)
            if params.start_time:
                filters.append(self.model.created_time >= params.start_time)
            if params.end_time:
                filters.append(self.model.created_time <= params.end_time)
        
        if filters:
            return await self.select_order('created_time', 'desc', *filters)
        return await self.select_order('created_time', 'desc')

    async def get_all(self, db: AsyncSession) -> Sequence[Webhook]:
        """
        获取所有Webhook事件

        :param db: 数据库会话
        :return:
        """
        return await self.select_models(db)

    async def create(self, db: AsyncSession, obj: CreateWebhookParam) -> Webhook:
        """
        创建Webhook事件

        :param db: 数据库会话
        :param obj: 创建Webhook事件参数
        :return:
        """
        return await self.create_model(db, obj)

    async def update(self, db: AsyncSession, pk: int, obj: UpdateWebhookParam) -> int:
        """
        更新Webhook事件

        :param db: 数据库会话
        :param pk: Webhook事件 ID
        :param obj: 更新Webhook事件参数
        :return:
        """
        return await self.update_model(db, pk, obj)

    async def delete(self, db: AsyncSession, pks: list[int]) -> int:
        """
        批量删除Webhook事件

        :param db: 数据库会话
        :param pks: Webhook事件 ID 列表
        :return:
        """
        return await self.delete_model_by_column(db, allow_multiple=True, id__in=pks)

    async def get_pending_webhooks(self, db: AsyncSession, limit: int = 100) -> Sequence[Webhook]:
        """
        获取待处理的Webhook事件

        :param db: 数据库会话
        :param limit: 限制数量
        :return:
        """
        return await self.select_models(db, self.model.status == 2, limit=limit)

    async def get_failed_webhooks(self, db: AsyncSession, max_retry: int = 3) -> Sequence[Webhook]:
        """
        获取失败且可重试的Webhook事件

        :param db: 数据库会话
        :param max_retry: 最大重试次数
        :return:
        """
        filters = and_(
            self.model.status == 0,
            self.model.retry_count < max_retry
        )
        return await self.select_models(db, filters)


webhook_dao: CRUDWebhook = CRUDWebhook(Webhook)


# ==================== WebhookConfig CRUD ====================

class CRUDWebhookConfig(CRUDPlus[WebhookConfig]):
    """WebhookConfig CRUD操作"""

    async def get(self, db: AsyncSession, pk: int) -> WebhookConfig | None:
        """
        获取WebhookConfig详情

        :param db: 数据库会话
        :param pk: 主键
        :return:
        """
        return await self.select_model(db, pk)

    async def get_list(self, params: WebhookConfigListParam | None = None) -> Select:
        """
        获取WebhookConfig列表

        :param params: 查询参数
        :return:
        """
        filters = []
        
        if params:
            if params.name:
                filters.append(self.model.name.like(f'%{params.name}%'))
            if params.endpoint_url:
                filters.append(self.model.endpoint_url.like(f'%{params.endpoint_url}%'))
            if params.is_active is not None:
                filters.append(self.model.is_active == params.is_active)
        
        if filters:
            return await self.select_order('created_time', 'desc', *filters)
        return await self.select_order('created_time', 'desc')

    async def get_all(self, db: AsyncSession) -> Sequence[WebhookConfig]:
        """
        获取所有WebhookConfig

        :param db: 数据库会话
        :return:
        """
        return await self.select_models(db)

    async def create(self, db: AsyncSession, obj: CreateWebhookConfigParam) -> WebhookConfig:
        """
        创建WebhookConfig

        :param db: 数据库会话
        :param obj: 创建参数
        :return:
        """
        return await self.create_model(db, obj)

    async def update(self, db: AsyncSession, pk: int, obj: UpdateWebhookConfigParam) -> int:
        """
        更新WebhookConfig

        :param db: 数据库会话
        :param pk: 主键
        :param obj: 更新参数
        :return:
        """
        return await self.update_model(db, pk, obj)

    async def delete(self, db: AsyncSession, pks: list[int]) -> int:
        """
        批量删除WebhookConfig

        :param db: 数据库会话
        :param pks: 主键列表
        :return:
        """
        return await self.delete_model_by_column(db, allow_multiple=True, id__in=pks)

    async def get_by_name(self, db: AsyncSession, name: str) -> WebhookConfig | None:
        """
        根据配置名称获取WebhookConfig

        :param db: 数据库会话
        :param name: 配置名称
        :return: WebhookConfig对象或None
        """
        return await self.select_model_by_column(db, name=name)

    async def get_active_configs(self, db: AsyncSession) -> Sequence[WebhookConfig]:
        """
        获取所有启用的WebhookConfig

        :param db: 数据库会话
        :return: 启用的WebhookConfig列表
        """
        return await self.select_models(db, self.model.is_active == True)

    async def update_status(self, db: AsyncSession, pk: int, is_active: bool) -> int:
        """
        更新WebhookConfig状态

        :param db: 数据库会话
        :param pk: 主键
        :param is_active: 是否启用
        :return: 更新的记录数
        """
        # 直接使用字典更新，避免Schema验证问题
        from sqlalchemy import update
        stmt = update(self.model).where(self.model.id == pk).values(is_active=is_active)
        result = await db.execute(stmt)
        return result.rowcount


webhook_config_dao: CRUDWebhookConfig = CRUDWebhookConfig(WebhookConfig) 