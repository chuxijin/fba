#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Sequence

from sqlalchemy import Select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.plugin.webhook.model.webhook_endpoint import WebhookEndpoint
from backend.plugin.webhook.schema.endpoint import (
    CreateEndpointParam,
    EndpointListParam,
    UpdateEndpointParam,
)


class CRUDEndpoint(CRUDPlus[WebhookEndpoint]):
    """出站端点数据库操作类"""

    async def get(self, db: AsyncSession, pk: int) -> WebhookEndpoint | None:
        """
        获取端点详情

        :param db: 数据库会话
        :param pk: 主键 ID
        :return:
        """
        return await self.select_model(db, pk)

    async def get_by_uid(self, db: AsyncSession, uid: str) -> WebhookEndpoint | None:
        """
        根据 UID 获取端点

        :param db: 数据库会话
        :param uid: 端点唯一标识
        :return:
        """
        return await self.select_model_by_column(db, uid=uid)

    async def get_list(self, params: EndpointListParam | None = None) -> Select:
        """
        获取端点列表

        :param params: 查询参数
        :return:
        """
        filters = []

        if params:
            if params.name:
                filters.append(self.model.name.like(f'%{params.name}%'))
            if params.is_active is not None:
                filters.append(self.model.is_active == params.is_active)

        if filters:
            return await self.select_order('created_time', 'desc', *filters)
        return await self.select_order('created_time', 'desc')

    async def create(self, db: AsyncSession, obj: CreateEndpointParam) -> WebhookEndpoint:
        """
        创建端点

        :param db: 数据库会话
        :param obj: 创建参数
        :return:
        """
        return await self.create_model(db, obj)

    async def update(self, db: AsyncSession, pk: int, obj: UpdateEndpointParam) -> int:
        """
        更新端点

        :param db: 数据库会话
        :param pk: 主键 ID
        :param obj: 更新参数
        :return:
        """
        return await self.update_model(db, pk, obj)

    async def delete(self, db: AsyncSession, pks: list[int]) -> int:
        """
        批量删除端点

        :param db: 数据库会话
        :param pks: 主键列表
        :return:
        """
        return await self.delete_model_by_column(db, allow_multiple=True, id__in=pks)

    async def get_active_endpoints(self, db: AsyncSession) -> Sequence[WebhookEndpoint]:
        """
        获取所有活跃端点

        :param db: 数据库会话
        :return:
        """
        return await self.select_models(db, self.model.is_active.is_(True))

    async def update_failure_count(self, db: AsyncSession, pk: int, count: int) -> None:
        """
        更新端点失败计数

        :param db: 数据库会话
        :param pk: 主键 ID
        :param count: 失败次数
        :return:
        """
        from sqlalchemy import update

        stmt = update(self.model).where(self.model.id == pk).values(failure_count=count)
        await db.execute(stmt)

    async def reset_failure_count(self, db: AsyncSession, pk: int) -> None:
        """
        重置端点失败计数

        :param db: 数据库会话
        :param pk: 主键 ID
        :return:
        """
        from sqlalchemy import update

        stmt = (
            update(self.model)
            .where(self.model.id == pk)
            .values(failure_count=0, last_success_at=self.model.last_success_at)
        )
        await db.execute(stmt)

    async def update_secret(self, db: AsyncSession, pk: int, secret: str) -> None:
        """
        更新端点密钥

        :param db: 数据库会话
        :param pk: 主键 ID
        :param secret: 新密钥
        :return:
        """
        from sqlalchemy import update

        stmt = update(self.model).where(self.model.id == pk).values(secret=secret)
        await db.execute(stmt)


crud_endpoint: CRUDEndpoint = CRUDEndpoint(WebhookEndpoint)
