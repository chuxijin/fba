#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated, Any

from fastapi import APIRouter, Depends

from backend.common.response.response_schema import ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.plugin.webhook.schema.cloud_event import CloudEventCreate
from backend.plugin.webhook.service.outbound_service import outbound_service

router = APIRouter()


@router.post(
    '',
    summary='手动发布事件',
    dependencies=[DependsJwtAuth],
)
async def publish_event(obj: CloudEventCreate) -> ResponseSchemaModel[dict[str, Any]]:
    """
    手动发布事件, 推送到所有订阅了该事件类型的 Endpoint

    用于测试或手动触发事件推送
    """
    count = await outbound_service.dispatch(
        event_type=obj.type,
        data=obj.data,
        subject=obj.subject,
        source=obj.source,
    )
    return response_base.success(data={
        'deliveries_created': count,
        'message': f'已创建 {count} 条投递记录',
    })
