#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Any, Sequence

from sqlalchemy import Select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.coulddrive.model.filesync import SyncConfig, SyncTask, SyncTaskItem
from backend.app.coulddrive.schema.filesync import (
    CreateSyncConfigParam,
    CreateSyncTaskParam,
    CreateSyncTaskItemParam,
    UpdateSyncConfigParam,
    UpdateSyncTaskParam,
    UpdateSyncTaskItemParam,
)


class CRUDSyncConfig(CRUDPlus[SyncConfig]):
    async def get_all(self, db: AsyncSession) -> Sequence[SyncConfig]:
        """
        获取所有同步配置
        
        :param db: 数据库会话
        :return: 同步配置列表
        """
        return await self.select_models(db)

    async def get_by_account_id(self, db: AsyncSession, *, account_id: int) -> list[SyncConfig]:
        """
        根据账号ID获取同步配置列表
        
        :param db: 数据库会话
        :param account_id: 账号ID
        """
        return await self.get_list(db, account_id=account_id)

    async def get_enabled_configs(self, db: AsyncSession) -> list[SyncConfig]:
        """获取所有启用的同步配置"""
        return await self.get_list(db, enable=True)


class CRUDSyncTask(CRUDPlus[SyncTask]):
    async def get_by_config_id(self, db: AsyncSession, *, config_id: int) -> list[SyncTask]:
        """
        根据配置ID获取同步任务列表
        
        :param db: 数据库会话
        :param config_id: 配置ID
        """
        return await self.get_list(db, config_id=config_id)

    async def get_running_tasks(self, db: AsyncSession) -> list[SyncTask]:
        """获取所有运行中的任务"""
        return await self.get_list(db, status="running")

    async def get_pending_tasks(self, db: AsyncSession) -> list[SyncTask]:
        """获取所有待执行的任务"""
        return await self.get_list(db, status="pending")


class CRUDSyncTaskItem(CRUDPlus[SyncTaskItem]):
    async def get_by_task_id(self, db: AsyncSession, *, task_id: int) -> list[SyncTaskItem]:
        """
        根据任务ID获取任务项列表
        
        :param db: 数据库会话
        :param task_id: 任务ID
        """
        return await self.get_list(db, task_id=task_id)

    async def get_failed_items(self, db: AsyncSession, *, task_id: int) -> list[SyncTaskItem]:
        """
        获取指定任务的失败项
        
        :param db: 数据库会话
        :param task_id: 任务ID
        """
        return await self.get_list(db, task_id=task_id, status="failed")

    async def get_completed_items(self, db: AsyncSession, *, task_id: int) -> list[SyncTaskItem]:
        """
        获取指定任务的完成项
        
        :param db: 数据库会话
        :param task_id: 任务ID
        """
        return await self.get_list(db, task_id=task_id, status="completed")


sync_config_dao: CRUDSyncConfig = CRUDSyncConfig(SyncConfig)
sync_task_dao: CRUDSyncTask = CRUDSyncTask(SyncTask)
sync_task_item_dao: CRUDSyncTaskItem = CRUDSyncTaskItem(SyncTaskItem) 