#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
应用启动时的任务初始化服务

在应用启动时自动加载数据库中的同步配置到 Celery Beat 调度器
"""

import logging
import asyncio
from typing import Dict, Any

from backend.app.task.service.sync_scheduler import get_sync_scheduler

logger = logging.getLogger(__name__)


async def initialize_sync_tasks() -> Dict[str, Any]:
    """
    初始化同步任务
    
    在应用启动时调用，从数据库加载所有启用的同步配置到调度器
    
    :return: 初始化结果
    """
    logger.info("开始初始化同步任务调度器...")
    
    try:
        scheduler = get_sync_scheduler()
        result = await scheduler.sync_all_tasks_from_db()
        
        if result["success"]:
            logger.info(f"同步任务调度器初始化成功: {result['message']}")
        else:
            logger.error(f"同步任务调度器初始化失败: {result.get('message', 'Unknown error')}")
        
        return result
        
    except Exception as e:
        error_msg = f"同步任务调度器初始化异常: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return {
            "success": False,
            "message": error_msg,
            "error": str(e)
        }


def setup_startup_tasks():
    """
    设置启动任务
    
    这个函数应该在 FastAPI 应用的 startup 事件中调用
    """
    logger.info("设置应用启动任务...")
    
    # 创建异步任务来初始化同步任务
    async def startup_task():
        await initialize_sync_tasks()
    
    # 在事件循环中运行初始化任务
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # 如果事件循环已经在运行，创建任务
            loop.create_task(startup_task())
        else:
            # 如果事件循环还没运行，直接运行
            loop.run_until_complete(startup_task())
    except RuntimeError:
        # 如果没有事件循环，创建一个新的
        asyncio.run(startup_task())


# 便捷函数，用于在应用启动时调用
async def on_startup():
    """应用启动时的回调函数"""
    await initialize_sync_tasks()


def on_shutdown():
    """应用关闭时的回调函数"""
    logger.info("应用关闭，清理同步任务调度器...")
    
    try:
        scheduler = get_sync_scheduler()
        scheduler.clear_all_tasks()
        logger.info("同步任务调度器已清理")
    except Exception as e:
        logger.error(f"清理同步任务调度器失败: {e}") 