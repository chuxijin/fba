#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query

from backend.common.pagination import DependsPagination, PageData, paging_data
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.common.security.rbac import DependsRBAC
from backend.database.db import CurrentSession
from backend.plugin.app_auth.schema.version import (
    CreateVersionParam,
    GetVersionDetail,
    UpdateVersionParam,
)
from backend.plugin.app_auth.service.version_service import version_service

router = APIRouter()


@router.post('', summary='创建版本', dependencies=[DependsRBAC])
async def create_version(obj: CreateVersionParam) -> ResponseSchemaModel[GetVersionDetail]:
    """
    创建新版本
    
    :param obj: 版本创建参数
    :return:
    """
    data = await version_service.create(obj=obj)
    return response_base.success(data=data)


@router.delete('/{pk}', summary='删除版本', dependencies=[DependsRBAC])
async def delete_version(pk: Annotated[int, Path(description='版本ID')]) -> ResponseModel:
    """
    删除版本
    
    :param pk: 版本ID
    :return:
    """
    count = await version_service.delete(pk=pk)
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.put('/{pk}', summary='更新版本', dependencies=[DependsRBAC])
async def update_version(
    pk: Annotated[int, Path(description='版本ID')], obj: UpdateVersionParam
) -> ResponseModel:
    """
    更新版本信息
    
    :param pk: 版本ID
    :param obj: 版本更新参数
    :return:
    """
    count = await version_service.update(pk=pk, obj=obj)
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.get('', summary='分页获取版本列表', dependencies=[DependsJwtAuth, DependsPagination])
async def get_pagination_versions(
    db: CurrentSession,
    application_id: Annotated[int | None, Query(description='应用ID')] = None,
    version_name: Annotated[str | None, Query(description='版本名称')] = None,
    is_active: Annotated[bool | None, Query(description='是否启用')] = None,
) -> ResponseModel:
    """
    分页获取版本列表
    
    :param db: 数据库会话
    :param application_id: 应用ID
    :param version_name: 版本名称
    :param is_active: 是否启用
    :return:
    """
    select = version_service.get_select(application_id=application_id, version_name=version_name, is_active=is_active)
    page_data = await paging_data(db, select)
    return response_base.success(data=page_data)


@router.get('/{pk}', summary='获取版本详情', dependencies=[DependsJwtAuth])
async def get_version(pk: Annotated[int, Path(description='版本ID')]) -> ResponseSchemaModel[GetVersionDetail]:
    """
    获取版本详情
    
    :param pk: 版本ID
    :return:
    """
    data = await version_service.get(pk=pk)
    return response_base.success(data=data)


@router.get('/by-application/{application_id}/options', summary='根据应用获取版本选项', dependencies=[DependsJwtAuth])
async def get_version_options_by_application(
    application_id: Annotated[int, Path(description='应用ID')]
) -> ResponseSchemaModel[list[dict]]:
    """根据应用获取版本选项，用于下拉选择"""
    data = await version_service.get_options_by_application(application_id=application_id)
    return response_base.success(data=data) 