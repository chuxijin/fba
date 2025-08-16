#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import Field

from backend.common.schema import SchemaBase


class CopywritingSchema(SchemaBase):
    """作品文案"""

    title: str | None = Field(None, description="标题")
    content: str | None = Field(None, description="内容")
    topics: list[str] | None = Field(None, description="话题列表")


class SocialWorkBase(SchemaBase):
    """作品基础 schema"""

    account_id: int = Field(..., description="账号ID")
    work_url: str = Field(..., description="作品地址")
    copywriting: CopywritingSchema | None = Field(None, description="文案(JSON)")
    external_id: str = Field(..., description="平台作品ID")
    published_at: datetime | None = Field(None, description="发布时间")


class CreateSocialWorkParam(SchemaBase):
    """创建作品参数"""

    account_id: int = Field(..., description="账号ID")
    work_url: str = Field(..., description="作品地址")
    external_id: str | None = Field(None, description="平台作品ID（可选，后端可自动解析）")
    copywriting: CopywritingSchema | None = Field(None, description="文案(JSON)")
    published_at: datetime | None = Field(None, description="发布时间")


class UpdateSocialWorkParam(SchemaBase):
    """更新作品参数"""

    work_url: str | None = Field(None, description="作品地址")
    external_id: str | None = Field(None, description="平台作品ID")
    copywriting: CopywritingSchema | None = Field(None, description="文案(JSON)")
    published_at: datetime | None = Field(None, description="发布时间")


class GetSocialWorkDetail(SchemaBase):
    """作品详情"""

    id: int = Field(..., description="主键 ID")
    account_id: int = Field(..., description="账号ID")
    work_url: str = Field(..., description="作品地址")
    copywriting: dict[str, Any] | None = Field(None, description="文案(JSON)")
    external_id: str = Field(..., description="平台作品ID")
    published_at: datetime | None = Field(None, description="发布时间")
    created_time: datetime | None = Field(None, description="创建时间")
    updated_time: datetime | None = Field(None, description="更新时间")


