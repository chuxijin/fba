#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy import Select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.plugin.webhook.model.webhook_event_log import WebhookEventLog
from backend.plugin.webhook.schema.inbound import EventLogListParam


class CRUDEventLog(CRUDPlus[WebhookEventLog]):
    """入站事件日志数据库操作类"""

    async def get(self, db: AsyncSession, pk: int) -> WebhookEventLog | None:
        """
        获取事件日志详情

        :param db: 数据库会话
        :param pk: 主键 ID
        :return:
        """
        return await self.select_model(db, pk)

    async def get_by_event_id(self, db: AsyncSession, event_id: str) -> WebhookEventLog | None:
        """
        根据外部事件 ID 获取日志 (幂等检查)

        :param db: 数据库会话
        :param event_id: 外部事件 ID
        :return:
        """
        return await self.select_model_by_column(db, event_id=event_id)

    async def get_list(self, params: EventLogListParam | None = None) -> Select:
        """
        获取事件日志列表

        :param params: 查询参数
        :return:
        """
        filters = []

        if params:
            if params.source:
                filters.append(self.model.source.like(f'%{params.source}%'))
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

    async def update_status(self, db: AsyncSession, pk: int, status: int, error_message: str | None = None) -> None:
        """
        更新事件日志状态

        :param db: 数据库会话
        :param pk: 主键 ID
        :param status: 新状态
        :param error_message: 错误信息
        :return:
        """
        from sqlalchemy import update

        values: dict = {'status': status}
        if error_message is not None:
            values['error_message'] = error_message

        stmt = update(self.model).where(self.model.id == pk).values(**values)
        await db.execute(stmt)


crud_event_log: CRUDEventLog = CRUDEventLog(WebhookEventLog)
