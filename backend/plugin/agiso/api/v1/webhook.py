#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Form, Query

from backend.common.response.response_schema import ResponseModel, response_base
from backend.database.db import CurrentSessionTransaction
from backend.plugin.agiso.service.webhook_service import webhook_service

router = APIRouter()


@router.post('/delivery', summary='接收阿奇索推送')
async def receive_agiso_push(
    db: CurrentSessionTransaction,
    json_data: Annotated[str, Form(alias='json', description='推送 JSON 数据')],
    timestamp: Annotated[str, Query(description='时间戳')],
    sign: Annotated[str, Query(description='签名')],
    fromPlatform: Annotated[str | None, Query(description='来源平台')] = None,
    aopic: Annotated[int | None, Query(description='推送类型 2097152:买家付款 2048:自动发货成功')] = None,
) -> ResponseModel:
    """
    统一接收阿奇索推送（买家付款推送、自动发货完成推送）

    :param db: 数据库会话
    :param json_data: 推送 JSON 数据 (Form field name: json)
    :param timestamp: 时间戳
    :param sign: 签名
    :param fromPlatform: 来源平台
    :param aopic: 推送类型
    :return:
    """
    result = await webhook_service.handle_push(json_data, timestamp, sign, fromPlatform, aopic, db=db)
    return response_base.success(data=result)
