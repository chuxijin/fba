#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.coulddrive.schema.filesync import (
    GetSyncTaskDetail,
    GetSyncTaskWithRelationDetail,
    GetSyncTaskItemDetail,
)
from backend.app.coulddrive.crud.crud_filesync import sync_task_dao, sync_task_item_dao
from backend.common.log import log

logger = logging.getLogger(__name__)


class SyncTaskService:
    """同步任务服务"""
    
    def __init__(self):
        """初始化同步任务服务"""
        pass
    
    async def get_sync_tasks_by_config_id(
        self, 
        config_id: int, 
        status: str | None = None, 
        *,
        db: AsyncSession
    ) -> list[GetSyncTaskDetail]:
        """
        根据配置ID获取同步任务列表
        
        Args:
            config_id: 配置ID
            status: 任务状态筛选
            db: 数据库会话
            
        Returns:
            list[GetSyncTaskDetail]: 同步任务列表
        """
        return await sync_task_dao.get_tasks_by_config_id(db, config_id=config_id, status=status)

    async def get_sync_task_detail(self, task_id: int, db: AsyncSession) -> GetSyncTaskWithRelationDetail | None:
        """
        获取同步任务详情
        
        Args:
            task_id: 任务ID
            db: 数据库会话
            
        Returns:
            GetSyncTaskWithRelationDetail | None: 同步任务详情
        """
        return await sync_task_dao.get_task_with_items(db, task_id=task_id)

    async def get_sync_task_items(
        self, 
        task_id: int, 
        status: str | None = None,
        operation_type: str | None = None,
        *,
        db: AsyncSession
    ) -> list[GetSyncTaskItemDetail]:
        """
        获取同步任务项列表
        
        Args:
            task_id: 任务ID
            status: 任务项状态筛选
            operation_type: 操作类型筛选
            db: 数据库会话
            
        Returns:
            list[GetSyncTaskItemDetail]: 同步任务项列表
        """
        return await sync_task_item_dao.get_items_by_task_id(
            db, task_id=task_id, status=status, operation_type=operation_type
        )

    async def get_task_statistics(self, task_id: int, db: AsyncSession) -> dict[str, int]:
        """
        获取任务统计信息
        
        Args:
            task_id: 任务ID
            db: 数据库会话
            
        Returns:
            dict[str, int]: 统计信息字典
        """
        return await sync_task_item_dao.get_task_statistics(db, task_id=task_id)


# 全局实例
sync_task_service = SyncTaskService()


def get_sync_task_service() -> SyncTaskService:
    """获取同步任务服务实例"""
    return sync_task_service 