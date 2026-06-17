#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import logging

from datetime import timedelta
from typing import Any, Dict

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.coulddrive.crud.crud_filesync import sync_task_dao, sync_task_item_dao
from backend.app.coulddrive.model.filesync import SyncTask, SyncTaskItem
from backend.app.coulddrive.schema.filesync import (
    GetSyncTaskDetail,
    GetSyncTaskItemDetail,
    GetSyncTaskWithRelationDetail,
)
from backend.utils.timezone import timezone

logger = logging.getLogger(__name__)


class SyncTaskService:
    """同步任务服务"""

    def __init__(self):
        """初始化同步任务服务"""
        pass

    async def get_sync_tasks_by_config_id(
        self, config_id: int, status: str | None = None, *, db: AsyncSession
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
        self, task_id: int, status: str | None = None, operation_type: str | None = None, *, db: AsyncSession
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

    async def delete_tasks_30days(self, db: AsyncSession) -> Dict[str, Any]:
        """
        删除30天以外的文件同步任务和任务项数据

        Args:
            db: 数据库会话

        Returns:
            Dict[str, Any]: 删除结果统计
        """
        try:
            # 计算30天前的日期
            cutoff_date = timezone.now() - timedelta(days=30)

            # 先删除30天以外的同步任务项（因为外键约束）
            task_items_stmt = delete(SyncTaskItem).where(SyncTaskItem.created_time < cutoff_date)
            task_items_result = await db.execute(task_items_stmt)
            deleted_task_items_count = task_items_result.rowcount

            # 再删除30天以外的同步任务
            tasks_stmt = delete(SyncTask).where(SyncTask.created_time < cutoff_date)
            tasks_result = await db.execute(tasks_stmt)
            deleted_tasks_count = tasks_result.rowcount

            # 提交事务
            await db.commit()

            total_deleted = deleted_task_items_count + deleted_tasks_count

            logger.info(f'成功删除30天以外的数据: 任务项 {deleted_task_items_count} 条, 任务 {deleted_tasks_count} 条')

            return {
                'success': True,
                'deleted_task_items': deleted_task_items_count,
                'deleted_tasks': deleted_tasks_count,
                'total_deleted': total_deleted,
                'cutoff_date': cutoff_date.isoformat(),
                'message': f'成功删除30天以外的数据: 任务项 {deleted_task_items_count} 条, 任务 {deleted_tasks_count} 条',
            }

        except Exception as e:
            logger.error(f'删除30天以外的文件同步数据失败: {str(e)}')
            # 回滚事务
            await db.rollback()
            return {
                'success': False,
                'error': str(e),
                'deleted_task_items': 0,
                'deleted_tasks': 0,
                'total_deleted': 0,
                'message': f'删除失败: {str(e)}',
            }


# 全局实例
sync_task_service = SyncTaskService()


def get_sync_task_service() -> SyncTaskService:
    """获取同步任务服务实例"""
    return sync_task_service
