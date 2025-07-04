#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Path, Query, Request

from backend.common.pagination import DependsPagination, PageData, paging_data
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.common.security.permission import RequestPermission
from backend.common.security.rbac import DependsRBAC
from backend.database.db import CurrentSession
from backend.plugin.webhook.schema.webhook import (
    DeleteWebhookParam,
    GetWebhookDetail,
    HeaderValidationRule,
    UpdateWebhookParam,
    WebhookListParam,
    WebhookReceiveParam,
)
from backend.plugin.webhook.service.webhook_service import webhook_service

router = APIRouter()


@router.post('/receive', summary='通用Webhook接收')
async def receive_webhook(request: Request) -> ResponseSchemaModel[dict[str, Any]]:
    """通用Webhook接收，支持所有格式"""
    result = await webhook_service.receive_generic_webhook(request=request)
    return response_base.success(data=result)


@router.post('/receive/structured', summary='结构化Webhook接收')
async def receive_structured_webhook(request: Request, obj: WebhookReceiveParam) -> ResponseSchemaModel[dict[str, Any]]:
    """结构化Webhook接收，使用我们的schema格式"""
    result = await webhook_service.receive_webhook(request=request, obj=obj)
    return response_base.success(data=result)


@router.post('/receive/standard', summary='Standard Webhooks接收')
async def receive_standard_webhook(request: Request) -> ResponseSchemaModel[dict[str, Any]]:
    """Standard Webhooks专用接收，严格按照Standard Webhooks规范验证"""
    result = await webhook_service.receive_standard_webhook(request=request)
    return response_base.success(data=result)


@router.post('/receive/validated', summary='接收需要验证的Webhook事件')
async def receive_validated_webhook(
    request: Request, 
    obj: WebhookReceiveParam,
    validation_rules: list[HeaderValidationRule] | None = None,
    secret_key: Annotated[str | None, Query(description='签名验证密钥')] = None
) -> ResponseSchemaModel[dict[str, Any]]:
    """接收需要Header验证和签名验证的Webhook事件"""
    result = await webhook_service.receive_webhook(
        request=request, 
        obj=obj, 
        validation_rules=validation_rules,
        secret_key=secret_key
    )
    return response_base.success(data=result)


@router.get('/{pk}', summary='获取Webhook事件详情', dependencies=[DependsJwtAuth])
async def get_webhook(pk: Annotated[int, Path(description='Webhook事件 ID')]) -> ResponseSchemaModel[GetWebhookDetail]:
    webhook = await webhook_service.get(pk=pk)
    return response_base.success(data=webhook)


@router.get(
    '',
    summary='分页获取Webhook事件列表',
    dependencies=[
        DependsJwtAuth,
        DependsPagination,
    ],
)
async def get_webhooks_paged(
    db: CurrentSession,
    event_type: Annotated[str | None, Query(description='事件类型')] = None,
    source: Annotated[str | None, Query(description='事件来源')] = None,
    status: Annotated[int | None, Query(description='处理状态')] = None,
    start_time: Annotated[str | None, Query(description='开始时间')] = None,
    end_time: Annotated[str | None, Query(description='结束时间')] = None,
) -> ResponseSchemaModel[PageData[GetWebhookDetail]]:
    params = WebhookListParam(
        event_type=event_type,
        source=source,
        status=status,
        start_time=start_time,
        end_time=end_time
    )
    webhook_select = await webhook_service.get_select(params)
    page_data = await paging_data(db, webhook_select)
    return response_base.success(data=page_data)


@router.put(
    '/{pk}',
    summary='更新Webhook事件',
    dependencies=[
        Depends(RequestPermission('sys:webhook:edit')),
        DependsRBAC,
    ],
)
async def update_webhook(
    pk: Annotated[int, Path(description='Webhook事件 ID')], 
    obj: UpdateWebhookParam
) -> ResponseModel:
    count = await webhook_service.update(pk=pk, obj=obj)
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.delete(
    '',
    summary='批量删除Webhook事件',
    dependencies=[
        Depends(RequestPermission('sys:webhook:del')),
        DependsRBAC,
    ],
)
async def delete_webhooks(obj: DeleteWebhookParam) -> ResponseModel:
    count = await webhook_service.delete(obj=obj)
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.post(
    '/retry',
    summary='重试失败的Webhook事件',
    dependencies=[
        Depends(RequestPermission('sys:webhook:retry')),
        DependsRBAC,
    ],
)
async def retry_failed_webhooks() -> ResponseSchemaModel[dict[str, Any]]:
    """重试失败的Webhook事件"""
    retry_count = await webhook_service.retry_failed_webhooks()
    return response_base.success(data={'retry_count': retry_count, 'message': f'已重试 {retry_count} 个失败的Webhook事件'})


@router.get(
    '/pending',
    summary='获取待处理的Webhook事件',
    dependencies=[
        DependsJwtAuth,
    ],
)
async def get_pending_webhooks(
    limit: Annotated[int, Query(description='限制数量', ge=1, le=1000)] = 100
) -> ResponseSchemaModel[list[GetWebhookDetail]]:
    """获取待处理的Webhook事件列表"""
    webhooks = await webhook_service.get_pending_webhooks(limit=limit)
    return response_base.success(data=webhooks)


 