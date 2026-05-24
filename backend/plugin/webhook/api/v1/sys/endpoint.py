#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query

from backend.common.pagination import DependsPagination, PageData, paging_data
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.common.security.permission import RequestPermission
from backend.common.security.rbac import DependsRBAC
from backend.database.db import CurrentSession
from backend.plugin.webhook.schema.endpoint import (
    CreateEndpointParam,
    EndpointListParam,
    GetEndpointDetail,
    RotateSecretResult,
    TestEndpointResult,
    UpdateEndpointParam,
)
from backend.plugin.webhook.service.endpoint_service import endpoint_service

router = APIRouter()


@router.post(
    '',
    summary='创建出站端点',
    dependencies=[
        Depends(RequestPermission('sys:webhook_endpoint:add')),
        DependsRBAC,
    ],
)
async def create_endpoint(obj: CreateEndpointParam) -> ResponseSchemaModel[GetEndpointDetail]:
    """创建出站端点, 自动生成签名密钥"""
    endpoint = await endpoint_service.create(obj=obj)
    return response_base.success(data=GetEndpointDetail.model_validate(endpoint))


@router.get(
    '',
    summary='分页获取端点列表',
    dependencies=[
        DependsJwtAuth,
        DependsPagination,
    ],
)
async def list_endpoints(
    db: CurrentSession,
    name: Annotated[str | None, Query(description='端点名称')] = None,
    is_active: Annotated[bool | None, Query(description='是否启用')] = None,
    event_type: Annotated[str | None, Query(description='订阅的事件类型')] = None,
) -> ResponseSchemaModel[PageData[GetEndpointDetail]]:
    """分页获取端点列表"""
    params = EndpointListParam(name=name, is_active=is_active, event_type=event_type)
    select = await endpoint_service.get_select(params)
    page_data = await paging_data(db, select)
    return response_base.success(data=page_data)


@router.get('/{pk}', summary='获取端点详情', dependencies=[DependsJwtAuth])
async def get_endpoint(pk: Annotated[int, Path(description='端点 ID')]) -> ResponseSchemaModel[GetEndpointDetail]:
    """获取端点详情"""
    endpoint = await endpoint_service.get(pk=pk)
    return response_base.success(data=GetEndpointDetail.model_validate(endpoint))


@router.put(
    '/{pk}',
    summary='更新端点',
    dependencies=[
        Depends(RequestPermission('sys:webhook_endpoint:edit')),
        DependsRBAC,
    ],
)
async def update_endpoint(
    pk: Annotated[int, Path(description='端点 ID')],
    obj: UpdateEndpointParam,
) -> ResponseModel:
    """更新端点配置"""
    count = await endpoint_service.update(pk=pk, obj=obj)
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.delete(
    '',
    summary='批量删除端点',
    dependencies=[
        Depends(RequestPermission('sys:webhook_endpoint:del')),
        DependsRBAC,
    ],
)
async def delete_endpoints(pks: list[int]) -> ResponseModel:
    """批量删除端点"""
    count = await endpoint_service.delete(pks=pks)
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.post(
    '/{pk}/rotate-secret',
    summary='轮换端点密钥',
    dependencies=[
        Depends(RequestPermission('sys:webhook_endpoint:edit')),
        DependsRBAC,
    ],
)
async def rotate_secret(pk: Annotated[int, Path(description='端点 ID')]) -> ResponseSchemaModel[RotateSecretResult]:
    """轮换端点签名密钥, 旧密钥立即失效"""
    result = await endpoint_service.rotate_secret(pk=pk)
    return response_base.success(data=result)


@router.post(
    '/{pk}/test',
    summary='测试推送到端点',
    dependencies=[DependsJwtAuth],
)
async def test_endpoint(pk: Annotated[int, Path(description='端点 ID')]) -> ResponseSchemaModel[TestEndpointResult]:
    """发送测试事件到端点, 验证连通性和签名"""
    result = await endpoint_service.test_push(pk=pk)
    return response_base.success(data=result)
