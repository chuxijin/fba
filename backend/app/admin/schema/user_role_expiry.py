#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

from pydantic import ConfigDict, Field

from backend.common.schema import SchemaBase


class CreateUserRoleExpiryParam(SchemaBase):
    """创建用户角色有效期"""

    user_id: int = Field(description='用户 ID')
    role_id: int = Field(description='角色 ID')
    valid_from: datetime | None = Field(default=None, description='有效期开始')
    valid_to: datetime | None = Field(default=None, description='有效期结束')


class UpdateUserRoleExpiryParam(SchemaBase):
    """更新用户角色有效期"""

    valid_from: datetime | None = Field(default=None, description='有效期开始')
    valid_to: datetime | None = Field(default=None, description='有效期结束')
    status: int | None = Field(default=None, ge=0, le=2, description='状态(0停用 1正常 2已过期)')


class GetUserRoleExpiryDetail(SchemaBase):
    """用户角色有效期详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='记录 ID')
    user_id: int = Field(description='用户 ID')
    role_id: int = Field(description='角色 ID')
    valid_from: datetime | None = Field(default=None, description='有效期开始')
    valid_to: datetime | None = Field(default=None, description='有效期结束')
    status: int = Field(description='状态')
    created_time: datetime = Field(description='创建时间')
