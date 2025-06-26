#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Request

from backend.common.pagination import DependsPagination, PageData, paging_data
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.common.security.rbac import DependsRBAC
from backend.database.db import CurrentSession
from backend.plugin.app_auth.schema.application import (
    CreateApplicationParam,
    GetApplicationDetail,
    UpdateApplicationParam,
)
from backend.plugin.app_auth.service.application_service import application_service

router = APIRouter()


@router.post('', summary='创建应用', dependencies=[DependsRBAC])
async def create_application(request: Request, obj: CreateApplicationParam) -> ResponseSchemaModel[GetApplicationDetail]:
    """
    创建新应用
    
    :param request: FastAPI 请求对象
    :param obj: 应用创建参数
    :return:
    """
    data = await application_service.create(request=request, obj=obj)
    return response_base.success(data=data)


@router.delete('/{pk}', summary='删除应用', dependencies=[DependsRBAC])
async def delete_application(request: Request, pk: Annotated[int, Path(description='应用ID')]) -> ResponseModel:
    """
    删除应用
    
    :param request: FastAPI 请求对象
    :param pk: 应用ID
    :return:
    """
    count = await application_service.delete(request=request, app_id=pk)
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.put('/{pk}', summary='更新应用', dependencies=[DependsRBAC])
async def update_application(
    request: Request, pk: Annotated[int, Path(description='应用ID')], obj: UpdateApplicationParam
) -> ResponseModel:
    """
    更新应用信息
    
    :param request: FastAPI 请求对象
    :param pk: 应用ID
    :param obj: 应用更新参数
    :return:
    """
    count = await application_service.update(request=request, app_id=pk, obj=obj)
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.get('', summary='分页获取应用列表', dependencies=[DependsJwtAuth, DependsPagination])
async def get_pagination_applications(
    db: CurrentSession,
    name: Annotated[str | None, Query(description='应用名称')] = None,
    app_key: Annotated[str | None, Query(description='应用标识')] = None,
    status: Annotated[int | None, Query(description='状态')] = None,
) -> ResponseModel:
    """
    分页获取应用列表
    
    :param db: 数据库会话
    :param name: 应用名称
    :param app_key: 应用标识
    :param status: 状态
    :return:
    """
    select = application_service.get_select(name=name, app_key=app_key, status=status)
    page_data = await paging_data(db, select)
    return response_base.success(data=page_data)


@router.get('/{pk}', summary='获取应用详情', dependencies=[DependsJwtAuth])
async def get_application(pk: Annotated[int, Path(description='应用ID')]) -> ResponseSchemaModel[GetApplicationDetail]:
    """
    获取应用详情
    
    :param pk: 应用ID
    :return:
    """
    data = await application_service.get(app_id=pk)
    return response_base.success(data=data)


@router.get('/all/options', summary='获取所有应用选项', dependencies=[DependsJwtAuth])
async def get_all_application_options() -> ResponseSchemaModel[list[dict]]:
    """获取所有应用选项，用于下拉选择"""
    data = await application_service.get_options()
    return response_base.success(data=data)