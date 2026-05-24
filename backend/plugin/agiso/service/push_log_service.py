#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.db import async_db_session
from backend.plugin.agiso.crud.crud_push_log import push_log_dao
from backend.plugin.agiso.schema.push_log import CreatePushLog, GetPushLogDetail


class PushLogService:
    """推送日志服务"""

    @staticmethod
    async def create_log(obj: CreatePushLog, *, db: AsyncSession | None = None) -> GetPushLogDetail:
        """
        创建推送日志

        :param obj: 创建推送日志参数
        :param db: 数据库会话
        :return:
        """
        if db:
            created_log = await push_log_dao.create_model(db, obj)
            await db.flush()
            return GetPushLogDetail.model_validate(created_log)
        else:
            async with async_db_session.begin() as db_context:
                created_log = await push_log_dao.create_model(db_context, obj)
                await db_context.flush()
                return GetPushLogDetail.model_validate(created_log)

    @staticmethod
    async def update_log_status(
        log_id: int,
        process_status: int,
        process_result: str | None = None,
        *,
        db: AsyncSession | None = None,
    ) -> None:
        """
        更新日志处理状态

        :param log_id: 日志ID
        :param process_status: 处理状态 (1:成功, 2:失败)
        :param process_result: 处理结果
        :param db: 数据库会话
        :return:
        """
        if db:
            await push_log_dao.update_model(
                db,
                log_id,
                {
                    'process_status': process_status,
                    'process_result': process_result,
                },
            )
        else:
            async with async_db_session.begin() as db_context:
                await push_log_dao.update_model(
                    db_context,
                    log_id,
                    {
                        'process_status': process_status,
                        'process_result': process_result,
                    },
                )

    @staticmethod
    async def get_by_order_no(order_no: str, *, db: AsyncSession | None = None) -> GetPushLogDetail | None:
        """
        根据订单号获取推送日志

        :param order_no: 订单编号
        :param db: 数据库会话
        :return:
        """
        if db:
            log_record = await push_log_dao.get_by_order_no(db, order_no)
            if not log_record:
                return None
            return GetPushLogDetail.model_validate(log_record)
        else:
            async with async_db_session() as db_context:
                log_record = await push_log_dao.get_by_order_no(db_context, order_no)
                if not log_record:
                    return None
                return GetPushLogDetail.model_validate(log_record)

    @staticmethod
    async def get_by_order_no_and_type(
        order_no: str,
        push_type: int | None,
        *,
        db: AsyncSession | None = None,
    ) -> GetPushLogDetail | None:
        """
        根据订单号和推送类型查找日志（用于去重）

        :param order_no: 订单编号
        :param push_type: 推送类型(aopic)
        :param db: 数据库会话
        :return:
        """
        if db:
            record = await push_log_dao.get_by_order_no(db, order_no, push_type=push_type)
            if not record:
                return None
            return GetPushLogDetail.model_validate(record)
        else:
            async with async_db_session() as db_context:
                record = await push_log_dao.get_by_order_no(db_context, order_no, push_type=push_type)
                if not record:
                    return None
                return GetPushLogDetail.model_validate(record)


push_log_service = PushLogService()
