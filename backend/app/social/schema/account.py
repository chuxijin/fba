#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any

from pydantic import Field

from backend.app.social.model.account import DomainEnum, PlatformEnum
from backend.common.schema import SchemaBase


class SocialAccountBase(SchemaBase):
    """账号基础 schema"""

    name: str = Field(..., description="账号名称")
    homepage: str | None = Field(None, description="主页地址")
    phone: str | None = Field(None, description="电话号码")
    platform: PlatformEnum = Field(..., description="所属平台")
    domain: DomainEnum = Field(..., description="领域")
    account_info: dict[str, Any] | None = Field(None, description="账号信息(JSON)")


class CreateSocialAccountParam(SchemaBase):
    """创建账号参数"""

    name: str = Field(..., description="账号名称")
    platform: PlatformEnum = Field(..., description="所属平台")
    domain: DomainEnum = Field(..., description="领域")
    homepage: str | None = Field(None, description="主页地址")
    phone: str | None = Field(None, description="电话号码")
    account_info: dict[str, Any] | None = Field(None, description="账号信息(JSON)")


class UpdateSocialAccountParam(SchemaBase):
    """更新账号参数"""

    name: str | None = Field(None, description="账号名称")
    platform: PlatformEnum | None = Field(None, description="所属平台")
    domain: DomainEnum | None = Field(None, description="领域")
    homepage: str | None = Field(None, description="主页地址")
    phone: str | None = Field(None, description="电话号码")
    account_info: dict[str, Any] | None = Field(None, description="账号信息(JSON)")


class GetSocialAccountDetail(SchemaBase):
    """账号详情"""

    id: int = Field(..., description="主键 ID")
    name: str = Field(..., description="账号名称")
    homepage: str | None = Field(None, description="主页地址")
    phone: str | None = Field(None, description="电话号码")
    platform: PlatformEnum = Field(..., description="所属平台")
    domain: DomainEnum = Field(..., description="领域")
    account_info: dict[str, Any] | None = Field(None, description="账号信息(JSON)")
    created_time: str | None = Field(None, description="创建时间")
    updated_time: str | None = Field(None, description="更新时间")


