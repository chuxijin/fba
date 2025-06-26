#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Request

from backend.common.pagination import DependsPagination, PageData, paging_data
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.common.security.rbac import DependsRBAC
from backend.database.db import CurrentSession
from backend.plugin.app_auth.schema.package import (
    CreatePackageParam,
    GetPackageDetail,
    UpdatePackageParam,
)
from backend.plugin.app_auth.service.package_service import package_service

router = APIRouter()


@router.post('', summary='创建套餐', dependencies=[DependsRBAC])
async def create_package(request: Request, obj: CreatePackageParam) -> ResponseSchemaModel[GetPackageDetail]:
    """
    创建新套餐
    
    :param request: FastAPI 请求对象
    :param obj: 套餐创建参数
    :return:
    """
    data = await package_service.create(request=request, obj=obj)
    return response_base.success(data=data)


@router.delete('/{pk}', summary='删除套餐', dependencies=[DependsRBAC])
async def delete_package(request: Request, pk: Annotated[int, Path(description='套餐ID')]) -> ResponseModel:
    """
    删除套餐
    
    :param request: FastAPI 请求对象
    :param pk: 套餐ID
    :return:
    """
    count = await package_service.delete(request=request, package_id=pk)
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.put('/{pk}', summary='更新套餐', dependencies=[DependsRBAC])
async def update_package(
    request: Request, pk: Annotated[int, Path(description='套餐ID')], obj: UpdatePackageParam
) -> ResponseModel:
    """
    更新套餐信息
    
    :param request: FastAPI 请求对象
    :param pk: 套餐ID
    :param obj: 套餐更新参数
    :return:
    """
    count = await package_service.update(request=request, package_id=pk, obj=obj)
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.get('', summary='分页获取套餐列表', dependencies=[DependsJwtAuth, DependsPagination])
async def get_pagination_packages(
    db: CurrentSession,
    application_id: Annotated[int | None, Query(description='应用ID')] = None,
    name: Annotated[str | None, Query(description='套餐名称')] = None,
    is_active: Annotated[bool | None, Query(description='是否启用')] = None,
) -> ResponseModel:
    """
    分页获取套餐列表
    
    :param db: 数据库会话
    :param application_id: 应用ID
    :param name: 套餐名称
    :param is_active: 是否启用
    :return:
    """
    # 暂时使用自定义查询方法，避免分页序列化问题
    packages = await package_service.get_pagination_list(
        db, application_id=application_id, name=name, is_active=is_active
    )
    
    # 简单的分页处理（这里可以后续优化为真正的分页）
    page_data = {
        'items': packages,
        'total': len(packages),
        'page': 1,
        'size': len(packages),
        'total_pages': 1,
        'links': {
            'first': '',
            'last': '',
            'self': '',
        }
    }
    return response_base.success(data=page_data)


@router.get('/{pk}', summary='获取套餐详情', dependencies=[DependsJwtAuth])
async def get_package(pk: Annotated[int, Path(description='套餐ID')]) -> ResponseSchemaModel[GetPackageDetail]:
    """
    获取套餐详情
    
    :param pk: 套餐ID
    :return:
    """
    data = await package_service.get(package_id=pk)
    return response_base.success(data=data)


@router.get('/by-application/{application_id}/options', summary='根据应用获取套餐选项', dependencies=[DependsJwtAuth])
async def get_package_options_by_application(
    application_id: Annotated[int, Path(description='应用ID')]
) -> ResponseSchemaModel[list[dict]]:
    """根据应用获取套餐选项，用于下拉选择"""
    data = await package_service.get_options_by_application(application_id=application_id)
    return response_base.success(data=data)