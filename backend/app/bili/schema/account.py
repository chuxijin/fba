#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

from pydantic import ConfigDict, Field

from backend.common.schema import SchemaBase


class BiliAccountSchemaBase(SchemaBase):
    """B 站账号基础模型"""

    account_name: str = Field(description='账号名称')
    mid: str | None = Field(None, description='B 站用户 MID')
    cookie: str | None = Field(None, description='登录凭证')
    ip: str | None = Field(None, description='使用 IP')
    status: int = Field(1, description='状态(0 停用 1 正常)')
    remark: str | None = Field(None, description='备注')
    category_id: int | None = Field(None, description='分类关联 ID')


class CreateBiliAccountParam(BiliAccountSchemaBase):
    """创建 B 站账号参数"""


class UpdateBiliAccountParam(SchemaBase):
    """更新 B 站账号参数"""

    account_name: str | None = Field(None, description='账号名称')
    mid: str | None = Field(None, description='B 站用户 MID')
    cookie: str | None = Field(None, description='登录凭证')
    ip: str | None = Field(None, description='使用 IP')
    status: int | None = Field(None, description='状态(0 停用 1 正常)')
    remark: str | None = Field(None, description='备注')
    category_id: int | None = Field(None, description='分类关��� ID')


class GetBiliAccountDetail(BiliAccountSchemaBase):
    """B 站账号详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='ID')
    last_active_time: datetime | None = Field(None, description='最后活跃时间')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(None, description='更新时间')
