import logging

from datetime import timedelta
from typing import Any, Dict

from sqlalchemy import and_, delete

from backend.app.admin.service.login_log_service import login_log_service
from backend.app.admin.service.opera_log_service import opera_log_service
from backend.app.coulddrive.service.synctask_service import get_sync_task_service
from backend.app.task.celery import celery_app
from backend.app.task.model.result import Task
from backend.database.db import async_db_session
from backend.utils.timezone import timezone

logger = logging.getLogger(__name__)


@celery_app.task(name='delete_db_opera_log')
async def delete_db_opera_log() -> str:
    """自动删除数据库操作日志"""
    async with async_db_session.begin() as db:
        await opera_log_service.delete_all(db=db)
        return 'Success'


@celery_app.task(name='delete_db_login_log')
async def delete_db_login_log() -> str:
    """自动删除数据库登录日志"""
    async with async_db_session.begin() as db:
        await login_log_service.delete_all(db=db)
        return 'Success'


@celery_app.task(name='delete_filesync_data_older_than_30_days')
async def delete_filesync_data_older_than_30_days() -> Dict[str, Any]:
    """删除30天以外的文件同步数据（包括任务和任务项）"""
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


@celery_app.task(name='delete_celery_task_results')
async def delete_celery_task_results() -> Dict[str, Any]:
    """
    删除 30 天以外的 Celery 任务结果

    :return: 删除结果统计
    """
    try:
        async with async_db_session() as db:
            # 计算30天前的时间
            threshold_date = timezone.now() - timedelta(days=30)

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

