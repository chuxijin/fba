#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Path, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.coulddrive.service.filesync_service import file_sync_service
from backend.app.coulddrive.service.synctask_service import sync_task_service
from backend.app.task.celery_task.filesync.tasks import execute_filesync_task_by_config_id
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.response.response_code import CustomResponseCode, CustomResponse
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession
from backend.common.pagination import DependsPagination, PageData, paging_data, _CustomPageParams

router = APIRouter()


@router.post(
    '/execute/{config_id}',
    summary='提交同步任务',
    description='根据配置ID提交异步同步任务',
    response_model=ResponseModel,
    dependencies=[DependsJwtAuth]
)
async def execute_sync_task(
    config_id: Annotated[int, Path(description="同步配置ID")],
    db: CurrentSession
) -> ResponseModel:
    """提交异步同步任务"""
    try:
        # 验证配置是否存在
        from backend.app.coulddrive.crud.crud_filesync import sync_config_dao
        config = await sync_config_dao.select_model(db, config_id)
        if not config:
            return response_base.fail(res=ResponseModel(code=404, msg=f"同步配置 {config_id} 不存在"))
        
        if not config.enable:
            return response_base.fail(res=ResponseModel(code=400, msg="同步配置已禁用"))
        
        # 临时直接执行，避免Celery导入问题
        try:
            # 直接执行同步任务（临时解决方案）
            result = await file_sync_service.execute_sync_by_config_id(config_id, db)
            return response_base.success(data={
                "task_id": f"direct_{config_id}_{int(__import__('time').time())}",
                "config_id": config_id,
                "status": "completed",
                "result": result,
                "message": "同步任务执行完成"
            })
        except Exception as sync_error:
            return response_base.fail(res=ResponseModel(code=500, msg=f"执行同步任务失败: {str(sync_error)}"))
    
    except Exception as e:
        return response_base.fail(res=ResponseModel(code=500, msg=f"提交同步任务失败: {str(e)}"))


@router.get(
    '/task/status/{task_id}',
    summary='查询任务状态',
    description='根据Celery任务ID查询异步任务状态',
    response_model=ResponseModel,
    dependencies=[DependsJwtAuth]
)
async def get_task_status(
    task_id: Annotated[str, Path(description="Celery任务ID")]
) -> ResponseModel:
    """查询异步任务状态"""
    try:
        from backend.app.task.celery import celery_app
        
        # 获取任务状态
        async_result = celery_app.AsyncResult(task_id)
        
        task_info = {
            "task_id": task_id,
            "status": async_result.status,
            "ready": async_result.ready(),
            "successful": async_result.successful() if async_result.ready() else None,
            "failed": async_result.failed() if async_result.ready() else None,
        }
        
        # 如果任务完成，获取结果
        if async_result.ready():
            if async_result.successful():
                result = async_result.result
                task_info.update({
                    "result": result if result is not None else {},
                    "message": "任务执行完成"
                })
            elif async_result.failed():
                task_info.update({
                    "error": str(async_result.info) if async_result.info else "任务执行失败",
                    "message": "任务执行失败"
                })
        else:
            # 任务还在执行中
            task_info["message"] = "任务正在执行中"
        
        return response_base.success(data=task_info)
    
    except Exception as e:
        return response_base.fail(res=ResponseModel(code=500, msg=f"查询任务状态失败: {str(e)}"))


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
    :param page_params: 分页参数
    :param status: 任务状态筛选
    :return: 同步任务列表
    """
    try:
        # 获取任务列表
        tasks = await sync_task_service.get_sync_tasks_by_config_id(
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
        task_detail = await sync_task_service.get_sync_task_detail(task_id, db)
        
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
    :param page_params: 分页参数
    :param status: 任务项状态筛选
    :param operation_type: 操作类型筛选
    :return: 同步任务项列表
    """
    try:
        # 获取任务项列表
        task_items = await sync_task_service.get_sync_task_items(
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
