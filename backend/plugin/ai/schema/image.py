#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from pydantic import BaseModel, Field


class AIImageItem(BaseModel):
    """单张生成图片信息"""

    url: str = Field(..., description='图片直链 URL')
    revised_prompt: str | None = Field(default=None, description='模型优化后的 Prompt')


class AIImageGenerateParam(BaseModel):
    """AI 生图请求入参（OpenAI 兼容规范）"""

    prompt: str = Field(..., description='生图提示词')
    model: str = Field(default='dall-e-3', description='模型名称，例如 dall-e-3 / flux-schnell / flux-dev')
    n: int = Field(default=1, ge=1, le=4, description='生成图片数量')
    size: str = Field(default='1024x1024', description='图片尺寸，例如 1024x1024 / 1024x1792 / 1792x1024')
    quality: str = Field(default='standard', description='图像质量 standard / hd')
    image_url: str | None = Field(default=None, description='参考图直链 URL（图生图/参考图二创）')
    provider_id: int | None = Field(default=None, description='首选供应商 ID（若失败将自动故障转移至其他启用节点）')
    timeout: float = Field(default=60.0, description='单个中转站请求超时时间（秒）')


class AIImageGenerateResult(BaseModel):
    """AI 生图响应结果"""

    images: list[AIImageItem] = Field(default_factory=list, description='生成的图片列表')
    provider_id: int = Field(..., description='实际成功出图的供应商 ID')
    provider_name: str = Field(..., description='实际生效的供应商名称')
    model: str = Field(..., description='实际生效的模型名称')
    elapsed_seconds: float = Field(..., description='生图耗时（秒）')