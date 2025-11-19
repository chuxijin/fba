#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.bili.crud.crud_task_config import bili_task_config_crud
from backend.app.bili.model.task_config import BiliTaskConfig
from backend.app.bili.schema.task_config import CreateBiliTaskConfig, UpdateBiliTaskConfig
from backend.common.exception import errors
from backend.common.pagination import paging_data


class BiliTaskConfigService:
    """任务配置服务"""

    @staticmethod
    async def get_list(
        db: AsyncSession,
        task_name: str | None = None,
        task_type: str | None = None,
        is_enabled: bool | None = None,
    ) -> dict[str, Any]:
        """
        获取任务配置分页列表

        :param db: 数据库会话
        :param task_name: 任务名称
        :param task_type: 任务类型
        :param is_enabled: 是否启用
        :return:
        """
        task_select = await bili_task_config_crud.get_select(
            task_name=task_name, task_type=task_type, is_enabled=is_enabled
        )
        return await paging_data(db, task_select)

    @staticmethod
    async def get_detail(db: AsyncSession, pk: int) -> BiliTaskConfig:
        """
        获取任务配置详情

        :param db: 数据库会话
        :param pk: 任务 ID
        :return:
        """
        task_config = await bili_task_config_crud.get(db, pk)
        if not task_config:
            raise errors.NotFoundError(msg='任务配置不存在')
        return task_config

    @staticmethod
    async def create(db: AsyncSession, obj_in: CreateBiliTaskConfig) -> None:
        """
        创建任务配置

        :param db: 数据库会话
        :param obj_in: 创建数据
        :return:
        """
        existing = await bili_task_config_crud.get_by_name(db, obj_in.task_name)
        if existing:
            raise errors.ConflictError(msg='任务名称已存在')
        await bili_task_config_crud.create(db, obj_in)

    @staticmethod
    async def update(db: AsyncSession, pk: int, obj_in: UpdateBiliTaskConfig) -> int:
        """
        更新任务配置

        :param db: 数据库会话
        :param pk: 任务 ID
        :param obj_in: 更新数据
        :return:
        """
        task_config = await bili_task_config_crud.get(db, pk)
        if not task_config:
            raise errors.NotFoundError(msg='任务配置不存在')

        if obj_in.task_name and obj_in.task_name != task_config.task_name:
            existing = await bili_task_config_crud.get_by_name(db, obj_in.task_name)
            if existing:
                raise errors.ConflictError(msg='任务名称已存在')

        return await bili_task_config_crud.update(db, pk, obj_in)

    @staticmethod
    async def delete(db: AsyncSession, pk: int) -> int:
        """
        删除任务配置

        :param db: 数据库会话
        :param pk: 任务 ID
        :return:
        """
        task_config = await bili_task_config_crud.get(db, pk)
        if not task_config:
            raise errors.NotFoundError(msg='任务配置不存在')
        return await bili_task_config_crud.delete(db, pk)

    @staticmethod
    async def execute_now(db: AsyncSession, pk: int) -> None:
        """
        立即执行任务

        :param db: 数据库会话
        :param pk: 任务 ID
        """
        from backend.app.bili.scheduler.manager import task_scheduler

        task_config = await bili_task_config_crud.get(db, pk)
        if not task_config:
            raise errors.NotFoundError(msg='任务配置不存在')

        # 调用调度器立即执行任务
        await task_scheduler.execute_task_immediately(task_config)


bili_task_config_service = BiliTaskConfigService()
