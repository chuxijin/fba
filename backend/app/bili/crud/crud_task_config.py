#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from collections.abc import Sequence

from sqlalchemy import Select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.bili.model.task_config import BiliTaskConfig
from backend.app.bili.schema.task_config import CreateBiliTaskConfig, UpdateBiliTaskConfig


class CRUDBiliTaskConfig(CRUDPlus[BiliTaskConfig]):
    """B 站任务配置数据库操作类"""

    async def get_select(
        self,
        task_name: str | None = None,
        task_type: str | None = None,
        is_enabled: bool | None = None,
    ) -> Select:
        """
        获取任务配置列表查询表达式

        :param task_name: 任务名称
        :param task_type: 任务类型
        :param is_enabled: 是否启用
        :return:
        """
        filters = {}
        if task_name is not None:
            filters['task_name__like'] = f'%{task_name}%'
        if task_type is not None:
            filters['task_type'] = task_type
        if is_enabled is not None:
            filters['is_enabled'] = is_enabled

        return await self.select_order('created_time', 'desc', **filters)

    async def get(self, db: AsyncSession, pk: int) -> BiliTaskConfig | None:
        """
        获取任务配置详情

        :param db: 数据库会话
        :param pk: 主键 ID
        :return:
        """
        return await self.select_model(db, pk)

    async def get_by_name(self, db: AsyncSession, task_name: str) -> BiliTaskConfig | None:
        """
        通过任务名称获取配置

        :param db: 数据库会话
        :param task_name: 任务名称
        :return:
        """
        return await self.select_model_by_column(db, task_name=task_name)

    async def get_enabled_tasks(self, db: AsyncSession) -> Sequence[BiliTaskConfig]:
        """获取所有启用的任务配置"""
        return await self.select_models(db, is_enabled=True)

    async def create(self, db: AsyncSession, obj: CreateBiliTaskConfig) -> None:
        """
        创建任务配置

        :param db: 数据库会话
        :param obj: 创建参数
        :return:
        """
        await self.create_model(db, obj)

    async def update(self, db: AsyncSession, pk: int, obj: UpdateBiliTaskConfig) -> int:
        """
        更新任务配置

        :param db: 数据库会话
        :param pk: 主键 ID
        :param obj: 更新参数
        :return:
        """
        return await self.update_model(db, pk, obj)

    async def delete(self, db: AsyncSession, pk: int) -> int:
        """
        删除任务配置

        :param db: 数据库会话
        :param pk: 主键 ID
        :return:
        """
        return await self.delete_model(db, pk)


bili_task_config_crud: CRUDBiliTaskConfig = CRUDBiliTaskConfig(BiliTaskConfig)
