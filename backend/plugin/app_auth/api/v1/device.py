#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Request

from backend.common.pagination import DependsPagination, PageData, paging_data
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.common.security.rbac import DependsRBAC
from backend.database.db import CurrentSession
from backend.plugin.app_auth.schema.device import (
    CreateDeviceParam,
    GetDeviceDetail,
    UpdateDeviceParam,
)
from backend.plugin.app_auth.service.device_service import device_service

router = APIRouter()


@router.post('', summary='创建设备', dependencies=[DependsRBAC])
async def create_device(request: Request, obj: CreateDeviceParam) -> ResponseSchemaModel[GetDeviceDetail]:
    """
    创建新设备
    
    :param request: FastAPI 请求对象
    :param obj: 设备创建参数
    :return:
    """
    data = await device_service.create(request=request, obj=obj)
    return response_base.success(data=data)


@router.delete('/{pk}', summary='删除设备', dependencies=[DependsRBAC])
async def delete_device(request: Request, pk: Annotated[int, Path(description='设备ID')]) -> ResponseModel:
    """
    删除设备
    
    :param request: FastAPI 请求对象
    :param pk: 设备ID
    :return:
    """
    count = await device_service.delete(request=request, device_id=pk)
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.put('/{pk}', summary='更新设备', dependencies=[DependsRBAC])
async def update_device(
    request: Request, pk: Annotated[int, Path(description='设备ID')], obj: UpdateDeviceParam
) -> ResponseModel:
    """
    更新设备信息
    
    :param request: FastAPI 请求对象
    :param pk: 设备ID
    :param obj: 设备更新参数
    :return:
    """
    count = await device_service.update(request=request, device_id=pk, obj=obj)
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.get('', summary='分页获取设备列表', dependencies=[DependsJwtAuth, DependsPagination])
async def get_pagination_devices(
    db: CurrentSession,
    device_id: Annotated[str | None, Query(description='设备标识')] = None,
    device_name: Annotated[str | None, Query(description='设备名称')] = None,
    status: Annotated[int | None, Query(description='状态')] = None,
) -> ResponseModel:
    """
    分页获取设备列表
    
    :param db: 数据库会话
    :param device_id: 设备标识
    :param device_name: 设备名称
    :param status: 状态
    :return:
    """
    select = device_service.get_select(device_id=device_id, device_name=device_name, status=status)
    page_data = await paging_data(db, select)
    return response_base.success(data=page_data)


@router.get('/{pk}', summary='获取设备详情', dependencies=[DependsJwtAuth])
async def get_device(pk: Annotated[int, Path(description='设备ID')]) -> ResponseSchemaModel[GetDeviceDetail]:
    """
    获取设备详情
    
    :param pk: 设备ID
    :return:
    """
    data = await device_service.get(device_id=pk)
    return response_base.success(data=data)