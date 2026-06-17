#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Path, Query, Request

from backend.common.response.response_schema import ResponseSchemaModel, response_base
from backend.plugin.webhook.schema.inbound import InboundReceiveParam, InboundReceiveResult
from backend.plugin.webhook.service.inbound_service import inbound_service

router = APIRouter()


@router.post('/{source}', summary='接收入站 Webhook')
async def receive_inbound(
    request: Request,
    source: Annotated[str, Path(description='事件来源 (github/stripe/wechat_pay/generic)')],
    secret: Annotated[str | None, Query(description='签名密钥')] = None,
) -> ResponseSchemaModel[InboundReceiveResult]:
    """
    接收外部系统的 Webhook 推送

    - 自动验证 Standard Webhooks 签名 (如果配置了 secret)
    - 自动去重 (基于 event_id)
    - 异步分发到注册的 Handler
    """
    result = await inbound_service.receive(request=request, source=source, secret=secret)
    return response_base.success(data=result)


@router.post('/structured/{source}', summary='结构化入站接收')
async def receive_structured(
    obj: InboundReceiveParam,
    source: Annotated[str, Path(description='事件来源')],
) -> ResponseSchemaModel[InboundReceiveResult]:
    """
    结构化入站接收 (使用 JSON body 传递事件数据)

    适用于内部系统之间的事件传递
    """
    result = await inbound_service.receive_structured(obj=obj, source=source)
    return response_base.success(data=result)
