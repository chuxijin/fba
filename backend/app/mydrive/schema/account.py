#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime
from typing import Any

from pydantic import ConfigDict, Field

from backend.common.schema import SchemaBase


class CreateMyDriveAccountParam(SchemaBase):
    """创建网盘账户"""

    provider: str = Field(max_length=64, description='网盘驱动标识')
    external_account_id: str = Field(default='', max_length=256, description='网盘侧账户标识')
    display_name: str = Field(max_length=128, description='账户显示名称')
    credential: dict[str, Any] = Field(default_factory=dict, description='授权凭证')
    credential_expires_at: datetime | None = Field(default=None, description='凭证过期时间')


class UpdateMyDriveAccountParam(SchemaBase):
    """更新网盘账户"""

    display_name: str | None = Field(default=None, max_length=128, description='账户显示名称')
    credential: dict[str, Any] | None = Field(default=None, description='授权凭证')
    credential_expires_at: datetime | None = Field(default=None, description='凭证过期时间')
    status: str | None = Field(default=None, max_length=32, description='状态')


class GetMyDriveAccountDetail(SchemaBase):
    """网盘账户详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='账户 ID')
    owner_id: int = Field(description='所属用户 ID')
    provider: str = Field(description='网盘驱动标识')
    external_account_id: str = Field(description='网盘侧账户标识')
    display_name: str = Field(description='账户显示名称')
    username: str | None = Field(description='网盘用户名')
    avatar_url: str | None = Field(description='头像地址')
    quota: int | None = Field(description='总容量（字节）')
    used: int | None = Field(description='已用容量（字节）')
    vip_level: str | None = Field(description='会员等级')
    credential_expires_at: datetime | None = Field(description='凭证过期时间')
    status: str = Field(description='状态')
    last_verified_at: datetime | None = Field(description='最近验证时间')
    last_profile_synced_at: datetime | None = Field(description='最近账户资料同步时间')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(description='更新时间')
