#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Request

from backend.common.pagination import DependsPagination, PageData, paging_data
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.common.security.rbac import DependsRBAC
from backend.database.db import CurrentSession
from backend.plugin.app_auth.schema.authorization import (
    AuthorizeDeviceParam,
    CheckAuthorizationParam,
    GetAuthorizationDetail,
    RedeemCodeAuthParam,
    UpdateAuthorizationTimeParam,
)
from backend.plugin.app_auth.service.authorization_service import authorization_service

router = APIRouter()


@router.post('/manual', summary='手动授权设备', dependencies=[DependsRBAC])
async def manual_authorize_device(request: Request, obj: AuthorizeDeviceParam) -> ResponseSchemaModel[GetAuthorizationDetail]:
    """
    手动授权设备
    
    :param request: FastAPI 请求对象
    :param obj: 授权参数
    :return:
    """
    data = await authorization_service.manual_authorize(request=request, obj=obj)
    return response_base.success(data=data)


@router.post('/redeem', summary='兑换码授权')
async def redeem_code_authorize(obj: RedeemCodeAuthParam) -> ResponseSchemaModel[GetAuthorizationDetail]:
    """
    兑换码授权
    
    :param obj: 兑换码授权参数
    :return:
    """
    data = await authorization_service.redeem_code_auth(obj=obj)
    return response_base.success(data=data)


@router.post('/check', summary='检查设备授权状态')
async def check_authorization(obj: CheckAuthorizationParam) -> ResponseModel:
    """
    检查设备授权状态
    
    :param obj: 检查授权参数
    :return:
    """
    result = await authorization_service.check_authorization(obj=obj)
    return response_base.success(data=result)


@router.get('', summary='分页获取授权列表', dependencies=[DependsJwtAuth, DependsPagination])
async def get_pagination_authorizations(
    db: CurrentSession,
    application_id: Annotated[int | None, Query(description='应用ID')] = None,
    device_id: Annotated[int | None, Query(description='设备ID')] = None,
    auth_type: Annotated[int | None, Query(description='授权类型')] = None,
    status: Annotated[int | None, Query(description='授权状态')] = None,
) -> ResponseModel:
    """
    分页获取授权列表
    
    :param db: 数据库会话
    :param application_id: 应用ID
    :param device_id: 设备ID
    :param auth_type: 授权类型
    :param status: 授权状态
    :return:
    """
    select = authorization_service.get_select(
        application_id=application_id, device_id=device_id, auth_type=auth_type, status=status
    )
    page_data = await paging_data(db, select)
    return response_base.success(data=page_data)


@router.get('/application/{application_id}/trend', summary='获取应用注册趋势', dependencies=[DependsJwtAuth])
async def get_application_registration_trend(
    application_id: Annotated[int, Path(description='应用ID')],
    days: Annotated[int, Query(description='统计天数')] = 30
) -> ResponseModel:
    """
    获取应用注册趋势数据
    
    :param application_id: 应用ID
    :param days: 统计天数，默认30天
    :return:
    """
    data = await authorization_service.get_application_registration_trend(application_id, days)
    return response_base.success(data=data)


@router.get('/device/{device_id}/history', summary='获取设备授权历史', dependencies=[DependsJwtAuth])
async def get_device_authorization_history(
    device_id: Annotated[int, Path(description='设备ID')]
) -> ResponseModel:
    """
    获取设备授权历史
    
    :param device_id: 设备ID
    :return:
    """
    data = await authorization_service.get_device_authorization_history(device_id)
    return response_base.success(data=data)


@router.get('/{pk}', summary='获取授权详情', dependencies=[DependsJwtAuth])
async def get_authorization(pk: Annotated[int, Path(description='授权ID')]) -> ResponseSchemaModel[GetAuthorizationDetail]:
    """
    获取授权详情
    
    :param pk: 授权ID
    :return:
    """
    data = await authorization_service.get(pk=pk)
    return response_base.success(data=data)


@router.put('/{pk}/time', summary='修改授权时间', dependencies=[DependsRBAC])
async def update_authorization_time(
    pk: Annotated[int, Path(description='授权ID')],
    obj: UpdateAuthorizationTimeParam
) -> ResponseModel:
    """
    修改授权时间
    
    :param pk: 授权ID
    :param obj: 修改参数
    :return:
    """
    count = await authorization_service.update_authorization_time(pk=pk, obj=obj)
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.put('/{pk}/disable', summary='使授权失效', dependencies=[DependsRBAC])
async def disable_authorization(pk: Annotated[int, Path(description='授权ID')]) -> ResponseModel:
    """
    使授权失效
    
    :param pk: 授权ID
    :return:
    """
    count = await authorization_service.disable_authorization(pk=pk)
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.delete('/{pk}', summary='删除授权', dependencies=[DependsRBAC])
async def delete_authorization(pk: Annotated[int, Path(description='授权ID')]) -> ResponseModel:
    """
    删除授权
    
    :param pk: 授权ID
    :return:
    """
    count = await authorization_service.delete(pk=pk)
    if count > 0:
        return response_base.success()
    return response_base.fail()