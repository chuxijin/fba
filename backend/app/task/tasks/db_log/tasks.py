#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any

from celery import shared_task
from sqlalchemy import delete, and_

from backend.app.admin.service.login_log_service import login_log_service
from backend.app.admin.service.opera_log_service import opera_log_service
from backend.app.coulddrive.service.synctask_service import get_sync_task_service
from backend.database.db import async_db_session

logger = logging.getLogger(__name__)


@shared_task
async def delete_db_opera_log() -> str:
    """自动删除数据库操作日志"""
    await opera_log_service.delete_all()
    return 'Success'


@shared_task
async def delete_db_login_log() -> str:
    """自动删除数据库登录日志"""
    await login_log_service.delete_all()
    return 'Success'


@shared_task
def delete_filesync_data_older_than_30_days() -> Dict[str, Any]:
    """删除30天以外的文件同步数据（包括任务和任务项）"""
    try:
        # 使用 asyncio.run 在同步环境中执行异步函数
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(_delete_filesync_data_older_than_30_days())
            return result
        finally:
            loop.close()
    except Exception as e:
        logger.error(f"删除30天以外的文件同步数据失败: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "deleted_count": 0,
            "message": f"删除失败: {str(e)}"
        }


async def _delete_filesync_data_older_than_30_days() -> Dict[str, Any]:
    """删除30天以外的文件同步数据的异步实现"""
    try:
        async with async_db_session() as db:
            # 直接调用 sync_task_service 的删除方法
            sync_task_service = get_sync_task_service()
            result = await sync_task_service.delete_tasks_30days(db)
            return result
            
    except Exception as e:
        logger.error(f"删除30天以外的文件同步数据失败: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "deleted_count": 0,
            "message": f"删除失败: {str(e)}"
        }
