#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy import Select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.plugin.links.crud import log_dao
from backend.plugin.links.model import Log
from backend.plugin.links.schema import LogStatistics

# 日志类型常量
LOG_TYPE_DWZ = 1
LOG_TYPE_QUN = 2
LOG_TYPE_KF = 3


class LogService:
    """访问日志服务"""

    @staticmethod
    def get_select(
        *,
        log_type: int | None = None,
        target_id: int | None = None,
        device: str | None = None,
        reference: str | None = None,
    ) -> Select:
        """
        获取日志列表查询

        :param log_type: 类型筛选(1短链 2群活码 3客服码)
        :param target_id: 目标ID筛选
        :param device: 设备筛选
        :param reference: 来源筛选
        :return:
        """
        return log_dao.get_select(
            log_type=log_type,
            target_id=target_id,
            device=device,
            reference=reference,
        )

    @staticmethod
    async def get_by_target(
        *,
        db: AsyncSession,
        log_type: int,
        target_id: int,
        limit: int = 100,
    ) -> list[Log]:
        """
        获取目标的访问日志

        :param db: 数据库会话
        :param log_type: 类型(1短链 2群活码 3客服码)
        :param target_id: 目标ID
        :param limit: 返回数量限制
        :return:
        """
        return await log_dao.get_by_target(db, log_type, target_id, limit=limit)

    @staticmethod
    async def get_statistics(
        *,
        db: AsyncSession,
        log_type: int,
        target_id: int,
    ) -> LogStatistics:
        """
        获取统计数据

        :param db: 数据库会话
        :param log_type: 类型(1短链 2群活码 3客服码)
        :param target_id: 目标ID
        :return:
        """
        total_clicks = await log_dao.count_total(db, log_type, target_id)
        today_clicks = await log_dao.count_today(db, log_type, target_id)
        device_stats = await log_dao.get_device_stats(db, log_type, target_id)
        reference_stats = await log_dao.get_reference_stats(db, log_type, target_id)

        return LogStatistics(
            total_clicks=total_clicks,
            today_clicks=today_clicks,
            device_stats=device_stats,
            reference_stats=reference_stats,
        )

    @staticmethod
    async def delete_by_target(
        *,
        db: AsyncSession,
        log_type: int,
        target_id: int,
    ) -> int:
        """
        删除目标的所有访问日志

        :param db: 数据库会话
        :param log_type: 类型(1短链 2群活码 3客服码)
        :param target_id: 目标ID
        :return:
        """
        return await log_dao.delete_by_target(db, log_type, target_id)


log_service: LogService = LogService()
