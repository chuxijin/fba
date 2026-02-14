#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from backend.database.db import async_db_session
from backend.plugin.agiso.crud.crud_push_log import push_log_dao
from backend.plugin.agiso.schema.push_log import CreatePushLog, GetPushLogDetail


class PushLogService:
    """推送日志服务"""

    @staticmethod
    async def create_log(obj: CreatePushLog) -> GetPushLogDetail:
        """
        创建推送日志

        :param obj: 创建推送日志参数
        :return:
        """
        async with async_db_session.begin() as db:
            created_log = await push_log_dao.create_model(db, obj)
            await db.flush()
            return GetPushLogDetail.model_validate(created_log)

    @staticmethod
    async def update_log_status(
        log_id: int,
        process_status: int,
        process_result: str | None = None,
    ) -> None:
        """
        更新日志处理状态

        :param log_id: 日志ID
        :param process_status: 处理状态 (1:成功, 2:失败)
        :param process_result: 处理结果
        :return:
        """
        async with async_db_session.begin() as db:
            await push_log_dao.update_model(
                db,
                log_id,
                {
                    'process_status': process_status,
                    'process_result': process_result,
                },
            )

    @staticmethod
    async def get_by_order_no(order_no: str) -> GetPushLogDetail | None:
        """
        根据订单号获取推送日志

        :param order_no: 订单编号
        :return:
        """
        async with async_db_session() as db:
            log = await push_log_dao.get_by_order_no(db, order_no)
            if not log:
                return None
            return GetPushLogDetail.model_validate(log)

    @staticmethod
    async def get_by_order_no_and_type(order_no: str, push_type: int | None) -> GetPushLogDetail | None:
        """
        根据订单号和推送类型查找日志（用于去重）

        :param order_no: 订单编号
        :param push_type: 推送类型(aopic)
        :return:
        """
        async with async_db_session() as db:
            record = await push_log_dao.get_by_order_no(db, order_no, push_type=push_type)
            if not record:
                return None
            return GetPushLogDetail.model_validate(record)


push_log_service = PushLogService()
