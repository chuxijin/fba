#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from fastapi import APIRouter

from backend.common.response.response_schema import ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession
from backend.plugin.ai.schema.image import (
    AIImageGenerateParam,
    AIImageGenerateResult,
)
from backend.plugin.ai.service.image_service import image_service

router = APIRouter()


@router.post(
    '/generations',
    summary='AI 图像生成（具备多中转站自动故障转移）',
    dependencies=[DependsJwtAuth],
)
async def ai_generate_image(
    db: CurrentSession,
    param: AIImageGenerateParam,
) -> ResponseSchemaModel[AIImageGenerateResult]:
    """
    通过 AI 中转站调用生图模型（如 DALL-E 3、FLUX.1、Midjourney 等）
    若当前首选或主中转站请求失败，将自动尝试其他启用的备选中转站，保障高可用。

    :param db: 数据库会话
    :param param: 生图参数
    :return: 包含生成的图片 URL 及实际生效节点信息的结构化数据
    """
    data = await image_service.generate(db=db, param=param)
    return response_base.success(data=data)