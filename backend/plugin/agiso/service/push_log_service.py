#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.db import async_db_session
from backend.plugin.agiso.crud.crud_push_log import push_log_dao
from backend.plugin.agiso.schema.push_log import GetPushLogDetail
from backend.utils.timezone import timezone


class PushLogService:
    """推送日志服务"""

    @staticmethod
    async def create_log(
        push_type: str,
        order_no: str,
        push_data: str,
        platform: str | None = None,
    ) -> GetPushLogDetail:
        """
        创建推送日志

        :param push_type: 推送类型
        :param order_no: 订单编号
        :param push_data: 推送数据
        :param platform: 来源平台
        :return:
        """
        async with async_db_session.begin() as db:
            log_data = {
                'push_type': push_type,
                'order_no': order_no,
                'push_data': push_data,
                'platform': platform,
            }
            created_log = await push_log_dao.create_model(db, log_data)
            return GetPushLogDetail.model_validate(created_log)

    @staticmethod
    async def update_log_success(
        db: AsyncSession,
        log_id: int,
        process_result: str,
    ) -> None:
        """
        更新日志为成功状态

        :param db: 数据库会话
        :param log_id: 日志ID
        :param process_result: 处理结果
        :return:
        """
        await push_log_dao.update_model(
            db,
            log_id,
            {
                'process_status': 1,
                'process_result': process_result,
                'processed_time': timezone.now(),
            },
        )

    @staticmethod
    async def update_log_failed(
        db: AsyncSession,
        log_id: int,
        error_message: str,
    ) -> None:
        """
        更新日志为失败状态

        :param db: 数据库会话
        :param log_id: 日志ID
        :param error_message: 错误信息
        :return:
        """
        log = await push_log_dao.select_model(db, log_id)
        if not log:
            return

        await push_log_dao.update_model(
            db,
            log_id,
            {
                'process_status': 2,
                'error_message': error_message,
                'retry_count': log.retry_count + 1,
                'processed_time': timezone.now(),
            },
        )

    @staticmethod
    async def get_by_order_no(order_no: str, push_type: str | None = None) -> GetPushLogDetail | None:
        """
        根据订单号获取推送日志

        :param order_no: 订单编号
        :param push_type: 推送类型
        :return:
        """
        async with async_db_session() as db:
            log = await push_log_dao.get_by_order_no(db, order_no, push_type)
            if not log:
                return None
            return GetPushLogDetail.model_validate(log)


push_log_service = PushLogService()
