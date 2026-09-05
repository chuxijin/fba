#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from pydantic import BaseModel, Field


class MediaAuthor(BaseModel):
    """作者信息"""

    id: str | None = Field(default=None, description='作者 ID')
    name: str = Field(..., description='作者昵称')
    avatar: str | None = Field(default=None, description='作者头像 URL')
    url: str | None = Field(default=None, description='作者主页 URL')


class MediaStats(BaseModel):
    """统计信息"""

    like_count: int | None = Field(default=None, description='点赞数')
    comment_count: int | None = Field(default=None, description='评论数')
    collect_count: int | None = Field(default=None, description='收藏数')
    share_count: int | None = Field(default=None, description='分享数')


class UnifiedMediaResponse(BaseModel):
    """统一作品解析出参"""

    platform: str = Field(..., description='平台名称 (douyin/xhs)')
    media_type: str = Field(..., description='作品类型 (video/image)')
    title: str = Field(default='', description='作品标题')
    content: str = Field(default='', description='作品正文/文案描述')
    tags: list[str] = Field(default_factory=list, description='话题标签列表')
    cover_url: str | None = Field(default=None, description='封面图直链')
    images: list[str] = Field(default_factory=list, description='无水印高清图片列表')
    video_url: str | None = Field(default=None, description='无水印视频直链')
    author: MediaAuthor | None = Field(default=None, description='作者信息')
    stats: MediaStats | None = Field(default=None, description='互动统计')
    raw_url: str = Field(..., description='提取到的有效原始 URL')


class MediaParseParam(BaseModel):
    """解析入参"""

    url_or_text: str = Field(..., description='分享链接或包含链接的分享文案')
    cookie: str | None = Field(default=None, description='可选，用于反爬风控时的自定义 Cookie')


class OneClickRecreateParam(BaseModel):
    """一键二创入参"""

    url_or_text: str = Field(..., description='分享链接或包含链接的分享文案')
    cookie: str | None = Field(default=None, description='可选，自定义 Cookie')
    prompt_style: str | None = Field(default=None, description='附加风格描述，可为空')
    custom_prompt: str | None = Field(default=None, description='用户自定义二创提示词与要求')
    model: str = Field(default='dall-e-3', description='生图模型名称，例如 dall-e-3 / flux-schnell')
    size: str = Field(default='1024x1024', description='图片尺寸，例如 1024x1024 / 1024x1792')
    reference_image_url: str | None = Field(default=None, description='指定或选定作为参考图的直链 URL')
    provider_id: int | None = Field(default=None, description='指定首选中转站 ID')


class OneClickRecreateResult(BaseModel):
    """一键二创结果"""

    original_media: UnifiedMediaResponse = Field(..., description='解析出的原作品结构化数据')
    generated_prompt: str = Field(..., description='提炼出的生图提示词')
    generated_images: list[str] = Field(default_factory=list, description='生成的全新图片直链列表')
    provider_name: str = Field(..., description='实际生效的中转站名称')
    elapsed_seconds: float = Field(..., description='总耗时（秒）')