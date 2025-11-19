#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""动态任务调度管理器（支持工作时间段）"""
import asyncio
import json
import random
from datetime import datetime, time

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.bili.model.task_config import BiliTaskConfig
from backend.common.log import log
from backend.database.db import async_engine


class TaskSchedulerManager:
    """任务调度管理器（单例）"""

    _instance = None
    _scheduler: AsyncIOScheduler | None = None
    _task_registry: dict[str, any] = {}
    _running_tasks: dict[str, bool] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._scheduler is None:
            self._scheduler = AsyncIOScheduler(timezone='Asia/Shanghai')
            log.info('✅ TaskSchedulerManager 初始化完成')

    @classmethod
    def register_task(cls, task_type: str, task_func):
        """
        注册任务执行函数

        :param task_type: 任务类型
        :param task_func: 任务执行函数
        """
        cls._task_registry[task_type] = task_func
        log.info(f'✅ 注册任务类型: {task_type}')

    async def start(self):
        """启动调度器"""
        if not self._scheduler.running:
            await self.reload_tasks()
            self._scheduler.start()
            log.info('🚀 任务调度器已启动')

    async def stop(self):
        """停止调度器"""
        if self._scheduler.running:
            self._scheduler.shutdown()
            log.info('🛑 任务调度器已停止')

    async def reload_tasks(self):
        """热重载任务配置（从数据库读取）"""
        async with AsyncSession(async_engine) as db:
            stmt = select(BiliTaskConfig).where(BiliTaskConfig.is_enabled == True)
            result = await db.execute(stmt)
            tasks = result.scalars().all()

            # 清除旧任务
            self._scheduler.remove_all_jobs()
            log.info('🔄 开始重载任务配置...')

            for task in tasks:
                await self._add_task(task)

            log.info(f'✅ 任务重载完成，当前活跃任务: {len(self._scheduler.get_jobs())} 个')

    async def _add_task(self, task_config: BiliTaskConfig):
        """
        添加单个任务到调度器

        :param task_config: 任务配置对象
        """
        task_func = self._task_registry.get(task_config.task_type)
        if not task_func:
            log.error(f'❌ 未找到任务类型: {task_config.task_type}')
            return

        # 使用平均间隔作为触发器（实际执行时会随机）
        avg_interval = (task_config.check_interval_min + task_config.check_interval_max) // 2
        trigger = IntervalTrigger(seconds=avg_interval, timezone='Asia/Shanghai')

        # 添加任务
        self._scheduler.add_job(
            self._wrap_task_with_time_check(task_config.id, task_func, task_config),
            trigger=trigger,
            id=task_config.task_name,
            name=task_config.description or task_config.task_name,
            replace_existing=True,
        )

        log.info(f'✅ 添加任务: {task_config.task_name} ({task_config.task_type})')

    def _wrap_task_with_time_check(self, task_id: int, task_func, task_config: BiliTaskConfig):
        """
        包装任务执行（时间段检查 + 随机间隔 + 错误处理）

        :param task_id: 任务 ID
        :param task_func: 任务函数
        :param task_config: 任务配置
        """

        async def wrapped():
            # 检查是否在工作时间内
            if not self._is_work_time(task_config):
                log.debug(f'⏸️  任务 {task_config.task_name} 不在工作时间，跳过执行')
                return

            # 防止重复执行
            if self._running_tasks.get(task_config.task_name, False):
                log.warning(f'⚠️  任务 {task_config.task_name} 正在执行，跳过本次调度')
                return

            self._running_tasks[task_config.task_name] = True

            async with AsyncSession(async_engine) as db:
                try:
                    # 更新检查时间
                    stmt = select(BiliTaskConfig).where(BiliTaskConfig.id == task_id)
                    result = await db.execute(stmt)
                    task = result.scalar_one_or_none()

                    if not task:
                        log.error(f'❌ 任务 ID {task_id} 不存在')
                        return

                    log.info(f'🏃 开始执行任务: {task.task_name}')
                    task.last_check_time = datetime.now()
                    await db.commit()

                    # 执行任务（传递完整配置）
                    result = await task_func(task_config)

                    # 更新成功状态（result 可能是 reply_count 或 send_count）
                    task.last_run_time = datetime.now()
                    task.run_count += 1

                    # 根据任务类型更新统计
                    if task_config.task_type in ['reply_my_message', 'reply_my_comment']:
                        task.reply_count += result or 0
                        log.success(f'✅ 任务执行成功: {task.task_name}, 本次回复: {result} 条')
                    elif task_config.task_type == 'send_to_others_comment':
                        task.send_count += result or 0
                        log.success(f'✅ 任务执行成功: {task.task_name}, 本次发送: {result} 条')

                    task.last_error = None
                    await db.commit()

                    # 随机休眠（防检测）
                    random_sleep = random.randint(task_config.check_interval_min, task_config.check_interval_max)
                    log.debug(f'💤 随机休眠 {random_sleep} 秒')
                    await asyncio.sleep(random_sleep)

                except Exception as e:
                    log.error(f'❌ 任务执行失败: {task_config.task_name}, 错误: {str(e)}')

                    # 更新失败状态
                    stmt = select(BiliTaskConfig).where(BiliTaskConfig.id == task_id)
                    result = await db.execute(stmt)
                    task = result.scalar_one_or_none()
                    if task:
                        task.fail_count += 1
                        task.last_error = str(e)[:500]
                        await db.commit()

                finally:
                    self._running_tasks[task_config.task_name] = False

        return wrapped

    def _is_work_time(self, task_config: BiliTaskConfig) -> bool:
        """
        检查当前是否在工作时间内

        :param task_config: 任务配置
        :return:
        """
        now = datetime.now().time()

        # 解析时间字符串
        start_time = time.fromisoformat(task_config.start_time)
        end_time = time.fromisoformat(task_config.end_time)

        # 检查是否在工作时间段
        if start_time <= end_time:
            # 同一天内
            if not (start_time <= now <= end_time):
                return False
        else:
            # 跨天（例如 22:00 - 06:00）
            if not (now >= start_time or now <= end_time):
                return False

        # 检查是否在休息时间段
        if task_config.rest_start_time and task_config.rest_end_time:
            rest_start = time.fromisoformat(task_config.rest_start_time)
            rest_end = time.fromisoformat(task_config.rest_end_time)

            if rest_start <= rest_end:
                if rest_start <= now <= rest_end:
                    return False
            else:
                if now >= rest_start or now <= rest_end:
                    return False

        return True

    async def pause_task(self, task_name: str):
        """暂停任务"""
        self._scheduler.pause_job(task_name)
        log.info(f'⏸️  暂停任务: {task_name}')

    async def resume_task(self, task_name: str):
        """恢复任务"""
        self._scheduler.resume_job(task_name)
        log.info(f'▶️  恢复任务: {task_name}')

    def get_job_status(self) -> list[dict]:
        """获取所有任务状态"""
        jobs = self._scheduler.get_jobs()
        return [
            {
                'id': job.id,
                'name': job.name,
                'next_run_time': str(job.next_run_time),
                'is_running': self._running_tasks.get(job.id, False),
            }
            for job in jobs
        ]

    async def execute_task_immediately(self, task_config: BiliTaskConfig):
        """
        立即执行任务（不受时间限制）

        :param task_config: 任务配置
        """
        task_func = self._task_registry.get(task_config.task_type)
        if not task_func:
            log.error(f'❌ 未找到任务类型: {task_config.task_type}')
            raise ValueError(f'未注册的任务类型: {task_config.task_type}')

        # 检查是否正在运行
        if self._running_tasks.get(task_config.task_name, False):
            log.warning(f'⚠️  任务 {task_config.task_name} 正在执行，无法重复运行')
            raise ValueError('任务正在执行中，请稍后再试')

        self._running_tasks[task_config.task_name] = True

        async with AsyncSession(async_engine) as db:
            try:
                log.info(f'🚀 手动执行任务: {task_config.task_name}')

                # 执行任务
                result = await task_func(task_config)

                # 更新统计
                stmt = select(BiliTaskConfig).where(BiliTaskConfig.id == task_config.id)
                db_result = await db.execute(stmt)
                task = db_result.scalar_one_or_none()

                if task:
                    task.last_run_time = datetime.now()
                    task.run_count += 1

                    if task_config.task_type in ['reply_my_message', 'reply_my_comment']:
                        task.reply_count += result or 0
                        log.success(f'✅ 任务手动执行成功: {task.task_name}, 本次回复: {result} 条')
                    elif task_config.task_type == 'send_to_others_comment':
                        task.send_count += result or 0
                        log.success(f'✅ 任务手动执行成功: {task.task_name}, 本次发送: {result} 条')

                    task.last_error = None
                    await db.commit()

            except Exception as e:
                log.error(f'❌ 任务手动执行失败: {task_config.task_name}, 错误: {str(e)}')

                # 更新失败状态
                stmt = select(BiliTaskConfig).where(BiliTaskConfig.id == task_config.id)
                db_result = await db.execute(stmt)
                task = db_result.scalar_one_or_none()
                if task:
                    task.fail_count += 1
                    task.last_error = str(e)[:500]
                    await db.commit()

                raise

            finally:
                self._running_tasks[task_config.task_name] = False


# 全局实例
task_scheduler = TaskSchedulerManager()
