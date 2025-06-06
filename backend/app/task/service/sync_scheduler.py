#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
文件同步任务调度服务

提供基于 cron 表达式的动态任务调度功能，支持：
- 根据数据库中的同步配置动态创建/更新/删除定时任务
- 支持 cron 表达式解析和验证
- 任务状态监控和管理
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

from celery.schedules import crontab
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.task.celery import celery_app
from backend.app.coulddrive.crud.crud_filesync import sync_config_dao
from backend.app.coulddrive.model.filesync import SyncConfig
from backend.database.db import async_db_session

logger = logging.getLogger(__name__)


class SyncTaskScheduler:
    """同步任务调度器"""
    
    def __init__(self):
        """初始化调度器"""
        self._scheduled_tasks: Dict[int, str] = {}  # config_id -> task_name 映射
        self._task_prefix = "sync_config_"
    
    def _parse_cron_expression(self, cron_expr: str) -> Optional[crontab]:
        """
        解析 cron 表达式
        
        :param cron_expr: cron 表达式，格式: "分 时 日 月 周"
        :return: crontab 对象或 None
        """
        if not cron_expr or not cron_expr.strip():
            return None
        
        try:
            # 分割 cron 表达式
            parts = cron_expr.strip().split()
            
            if len(parts) != 5:
                logger.error(f"无效的 cron 表达式格式: {cron_expr}，应为 '分 时 日 月 周' 格式")
                return None
            
            minute, hour, day, month, day_of_week = parts
            
            # 创建 crontab 对象
            return crontab(
                minute=minute,
                hour=hour,
                day_of_month=day,
                month_of_year=month,
                day_of_week=day_of_week
            )
            
        except Exception as e:
            logger.error(f"解析 cron 表达式失败: {cron_expr}, 错误: {e}")
            return None
    
    def _get_task_name(self, config_id: int) -> str:
        """获取任务名称"""
        return f"{self._task_prefix}{config_id}"
    
    def add_sync_task(self, config: SyncConfig) -> bool:
        """
        添加同步任务到调度器
        
        :param config: 同步配置
        :return: 是否添加成功
        """
        if not config.enable or not config.cron:
            logger.warning(f"配置 {config.id} 未启用或缺少 cron 表达式，跳过添加任务")
            return False
        
        # 解析 cron 表达式
        cron_schedule = self._parse_cron_expression(config.cron)
        if not cron_schedule:
            logger.error(f"配置 {config.id} 的 cron 表达式无效: {config.cron}")
            return False
        
        task_name = self._get_task_name(config.id)
        
        try:
            # 添加到 Celery Beat 调度
            celery_app.conf.beat_schedule[task_name] = {
                'task': 'sync_file_task',
                'schedule': cron_schedule,
                'args': (config.id,),
                'options': {
                    'description': f'同步任务: {config.remark or f"配置{config.id}"}',
                    'expires': 3600,  # 任务过期时间（秒）
                }
            }
            
            # 记录任务映射
            self._scheduled_tasks[config.id] = task_name
            
            logger.info(f"成功添加同步任务: {task_name}, cron: {config.cron}, 配置: {config.remark or f'ID{config.id}'}")
            return True
            
        except Exception as e:
            logger.error(f"添加同步任务失败: {task_name}, 错误: {e}")
            return False
    
    def remove_sync_task(self, config_id: int) -> bool:
        """
        移除同步任务
        
        :param config_id: 配置ID
        :return: 是否移除成功
        """
        task_name = self._get_task_name(config_id)
        
        try:
            # 从 Celery Beat 调度中移除
            if task_name in celery_app.conf.beat_schedule:
                del celery_app.conf.beat_schedule[task_name]
            
            # 移除任务映射
            if config_id in self._scheduled_tasks:
                del self._scheduled_tasks[config_id]
            
            logger.info(f"成功移除同步任务: {task_name}")
            return True
            
        except Exception as e:
            logger.error(f"移除同步任务失败: {task_name}, 错误: {e}")
            return False
    
    def update_sync_task(self, config: SyncConfig) -> bool:
        """
        更新同步任务
        
        :param config: 同步配置
        :return: 是否更新成功
        """
        # 先移除旧任务
        self.remove_sync_task(config.id)
        
        # 再添加新任务
        return self.add_sync_task(config)
    
    async def sync_all_tasks_from_db(self) -> Dict[str, Any]:
        """
        从数据库同步所有任务到调度器
        
        :return: 同步结果
        """
        logger.info("开始从数据库同步所有任务到调度器")
        
        try:
            async with async_db_session() as db:
                # 获取所有同步配置
                all_configs = await sync_config_dao.get_all(db)
                
                # 清空现有任务
                self.clear_all_tasks()
                
                added_count = 0
                skipped_count = 0
                error_count = 0
                
                for config in all_configs:
                    if config.enable and config.cron:
                        if self.add_sync_task(config):
                            added_count += 1
                        else:
                            error_count += 1
                    else:
                        skipped_count += 1
                        logger.debug(f"跳过配置 {config.id}: 未启用或缺少 cron 表达式")
                
                result = {
                    "success": True,
                    "message": f"任务同步完成，添加: {added_count}, 跳过: {skipped_count}, 错误: {error_count}",
                    "total_configs": len(all_configs),
                    "added_count": added_count,
                    "skipped_count": skipped_count,
                    "error_count": error_count,
                    "active_tasks": list(self._scheduled_tasks.keys())
                }
                
                logger.info(result["message"])
                return result
                
        except Exception as e:
            error_msg = f"从数据库同步任务失败: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                "success": False,
                "message": error_msg,
                "error": str(e)
            }
    
    def clear_all_tasks(self) -> None:
        """清空所有同步任务"""
        logger.info("清空所有同步任务")
        
        # 移除所有同步相关的任务
        tasks_to_remove = [
            task_name for task_name in celery_app.conf.beat_schedule.keys()
            if task_name.startswith(self._task_prefix)
        ]
        
        for task_name in tasks_to_remove:
            del celery_app.conf.beat_schedule[task_name]
        
        # 清空映射
        self._scheduled_tasks.clear()
        
        logger.info(f"已清空 {len(tasks_to_remove)} 个同步任务")
    
    def get_task_status(self) -> Dict[str, Any]:
        """
        获取任务状态
        
        :return: 任务状态信息
        """
        return {
            "total_scheduled_tasks": len(self._scheduled_tasks),
            "scheduled_config_ids": list(self._scheduled_tasks.keys()),
            "task_names": list(self._scheduled_tasks.values()),
            "beat_schedule_count": len([
                name for name in celery_app.conf.beat_schedule.keys()
                if name.startswith(self._task_prefix)
            ])
        }
    
    def validate_cron_expression(self, cron_expr: str) -> Dict[str, Any]:
        """
        验证 cron 表达式
        
        :param cron_expr: cron 表达式
        :return: 验证结果
        """
        if not cron_expr or not cron_expr.strip():
            return {
                "valid": False,
                "error": "cron 表达式不能为空"
            }
        
        cron_schedule = self._parse_cron_expression(cron_expr)
        if cron_schedule:
            try:
                # 尝试获取下次执行时间来验证表达式
                next_run = cron_schedule.remaining_estimate(datetime.now())
                return {
                    "valid": True,
                    "message": "cron 表达式有效",
                    "next_run_in_seconds": next_run.total_seconds() if next_run else None
                }
            except Exception as e:
                return {
                    "valid": False,
                    "error": f"cron 表达式验证失败: {str(e)}"
                }
        else:
            return {
                "valid": False,
                "error": "无效的 cron 表达式格式，应为 '分 时 日 月 周' 格式"
            }


# 创建全局调度器实例
sync_scheduler = SyncTaskScheduler()


def get_sync_scheduler() -> SyncTaskScheduler:
    """获取同步任务调度器实例"""
    return sync_scheduler


# 便捷函数
async def refresh_sync_tasks() -> Dict[str, Any]:
    """刷新所有同步任务"""
    return await sync_scheduler.sync_all_tasks_from_db()


def validate_cron(cron_expr: str) -> Dict[str, Any]:
    """验证 cron 表达式"""
    return sync_scheduler.validate_cron_expression(cron_expr) 