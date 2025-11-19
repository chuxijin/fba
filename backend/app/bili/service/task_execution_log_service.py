#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.bili.crud.crud_task_execution_log import bili_task_execution_log_crud
from backend.app.bili.model.task_execution_log import BiliTaskExecutionLog
from backend.common.exception import errors
from backend.common.pagination import paging_data


class BiliTaskExecutionLogService:
    """任务执行记录服务"""

    @staticmethod
    async def get_list(
        db: AsyncSession,
        task_config_id: int | None = None,
        task_name: str | None = None,
        execution_status: str | None = None,
    ) -> dict[str, Any]:
        """
        获取任务执行记录分页列表

        :param db: 数据库会话
        :param task_config_id: 任务配置 ID
        :param task_name: 任务名称
        :param execution_status: 执行状态
        :return:
        """
        log_select = await bili_task_execution_log_crud.get_select(
            task_config_id=task_config_id, task_name=task_name, execution_status=execution_status
        )
        return await paging_data(db, log_select)

    @staticmethod
    async def get_detail(db: AsyncSession, pk: int) -> BiliTaskExecutionLog:
        """
        获取任务执行记录详情

        :param db: 数据库会话
        :param pk: 记录 ID
        :return:
        """
        execution_log = await bili_task_execution_log_crud.get(db, pk)
        if not execution_log:
            raise errors.NotFoundError(msg='执行记录不存在')
        return execution_log


bili_task_execution_log_service = BiliTaskExecutionLogService()
