#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated, Dict, Any

from fastapi import APIRouter, Query, Path
from starlette.concurrency import run_in_threadpool

from backend.app.task.tasks.resource.tasks import (
    check_and_refresh_expiring_resources,
    refresh_resource_share_by_id,
    get_expiring_resources,
    refresh_subject_mode2_to_permanent,
)
from backend.common.response.response_schema import ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth

router = APIRouter()


@router.post("/refresh-expiring", summary="检查并刷新即将过期的资源", dependencies=[DependsJwtAuth])
async def trigger_refresh_expiring_resources() -> ResponseSchemaModel[Dict[str, Any]]:
    """
    手动触发检查并刷新即将过期的资源任务
    
    扫描yp_resource表中以下两种情况的记录：
    1. 距离过期时间小于24小时的资源
    2. 已经过期的资源
    
    重新创建分享链接并更新数据库
    """
    # 在线程池中执行任务
    result = await run_in_threadpool(check_and_refresh_expiring_resources.delay)
    
    return response_base.success(data={
        "task_id": result.id,
        "message": "资源过期检查任务已启动",
        "status": "pending"
    })


@router.post("/refresh/{resource_id}", summary="刷新指定资源的分享链接", dependencies=[DependsJwtAuth])
async def trigger_refresh_resource_share(
    resource_id: Annotated[int, Path(..., description="资源ID")]
) -> ResponseSchemaModel[Dict[str, Any]]:
    """
    手动触发刷新指定资源的分享链接
    
    :param resource_id: 资源ID
    """
    # 在线程池中执行任务
    result = await run_in_threadpool(refresh_resource_share_by_id.delay, resource_id)
    
    return response_base.success(data={
        "task_id": result.id,
        "resource_id": resource_id,
        "message": f"资源 {resource_id} 分享链接刷新任务已启动",
        "status": "pending"
    })


@router.get("/expiring", summary="获取即将过期的资源列表", dependencies=[DependsJwtAuth])
async def get_expiring_resources_list(
    hours: Annotated[int, Query(ge=1, le=168, description="过期时间阈值（小时），1-168小时")] = 24,
) -> ResponseSchemaModel[Dict[str, Any]]:
    """
    获取即将过期的资源列表
    
    :param hours: 过期时间阈值（小时），默认24小时
    """
    # 在线程池中执行任务
    result = await run_in_threadpool(get_expiring_resources.delay, hours)
    
    return response_base.success(data={
        "task_id": result.id,
        "hours": hours,
        "message": f"获取{hours}小时内即将过期的资源列表任务已启动",
        "status": "pending"
    })


@router.get("/expiring/sync", summary="同步获取即将过期的资源列表", dependencies=[DependsJwtAuth])
async def get_expiring_resources_sync(
    hours: Annotated[int, Query(ge=1, le=168, description="过期时间阈值（小时），1-168小时")] = 24,
) -> ResponseSchemaModel[Dict[str, Any]]:
    """
    同步获取即将过期的资源列表（直接返回结果）
    
    :param hours: 过期时间阈值（小时），默认24小时
    """
    # 直接执行任务并返回结果
    resources = await get_expiring_resources(hours)
    
    return response_base.success(data={
        "hours": hours,
        "total_count": len(resources),
        "resources": resources
    }) 


@router.post(
    "/refresh-permanent/by-subject",
    summary="按科目将临时模式为2的资源刷新为永久链接",
    dependencies=[DependsJwtAuth],
)
async def trigger_refresh_subject_to_permanent(
    subject: Annotated[str, Query(min_length=1, description="科目")],
) -> ResponseSchemaModel[Dict[str, Any]]:
    """
    按科目将 `is_temp_file=2` 的资源刷新为永久链接
    
    :param subject: 科目
    :return:
    """
    result = await run_in_threadpool(refresh_subject_mode2_to_permanent.delay, subject)
    return response_base.success(data={
        "task_id": result.id,
        "subject": subject,
        "message": f"科目 {subject} 的资源刷新永久链接任务已启动",
        "status": "pending",
    })