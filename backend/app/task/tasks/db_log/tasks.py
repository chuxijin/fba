import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any, Dict
from celery import shared_task
from sqlalchemy import delete, and_

from backend.app.admin.service.login_log_service import login_log_service
from backend.app.admin.service.opera_log_service import opera_log_service
from backend.app.coulddrive.service.synctask_service import get_sync_task_service
from backend.app.task.model.result import Task
from backend.database.db import async_db_session

logger = logging.getLogger(__name__)


@shared_task
async def delete_db_opera_log() -> str:
    """自动删除数据库操作日志"""
    async with async_db_session.begin() as db:
        await opera_log_service.delete_all(db=db)
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


@shared_task
def delete_celery_task_results() -> Dict[str, Any]:
    """
    删除 30 天以外的 Celery 任务结果

    :return: 删除结果统计
    """
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(_delete_celery_task_results())
            return result
        finally:
            loop.close()
    except Exception as e:
        logger.error(f"删除 Celery 任务结果失败: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "deleted_count": 0,
            "message": f"删除失败: {str(e)}"
        }


async def _delete_celery_task_results() -> Dict[str, Any]:
    """
    删除 30 天以外的 Celery 任务结果的异步实现

    :return: 删除结果统计
    """
    try:
        async with async_db_session() as db:
            # 计算30天前的时间
            threshold_date = datetime.now() - timedelta(days=30)

            # 构建删除语句：删除 date_done 在 30 天之前的记录
            stmt = delete(Task).where(
                and_(
                    Task.date_done.isnot(None),
                    Task.date_done < threshold_date
                )
            )

            # 执行删除
            result = await db.execute(stmt)
            await db.commit()

            deleted_count = result.rowcount

            logger.info(f"成功删除 {deleted_count} 条 30 天以外的 Celery 任务结果")

            return {
                "success": True,
                "deleted_count": deleted_count,
                "threshold_date": threshold_date.isoformat(),
                "message": f"成功删除 {deleted_count} 条任务结果"
            }

    except Exception as e:
        logger.error(f"删除 Celery 任务结果时发生异常: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "deleted_count": 0,
            "message": f"删除失败: {str(e)}"
        }

