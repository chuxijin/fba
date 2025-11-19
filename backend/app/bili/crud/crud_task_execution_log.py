#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy import Select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.bili.model.task_execution_log import BiliTaskExecutionLog


class CRUDBiliTaskExecutionLog(CRUDPlus[BiliTaskExecutionLog]):
    """B 站任务执行记录数据库操作类"""

    async def get_select(
        self,
        task_config_id: int | None = None,
        task_name: str | None = None,
        execution_status: str | None = None,
    ) -> Select:
        """
        获取任务执行记录列表查询表达式

        :param task_config_id: 任务配置 ID
        :param task_name: 任务名称
        :param execution_status: 执行状态
        :return:
        """
        filters = {}
        if task_config_id is not None:
            filters['task_config_id'] = task_config_id
        if task_name is not None:
            filters['task_name__like'] = f'%{task_name}%'
        if execution_status is not None:
            filters['execution_status'] = execution_status

        return await self.select_order('start_time', 'desc', **filters)

    async def get(self, db: AsyncSession, pk: int) -> BiliTaskExecutionLog | None:
        """
        获取执行记录详情

        :param db: 数据库会话
        :param pk: 主键 ID
        :return:
        """
        return await self.select_model(db, pk)


bili_task_execution_log_crud: CRUDBiliTaskExecutionLog = CRUDBiliTaskExecutionLog(BiliTaskExecutionLog)
