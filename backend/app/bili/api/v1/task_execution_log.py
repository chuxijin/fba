#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Query

from backend.app.bili.schema.task_execution_log import GetBiliTaskExecutionLogDetail
from backend.app.bili.service.task_execution_log_service import bili_task_execution_log_service
from backend.common.pagination import DependsPagination, PageData
from backend.common.response.response_schema import ResponseSchemaModel, response_base
from backend.database.db import CurrentSession

router = APIRouter()


@router.get('', summary='分页获取任务执行记录列表', dependencies=[DependsPagination])
async def get_bili_task_execution_log_list(
    db: CurrentSession,
    task_config_id: Annotated[int | None, Query(description='任务配置 ID')] = None,
    task_name: Annotated[str | None, Query(description='任务名称')] = None,
    execution_status: Annotated[str | None, Query(description='执行状态')] = None,
) -> ResponseSchemaModel[PageData[GetBiliTaskExecutionLogDetail]]:
    """分页获取任务执行记录列表"""
    page_data = await bili_task_execution_log_service.get_list(
        db=db, task_config_id=task_config_id, task_name=task_name, execution_status=execution_status
    )
    return response_base.success(data=page_data)


@router.get('/{pk}', summary='获取任务执行记录详情')
async def get_bili_task_execution_log_detail(
    db: CurrentSession, pk: int
) -> ResponseSchemaModel[GetBiliTaskExecutionLogDetail]:
    """获取任务执行记录详情"""
    execution_log = await bili_task_execution_log_service.get_detail(db, pk)
    return response_base.success(data=execution_log)
