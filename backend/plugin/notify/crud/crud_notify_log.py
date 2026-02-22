#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.plugin.notify.model.notify_log import NotifyLog


class CRUDNotifyLog(CRUDPlus[NotifyLog]):
    """通知日志 CRUD"""

    async def get_by_id(self, db: AsyncSession, log_id: int) -> NotifyLog | None:
        """
        根据 ID 获取通知日志

        :param db: 数据库会话
        :param log_id: 日志 ID
        :return:
        """
        return await self.select_model(db, log_id)

    def get_list_select(
        self,
        *,
        status: int | None = None,
        channel: str | None = None,
        source: str | None = None,
    ) -> Select:
        """
        获取通知日志列表查询

        :param status: 发送状态
        :param channel: 发送渠道
        :param source: 触发来源
        :return:
        """
        stmt = select(self.model)
        if status is not None:
            stmt = stmt.where(self.model.status == status)
        if channel:
            stmt = stmt.where(self.model.channel == channel)
        if source:
            stmt = stmt.where(self.model.source == source)
        return stmt.order_by(self.model.created_time.desc())


notify_log_dao: CRUDNotifyLog = CRUDNotifyLog(NotifyLog)
