#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Path, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.coulddrive.service.filesync_service import file_sync_service
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession
from backend.common.pagination import DependsPagination, PageData, paging_data, _CustomPageParams

router = APIRouter()


@router.post(
    '/execute/{config_id}',
    summary='执行同步任务',
    description='根据配置ID执行同步任务',
    response_model=ResponseSchemaModel[dict],
    dependencies=[DependsJwtAuth]
)
async def execute_sync_task(
    config_id: Annotated[int, Path(description="同步配置ID")],
    db: CurrentSession
) -> ResponseSchemaModel[dict]:
    """执行同步任务"""
    result = await file_sync_service.execute_sync_by_config_id(config_id, db)
    
    # 确保 result 不为 None
    if not result:
        return response_base.fail(res=ResponseModel(code=500, msg="同步任务执行失败，返回结果为空"), data={})
    
    if not result.get("success", False):
        error_msg = result.get("error", "未知错误")
        return response_base.fail(res=ResponseModel(code=400, msg=error_msg), data={})
    
    return response_base.success(data=result)


@router.get(
    '/{config_id}/tasks',
    summary='获取同步任务列表',
    description='根据配置ID获取同步任务执行历史列表',
    dependencies=[DependsJwtAuth]
)
async def get_sync_tasks(
    config_id: Annotated[int, Path(description="同步配置ID")],
    db: CurrentSession,
    page_params: Annotated[_CustomPageParams, DependsPagination],
    status: Annotated[str | None, Query(description="任务状态")] = None
):
    """
    获取同步任务列表
    
    :param config_id: 同步配置ID
    :param db: 数据库会话
    :param paging: 分页参数
    :param status: 任务状态筛选
    :return: 同步任务列表
    """
    try:
        # 获取任务列表
        tasks = await file_sync_service.get_sync_tasks_by_config_id(
            config_id=config_id,
            status=status,
            db=db
        )
        
        # 使用项目现有分页方法
        from backend.common.pagination import paging_list_data
        
        # 执行分页
        page_data = paging_list_data(tasks, page_params)
        
        return response_base.success(data=page_data)
        
    except Exception as e:
        return response_base.fail(res=ResponseModel(code=500, msg=f"获取同步任务列表失败: {str(e)}"))


@router.get(
    '/task/{task_id}',
    summary='获取同步任务详情',
    description='根据任务ID获取同步任务详情信息',
    dependencies=[DependsJwtAuth]
)
async def get_sync_task_detail(
    task_id: Annotated[int, Path(description="同步任务ID")],
    db: CurrentSession
):
    """
    获取同步任务详情
    
    :param task_id: 同步任务ID
    :param db: 数据库会话
    :return: 同步任务详情
    """
    try:
        task_detail = await file_sync_service.get_sync_task_detail(task_id, db)
        
        if not task_detail:
            return response_base.fail(res=ResponseModel(code=404, msg=f"同步任务 {task_id} 不存在"))
        
        return response_base.success(data=task_detail)
        
    except Exception as e:
        return response_base.fail(res=ResponseModel(code=500, msg=f"获取同步任务详情失败: {str(e)}"))


@router.get(
    '/task/{task_id}/items',
    summary='获取同步任务项列表',
    description='根据任务ID获取同步任务项目详情列表',
    dependencies=[DependsJwtAuth]
)
async def get_sync_task_items(
    task_id: Annotated[int, Path(description="同步任务ID")],
    db: CurrentSession,
    page_params: Annotated[_CustomPageParams, DependsPagination],
    status: Annotated[str | None, Query(description="任务项状态")] = None,
    operation_type: Annotated[str | None, Query(description="操作类型")] = None
):
    """
    获取同步任务项列表
    
    :param task_id: 同步任务ID
    :param db: 数据库会话
    :param paging: 分页参数
    :param status: 任务项状态筛选
    :param operation_type: 操作类型筛选
    :return: 同步任务项列表
    """
    try:
        # 获取任务项列表
        task_items = await file_sync_service.get_sync_task_items(
            task_id=task_id,
            status=status,
            operation_type=operation_type,
            db=db
        )
        
        # 使用项目现有分页方法
        from backend.common.pagination import paging_list_data
        
        # 执行分页
        page_data = paging_list_data(task_items, page_params)
        
        return response_base.success(data=page_data)
        
    except Exception as e:
        return response_base.fail(res=ResponseModel(code=500, msg=f"获取同步任务项列表失败: {str(e)}"))
