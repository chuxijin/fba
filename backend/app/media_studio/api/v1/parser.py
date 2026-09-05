#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from fastapi import APIRouter, Depends

from backend.app.media_studio.schema.media import (
    MediaParseParam,
    UnifiedMediaResponse,
)
from backend.app.media_studio.service import media_studio_service
from backend.common.response.response_schema import ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth

router = APIRouter()


@router.post(
    '/parse',
    summary='解析平台作品（抖音/小红书）',
    dependencies=[DependsJwtAuth],
)
async def parse_media(
    param: MediaParseParam,
) -> ResponseSchemaModel[UnifiedMediaResponse]:
    """
    解析指定平台作品链接或分享文本，自动提取标题、正文、无水印图片/视频及作者信息

    :param param: 解析请求入参
    :return: 统一规范作品数据
    """
    data = await media_studio_service.parse_media(param)
    return response_base.success(data=data)