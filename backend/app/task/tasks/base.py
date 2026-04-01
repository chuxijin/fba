import asyncio

from typing import Any

from celery import Task
from sqlalchemy.exc import SQLAlchemyError

from backend.common.socketio.actions import task_notification
from backend.core.conf import settings


class TaskBase(Task):
    """Celery 任务基类"""

    autoretry_for = (SQLAlchemyError,)
    max_retries = settings.CELERY_TASK_MAX_RETRIES

    async def before_start(self, task_id: str, args, kwargs) -> None:  # noqa: ANN001
        """
        任务开始前执行钩子

        :param task_id: 任务 ID
        :return:
        """
        await task_notification(msg=f'任务 {task_id} 开始执行')

    async def on_success(self, retval: Any, task_id: str, args, kwargs) -> None:  # noqa: ANN001
        """
        任务成功后执行钩子

        :param retval: 任务返回值
        :param task_id: 任务 ID
        :return:
        """
        await task_notification(msg=f'任务 {task_id} 执行成功')

    def on_failure(self, exc: Exception, task_id: str, args, kwargs, einfo) -> None:  # noqa: ANN001
        """
        任务失败后执行钩子

        :param exc: 异常对象
        :param task_id: 任务 ID
        :param einfo: 异常信息
        :return:
        """
        asyncio.create_task(task_notification(msg=f'任务 {task_id} 执行失败'))

        # 发送外部通知（微信/Server酱等）
        asyncio.create_task(self._send_failure_notify(self.name, task_id, exc))

    async def on_warning(self, message: str) -> None:
        """
        任务警告钩子

        :param message: 警告信息
        :return:
        """
        task_id = self.request.id
        await task_notification(msg=f'任务 {task_id} 警告: {message}')
        await self._send_warning_notify(self.name, task_id, message)

    @staticmethod
    async def _send_failure_notify(task_name: str, task_id: str, exc: Exception) -> None:
        """发送任务失败的外部通知"""
        try:
            from backend.plugin.notify.service.notify_service import notify_service

            await notify_service.send(
                title=f'定时任务执行失败: {task_name}',
                content=(
                    f'任务ID: {task_id}\n'
                    f'异常: {str(exc)[:500]}'
                ),
                options={'tags': '定时任务|执行失败'},
                source='celery_task',
            )
        except Exception:
            pass

    @staticmethod
    async def _send_warning_notify(task_name: str, task_id: str, message: str) -> None:
        """发送任务警告的外部通知"""
        try:
            from backend.plugin.notify.service.notify_service import notify_service

            await notify_service.send(
                title=f'定时任务警告: {task_name}',
                content=(
                    f'任务ID: {task_id}\n'
                    f'警告: {message}'
                ),
                options={'tags': '定时任务|警告'},
                source='celery_task',
            )
        except Exception:
            pass

