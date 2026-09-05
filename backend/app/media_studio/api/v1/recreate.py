#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from fastapi import APIRouter

from backend.app.media_studio.schema.media import (
    OneClickRecreateParam,
    OneClickRecreateResult,
)
from backend.app.media_studio.service import media_studio_service
from backend.common.response.response_schema import ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession

router = APIRouter()


@router.post(
    '/recreate',
    summary='一键二创流水线（解析 -> 提炼 Prompt -> 容灾生图）',
    dependencies=[DependsJwtAuth],
)
async def one_click_recreate(
    db: CurrentSession,
    param: OneClickRecreateParam,
) -> ResponseSchemaModel[OneClickRecreateResult]:
    """
    一键全自动二创：传入抖音/小红书链接，后台自动解析无水印媒体与文案，提炼场景描述词，并调用高可用中转站生成二创作品图片。

    :param db: 数据库会话
    :param param: 一键二创参数
    :return: 包含原作品详情与生成的全新二创图片列表
    """
    data = await media_studio_service.one_click_recreate(db=db, param=param)
    return response_base.success(data=data)