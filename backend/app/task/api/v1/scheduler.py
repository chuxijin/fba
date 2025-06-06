#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Query, Body
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.task.service.sync_scheduler import get_sync_scheduler, validate_cron, refresh_sync_tasks
from backend.app.task.celery_task.filesync.tasks import sync_file_task, sync_all_enabled_configs
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession

router = APIRouter()


@router.post(
    '/refresh-tasks',
    summary='刷新定时任务',
    description='从数据库重新加载所有同步配置的定时任务',
    response_model=ResponseSchemaModel[dict],
    dependencies=[DependsJwtAuth]
)
async def refresh_sync_tasks_endpoint() -> ResponseSchemaModel[dict]:
    """刷新定时任务"""
    result = await refresh_sync_tasks()
    return await response_base.success(data=result)


@router.get(
    '/task-status',
    summary='获取任务状态',
    description='获取当前调度器中的任务状态信息',
    response_model=ResponseSchemaModel[dict],
    dependencies=[DependsJwtAuth]
)
async def get_task_status() -> ResponseSchemaModel[dict]:
    """获取任务状态"""
    scheduler = get_sync_scheduler()
    status = scheduler.get_task_status()
    return await response_base.success(data=status)


@router.post(
    '/validate-cron',
    summary='验证 cron 表达式',
    description='验证 cron 表达式的格式和有效性',
    response_model=ResponseSchemaModel[dict],
    dependencies=[DependsJwtAuth]
)
async def validate_cron_expression(
    cron_expr: Annotated[str, Body(description="cron 表达式，格式: '分 时 日 月 周'")]
) -> ResponseSchemaModel[dict]:
    """验证 cron 表达式"""
    result = validate_cron(cron_expr)
    return await response_base.success(data=result)


@router.post(
    '/execute-sync/{config_id}',
    summary='立即执行同步任务',
    description='立即执行指定配置的同步任务（不等待定时调度）',
    response_model=ResponseSchemaModel[dict],
    dependencies=[DependsJwtAuth]
)
async def execute_sync_immediately(
    config_id: Annotated[int, Query(description="同步配置ID")]
) -> ResponseSchemaModel[dict]:
    """立即执行同步任务"""
    # 异步执行任务
    task_result = sync_file_task.delay(config_id)
    
    return await response_base.success(data={
        "message": "同步任务已提交执行",
        "task_id": task_result.id,
        "config_id": config_id,
        "status": "submitted"
    })


@router.post(
    '/execute-all-enabled',
    summary='执行所有启用的同步任务',
    description='立即执行所有启用配置的同步任务',
    response_model=ResponseSchemaModel[dict],
    dependencies=[DependsJwtAuth]
)
async def execute_all_enabled_sync() -> ResponseSchemaModel[dict]:
    """执行所有启用的同步任务"""
    # 异步执行批量任务
    task_result = sync_all_enabled_configs.delay()
    
    return await response_base.success(data={
        "message": "批量同步任务已提交执行",
        "task_id": task_result.id,
        "status": "submitted"
    })


@router.get(
    '/task-result/{task_id}',
    summary='获取任务执行结果',
    description='获取指定任务ID的执行结果',
    response_model=ResponseSchemaModel[dict],
    dependencies=[DependsJwtAuth]
)
async def get_task_result(
    task_id: Annotated[str, Query(description="任务ID")]
) -> ResponseSchemaModel[dict]:
    """获取任务执行结果"""
    from backend.app.task.celery import celery_app
    
    # 获取任务结果
    task_result = celery_app.AsyncResult(task_id)
    
    result_data = {
        "task_id": task_id,
        "status": task_result.status,
        "ready": task_result.ready(),
        "successful": task_result.successful() if task_result.ready() else None,
        "failed": task_result.failed() if task_result.ready() else None,
        "result": task_result.result if task_result.ready() else None,
        "traceback": str(task_result.traceback) if task_result.failed() else None
    }
    
    return await response_base.success(data=result_data)


@router.delete(
    '/clear-tasks',
    summary='清空所有定时任务',
    description='清空调度器中的所有同步定时任务',
    response_model=ResponseSchemaModel[dict],
    dependencies=[DependsJwtAuth]
)
async def clear_all_tasks() -> ResponseSchemaModel[dict]:
    """清空所有定时任务"""
    scheduler = get_sync_scheduler()
    scheduler.clear_all_tasks()
    
    return await response_base.success(data={
        "message": "所有定时任务已清空",
        "status": "cleared"
    }) 