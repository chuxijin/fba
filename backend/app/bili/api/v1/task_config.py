#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Path, Query

from backend.app.bili.schema.task_config import CreateBiliTaskConfig, GetBiliTaskConfigDetail, UpdateBiliTaskConfig
from backend.app.bili.service.task_config_service import bili_task_config_service
from backend.common.pagination import DependsPagination, PageData
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter()


@router.get('', summary='分页获取任务配置列表', dependencies=[DependsPagination])
async def get_bili_task_config_list(
    db: CurrentSession,
    task_name: Annotated[str | None, Query(description='任务名称')] = None,
    task_type: Annotated[str | None, Query(description='任务类型')] = None,
    is_enabled: Annotated[bool | None, Query(description='是否启用')] = None,
) -> ResponseSchemaModel[PageData[GetBiliTaskConfigDetail]]:
    """分页获取任务配置列表"""
    page_data = await bili_task_config_service.get_list(
        db=db, task_name=task_name, task_type=task_type, is_enabled=is_enabled
    )
    return response_base.success(data=page_data)


@router.get('/{pk}', summary='获取任务配置详情')
async def get_bili_task_config_detail(db: CurrentSession, pk: int) -> ResponseSchemaModel[GetBiliTaskConfigDetail]:
    """获取任务配置详情"""
    task_config = await bili_task_config_service.get_detail(db, pk)
    return response_base.success(data=task_config)


@router.post('', summary='创建任务配置')
async def create_bili_task_config(
    db: CurrentSessionTransaction, obj_in: CreateBiliTaskConfig
) -> ResponseSchemaModel[None]:
    """创建任务配置"""
    await bili_task_config_service.create(db, obj_in)
    return response_base.success()


@router.put('/{pk}', summary='更新任务配置')
async def update_bili_task_config(
    db: CurrentSessionTransaction, pk: int, obj_in: UpdateBiliTaskConfig
) -> ResponseSchemaModel[None]:
    """更新任务配置"""
    await bili_task_config_service.update(db, pk, obj_in)
    return response_base.success()


@router.delete('/{pk}', summary='删除任务配置')
async def delete_bili_task_config(db: CurrentSessionTransaction, pk: int) -> ResponseSchemaModel[None]:
    """删除任务配置"""
    await bili_task_config_service.delete(db, pk)
    return response_base.success()


@router.post('/{pk}/execute', summary='立即执行任务')
async def execute_task_config(
    db: CurrentSession, pk: Annotated[int, Path(description='任务配置 ID')]
) -> ResponseModel:
    """立即执行指定任务"""
    await bili_task_config_service.execute_now(db, pk)
    return response_base.success()
