#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.plugin.agiso.model.push_log import AgisoPushLog


class CRUDPushLog(CRUDPlus[AgisoPushLog]):
    """推送日志 CRUD"""

    async def get_by_order_no(
        self, db: AsyncSession, order_no: str, push_type: int | None = None
    ) -> AgisoPushLog | None:
        """
        根据订单号获取推送日志

        :param db: 数据库会话
        :param order_no: 订单编号
        :param push_type: 推送类型(aopic)
        :return:
        """
        stmt = select(self.model).where(self.model.order_no == order_no)
        if push_type is not None:
            stmt = stmt.where(self.model.push_type == push_type)
        stmt = stmt.order_by(self.model.created_time.desc())
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    def get_select(
        self,
        order_no: str | None = None,
        push_type: int | None = None,
        process_status: int | None = None,
    ) -> Select:
        """
        获取推送日志查询

        :param order_no: 订单编号
        :param push_type: 推送类型(aopic)
        :param process_status: 处理状态
        :return:
        """
        stmt = select(self.model)
        if order_no:
            stmt = stmt.where(self.model.order_no == order_no)
        if push_type is not None:
            stmt = stmt.where(self.model.push_type == push_type)
        if process_status is not None:
            stmt = stmt.where(self.model.process_status == process_status)

        return stmt.order_by(self.model.created_time.desc())


push_log_dao: CRUDPushLog = CRUDPushLog(AgisoPushLog)
