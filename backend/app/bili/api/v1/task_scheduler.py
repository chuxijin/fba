#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Query

from backend.app.bili.scheduler.manager import task_scheduler
from backend.common.response.response_schema import ResponseSchemaModel, response_base

router = APIRouter()


@router.post('/reload', summary='热重载所有任务配置')
async def reload_bili_tasks() -> ResponseSchemaModel[str]:
    """热重载任务配置（从数据库读取最新配置并应用）"""
    await task_scheduler.reload_tasks()
    return response_base.success(data='任务配置已热重载')


@router.post('/pause', summary='暂停指定任务')
async def pause_bili_task(task_name: Annotated[str, Query(description='任务名称')]) -> ResponseSchemaModel[str]:
    """暂停任务"""
    await task_scheduler.pause_task(task_name)
    return response_base.success(data=f'任务 {task_name} 已暂停')


@router.post('/resume', summary='恢复指定任务')
async def resume_bili_task(task_name: Annotated[str, Query(description='任务名称')]) -> ResponseSchemaModel[str]:
    """恢复任务"""
    await task_scheduler.resume_task(task_name)
    return response_base.success(data=f'任务 {task_name} 已恢复')


@router.get('/status', summary='获取所有任务状态')
async def get_bili_task_status() -> ResponseSchemaModel[list]:
    """获取任务状态"""
    status = task_scheduler.get_job_status()
    return response_base.success(data=status)

