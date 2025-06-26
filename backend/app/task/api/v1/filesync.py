#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated, Dict, Any

from fastapi import APIRouter, Path

from backend.app.task.celery_task.filesync.tasks import (
    check_and_execute_filesync_cron_tasks,
    execute_filesync_task_by_config_id,
    get_filesync_configs_with_cron,
)
from backend.common.response.response_schema import ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth

router = APIRouter()


@router.post(
    '/check-cron-tasks',
    summary='检查并执行文件同步定时任务',
    dependencies=[DependsJwtAuth],
)
async def check_filesync_cron_tasks() -> ResponseSchemaModel[Dict[str, Any]]:
    """
    手动触发检查并执行文件同步定时任务
    
    扫描所有启用的同步配置，检查其cron字段，
    如果到了执行时间则触发同步任务
    
    :return: 任务ID和状态
    """
    task = check_and_execute_filesync_cron_tasks.delay()
    return response_base.success(data={
        "task_id": task.id,
        "status": "submitted",
        "message": "文件同步定时任务检查已提交到队列"
    })


@router.post(
    '/execute/{config_id}',
    summary='执行指定配置的文件同步任务',
    dependencies=[DependsJwtAuth],
)
async def execute_filesync_task(
    config_id: Annotated[int, Path(description='同步配置ID')]
) -> ResponseSchemaModel[Dict[str, Any]]:
    """
    根据配置ID执行单个文件同步任务
    
    :param config_id: 同步配置ID
    :return: 任务ID和状态
    """
    task = execute_filesync_task_by_config_id.delay(config_id)
    return response_base.success(data={
        "task_id": task.id,
        "config_id": config_id,
        "status": "submitted",
        "message": f"配置 {config_id} 的同步任务已提交到队列"
    })


@router.get(
    '/configs-with-cron',
    summary='获取设置了cron的同步配置',
    dependencies=[DependsJwtAuth],
)
async def get_configs_with_cron() -> ResponseSchemaModel[Dict[str, Any]]:
    """
    获取所有设置了cron表达式的同步配置列表
    
    :return: 任务ID和状态
    """
    task = get_filesync_configs_with_cron.delay()
    return response_base.success(data={
        "task_id": task.id,
        "status": "submitted",
        "message": "获取配置列表任务已提交到队列"
    }) 