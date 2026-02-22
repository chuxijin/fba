#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from fastapi import APIRouter

from backend.common.response.response_schema import ResponseModel, response_base
from backend.plugin.notify.schema.notify import CreateNotifyParam
from backend.plugin.notify.service.notify_service import notify_service

router = APIRouter()


@router.post('/send', summary='发送通知')
async def send_notification(obj: CreateNotifyParam) -> ResponseModel:
    """
    发送多渠道通知（按优先级降级）

    :param obj: 发送通知参数
    :return:
    """
    result = await notify_service.send(
        title=obj.title,
        content=obj.content,
        channels=obj.channels,
        options=obj.options,
        source='api',
    )
    return response_base.success(data=result.model_dump())
