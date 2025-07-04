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
from backend.plugin.webhook.schema.webhook import (
    CreateWebhookConfigParam,
    DeleteWebhookConfigParam,
    GetWebhookConfigDetail,
    UpdateWebhookConfigParam,
    WebhookConfigListParam,
)
from backend.plugin.webhook.service.webhook_service import webhook_service

router = APIRouter()


@router.post(
    '',
    summary='创建WebhookConfig',
    dependencies=[
        Depends(RequestPermission('sys:webhook_config:add')),
        DependsRBAC,
    ],
)
async def create_webhook_config(obj: CreateWebhookConfigParam) -> ResponseModel:
    """创建WebhookConfig配置"""
    await webhook_service.create_config(obj=obj)
    return response_base.success()


@router.get('/{pk}', summary='获取WebhookConfig详情', dependencies=[DependsJwtAuth])
async def get_webhook_config(pk: Annotated[int, Path(description='WebhookConfig ID')]) -> ResponseSchemaModel[GetWebhookConfigDetail]:
    """获取WebhookConfig配置详情"""
    webhook_config = await webhook_service.get_config(pk=pk)
    return response_base.success(data=webhook_config)


@router.get(
    '',
    summary='分页获取WebhookConfig列表',
    dependencies=[
        DependsJwtAuth,
        DependsPagination,
    ],
)
async def get_webhook_configs_paged(
    db: CurrentSession,
    name: Annotated[str | None, Query(description='配置名称')] = None,
    endpoint_url: Annotated[str | None, Query(description='接收端点URL')] = None,
    is_active: Annotated[bool | None, Query(description='是否启用')] = None,
) -> ResponseSchemaModel[PageData[GetWebhookConfigDetail]]:
    """分页获取WebhookConfig配置列表"""
    params = WebhookConfigListParam(
        name=name,
        endpoint_url=endpoint_url,
        is_active=is_active
    )
    webhook_config_select = await webhook_service.get_config_select(params=params)
    page_data = await paging_data(db, webhook_config_select)
    return response_base.success(data=page_data)


@router.put(
    '/{pk}',
    summary='更新WebhookConfig',
    dependencies=[
        Depends(RequestPermission('sys:webhook_config:edit')),
        DependsRBAC,
    ],
)
async def update_webhook_config(
    pk: Annotated[int, Path(description='WebhookConfig ID')], 
    obj: UpdateWebhookConfigParam
) -> ResponseModel:
    """更新WebhookConfig配置"""
    count = await webhook_service.update_config(pk=pk, obj=obj)
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.delete(
    '',
    summary='批量删除WebhookConfig',
    dependencies=[
        Depends(RequestPermission('sys:webhook_config:del')),
        DependsRBAC,
    ],
)
async def delete_webhook_configs(obj: DeleteWebhookConfigParam) -> ResponseModel:
    """批量删除WebhookConfig配置"""
    count = await webhook_service.delete_config(obj=obj)
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.put(
    '/{pk}/status',
    summary='更新WebhookConfig状态',
    dependencies=[
        Depends(RequestPermission('sys:webhook_config:edit')),
        DependsRBAC,
    ],
)
async def update_webhook_config_status(
    pk: Annotated[int, Path(description='WebhookConfig ID')],
    is_active: Annotated[bool, Query(description='是否启用')]
) -> ResponseModel:
    """更新WebhookConfig配置状态"""
    count = await webhook_service.update_config_status(pk=pk, is_active=is_active)
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.get(
    '/active',
    summary='获取所有启用的WebhookConfig',
    dependencies=[DependsJwtAuth],
)
async def get_active_webhook_configs() -> ResponseSchemaModel[list[GetWebhookConfigDetail]]:
    """获取所有启用的WebhookConfig配置"""
    configs = await webhook_service.get_active_configs()
    return response_base.success(data=[GetWebhookConfigDetail.model_validate(config) for config in configs]) 