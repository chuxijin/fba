#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Path, Request
from starlette.concurrency import run_in_threadpool

from backend.app.coulddrive.schema.resource import (
    CreateResourceParam,
    UpdateResourceParam,
    GetResourceDetail,
    GetResourceListParam,
    ResourceStatistics,
    CreateResourceViewHistoryParam,
    GetResourceViewHistoryDetail,
    GetResourceViewHistoryListParam,
    ResourceViewTrendResponse,
    GetResourceViewTrendParam,
    UpdateResourceViewCountParam,
    UpdateResourceUserParam
)
from backend.app.coulddrive.schema.enum import (
    ResourceDomain,
    EducationSubject,
    TechnologySubject,
    EntertainmentSubject,
    DOMAIN_SUBJECT_MAPPING
)
from backend.app.coulddrive.service.resource_service import resource_service, resource_view_history_service
from backend.common.pagination import DependsPagination
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession

router = APIRouter()


@router.get(
    '/domain-subjects',
    summary='获取领域和科目映射关系',
    response_model=ResponseSchemaModel[dict],
    dependencies=[DependsJwtAuth]
)
async def get_domain_subjects(
    request: Request
) -> ResponseSchemaModel[dict]:
    """
    获取领域和科目映射关系
    
    :param request: 请求对象
    :return: 领域和科目映射关系
    """
    # 构建返回数据
    result = {
        'domains': [{'label': domain.value, 'value': domain.value} for domain in ResourceDomain],
        'subjects': DOMAIN_SUBJECT_MAPPING,
        'domain_subject_options': {
            domain_value: [{'label': subject, 'value': subject} for subject in subjects]
            for domain_value, subjects in DOMAIN_SUBJECT_MAPPING.items()
        }
    }
    return response_base.success(data=result)


@router.get(
    '/subjects/{domain}',
    summary='根据领域获取科目列表',
    response_model=ResponseSchemaModel[list],
    dependencies=[DependsJwtAuth]
)
async def get_subjects_by_domain(
    request: Request,
    domain: Annotated[str, Path(description='领域名称')]
) -> ResponseSchemaModel[list]:
    """
    根据领域获取科目列表
    
    :param request: 请求对象
    :param domain: 领域名称
    :return: 科目列表
    """
    subjects = DOMAIN_SUBJECT_MAPPING.get(domain, [])
    subject_options = [{'label': subject, 'value': subject} for subject in subjects]
    return response_base.success(data=subject_options)


@router.get(
    '',
    summary='获取资源列表',
    dependencies=[DependsJwtAuth, DependsPagination]
)
async def get_resource_list(
    request: Request,
    db: CurrentSession,
    params: Annotated[GetResourceListParam, Depends()]
) -> ResponseModel:
    """
    获取资源列表
    
    :param request: 请求对象
    :param db: 数据库会话
    :param params: 查询参数
    :return: 资源列表
    """
    page_data = await resource_service.get_resource_list(db, params)
    return response_base.success(data=page_data)


@router.get(
    '/statistics',
    summary='获取资源统计信息',
    response_model=ResponseSchemaModel[ResourceStatistics],
    dependencies=[DependsJwtAuth]
)
async def get_resource_statistics(
    request: Request,
    db: CurrentSession,
    user_id: Annotated[int | None, Query(description='用户ID')] = None
) -> ResponseSchemaModel[ResourceStatistics]:
    """
    获取资源统计信息
    
    :param request: 请求对象
    :param db: 数据库会话
    :param user_id: 用户ID
    :return: 资源统计信息
    """
    stats = await resource_service.get_resource_statistics(db, user_id)
    return response_base.success(data=stats)


@router.get(
    '/view-trend',
    summary='获取资源浏览量趋势',
    response_model=ResponseSchemaModel[ResourceViewTrendResponse],
    dependencies=[DependsJwtAuth]
)
async def get_resource_view_trend(
    request: Request,
    db: CurrentSession,
    params: Annotated[GetResourceViewTrendParam, Depends()]
) -> ResponseSchemaModel[ResourceViewTrendResponse]:
    """
    获取资源浏览量趋势
    
    :param request: 请求对象
    :param db: 数据库会话
    :param params: 查询参数
    :return: 浏览量趋势数据
    """
    trend_data = await resource_view_history_service.get_view_trend(db, params)
    return response_base.success(data=trend_data)


@router.post('', summary='创建资源', dependencies=[DependsJwtAuth])
async def create_resource(
    request: Request,
    db: CurrentSession,
    params: Annotated[CreateResourceParam, Depends()]
) -> ResponseSchemaModel[GetResourceDetail]:
    """
    创建资源
    
    :param request: 请求对象
    :param db: 数据库会话
    :param params: 创建参数
    :return: 资源详情
    """
    resource = await resource_service.create_resource(db, params, request.user.id)
    return response_base.success(data=resource)


@router.get(
    '/{resource_id}',
    summary='获取资源详情',
    response_model=ResponseSchemaModel[GetResourceDetail],
    dependencies=[DependsJwtAuth]
)
async def get_resource_detail(
    request: Request,
    db: CurrentSession,
    resource_id: Annotated[int, Path(description='资源ID')]
) -> ResponseSchemaModel[GetResourceDetail]:
    """
    获取资源详情
    
    :param request: 请求对象
    :param db: 数据库会话
    :param resource_id: 资源ID
    :return: 资源详情
    """
    resource = await resource_service.get_resource_detail(db, resource_id)
    return response_base.success(data=resource)


@router.put(
    '/{resource_id}',
    summary='更新资源',
    response_model=ResponseSchemaModel[GetResourceDetail],
    dependencies=[DependsJwtAuth]
)
async def update_resource(
    request: Request,
    db: CurrentSession,
    resource_id: Annotated[int, Path(description='资源ID')],
    obj: UpdateResourceUserParam,
    auto_refresh: Annotated[bool, Query(description='是否自动刷新分享信息')] = False
) -> ResponseSchemaModel[GetResourceDetail]:
    """
    更新资源
    
    :param request: 请求对象
    :param db: 数据库会话
    :param resource_id: 资源ID
    :param obj: 更新参数
    :param auto_refresh: 是否自动刷新分享信息
    :return: 更新后的资源详情
    """
    # 将用户输入参数转换为完整的更新参数
    update_param = UpdateResourceParam(**obj.model_dump(exclude_unset=True))
    resource = await resource_service.update_resource(db, resource_id, update_param, request.user.id, auto_refresh)
    return response_base.success(data=resource)


@router.put(
    '/{resource_id}/refresh-share-info',
    summary='刷新资源分享信息',
    response_model=ResponseSchemaModel[GetResourceDetail],
    dependencies=[DependsJwtAuth]
)
async def refresh_resource_share_info(
    request: Request,
    db: CurrentSession,
    resource_id: Annotated[int, Path(description='资源ID')]
) -> ResponseSchemaModel[GetResourceDetail]:
    """
    刷新资源分享信息
    
    :param request: 请求对象
    :param db: 数据库会话
    :param resource_id: 资源ID
    :return: 更新后的资源详情
    """
    resource = await resource_service.refresh_share_info(db, resource_id, request.user.id)
    return response_base.success(data=resource)


@router.delete(
    '/{resource_id}',
    summary='删除资源',
    response_model=ResponseModel,
    dependencies=[DependsJwtAuth]
)
async def delete_resource(
    request: Request,
    db: CurrentSession,
    resource_id: Annotated[int, Path(description='资源ID')]
) -> ResponseModel:
    """
    删除资源
    
    :param request: 请求对象
    :param db: 数据库会话
    :param resource_id: 资源ID
    :return: 删除结果
    """
    await resource_service.delete_resource(db, resource_id, request.user.id)
    return response_base.success()


# 浏览量历史记录相关接口
@router.post(
    '/{resource_id}/view-history',
    summary='记录资源浏览量',
    response_model=ResponseSchemaModel[GetResourceViewHistoryDetail],
    dependencies=[DependsJwtAuth]
)
async def create_resource_view_history(
    request: Request,
    db: CurrentSession,
    resource_id: Annotated[int, Path(description='资源ID')],
    params: Annotated[CreateResourceViewHistoryParam, Depends()]
) -> ResponseSchemaModel[GetResourceViewHistoryDetail]:
    """
    记录资源浏览量
    
    :param request: 请求对象
    :param db: 数据库会话
    :param resource_id: 资源ID
    :param params: 创建参数
    :return: 浏览量历史记录详情
    """
    history = await resource_view_history_service.create_view_history(db, params)
    return response_base.success(data=history)


@router.get(
    '/{resource_id}/view-history',
    summary='获取资源浏览量历史',
    dependencies=[DependsJwtAuth, DependsPagination]
)
async def get_resource_view_history(
    request: Request,
    db: CurrentSession,
    resource_id: Annotated[int, Path(description='资源ID')],
    params: Annotated[GetResourceViewHistoryListParam, Depends()]
) -> ResponseModel:
    """
    获取资源浏览量历史
    
    :param request: 请求对象
    :param db: 数据库会话
    :param resource_id: 资源ID
    :param params: 查询参数
    :return: 浏览量历史记录列表
    """
    page_data = await resource_view_history_service.get_view_history_list(db, params)
    return response_base.success(data=page_data)


@router.put(
    '/{resource_id}/view-count',
    summary='更新资源浏览量',
    response_model=ResponseModel,
    dependencies=[DependsJwtAuth]
)
async def update_resource_view_count(
    request: Request,
    db: CurrentSession,
    resource_id: Annotated[int, Path(description='资源ID')],
    params: Annotated[UpdateResourceViewCountParam, Depends()]
) -> ResponseModel:
    """
    更新资源浏览量
    
    :param request: 请求对象
    :param db: 数据库会话
    :param resource_id: 资源ID
    :param params: 更新参数
    :return: 更新结果
    """
    await resource_view_history_service.update_view_count(db, params)
    return response_base.success()


@router.delete('/view-history/clean', summary='清理旧的浏览量历史记录', dependencies=[DependsJwtAuth])
async def clean_old_view_history(
    db: CurrentSession,
    days: Annotated[int, Query(description='保留天数')] = 30
) -> ResponseModel:
    """清理旧的浏览量历史记录"""
    count = await run_in_threadpool(resource_view_history_service.clean_old_view_history, db, days)
    return await response_base.success(msg=f'清理完成，删除了 {count} 条记录') 