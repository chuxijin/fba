#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from fastapi import APIRouter

from backend.app.media_studio.service import media_studio_service
from backend.common.response.response_schema import ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession
from backend.plugin.ai.schema.image import (
    AIImageGenerateParam,
    AIImageGenerateResult,
)

router = APIRouter()


@router.post(
    '/image-gen',
    summary='单步 AI 生图（多中转站自动故障转移）',
    dependencies=[DependsJwtAuth],
)
async def media_studio_generate_image(
    db: CurrentSession,
    param: AIImageGenerateParam,
) -> ResponseSchemaModel[AIImageGenerateResult]:
    """
    通过配置的 AI 中转站生图，若主节点异常将自动切换至下一个可用节点。

    :param db: 数据库会话
    :param param: 生图参数
    :return: 包含生成的图片 URL 及实际生效节点信息的结构化数据
    """
    data = await media_studio_service.generate_image(db=db, param=param)
    return response_base.success(data=data)