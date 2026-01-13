#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

from pydantic import ConfigDict, Field

from backend.common.schema import SchemaBase


class DwzSchemaBase(SchemaBase):
    """短网址基础模型"""

    original_url: str = Field(max_length=2048, description='原网址')
    title: str | None = Field(None, max_length=128, description='标题')
    remark: str | None = Field(None, max_length=256, description='备注')
    entry_domain: str | None = Field(None, max_length=128, description='入口域名')
    redirect_domain: str | None = Field(None, max_length=128, description='中转域名')
    landing_domain: str | None = Field(None, max_length=128, description='落地域名')


class CreateDwzParam(DwzSchemaBase):
    """创建短网址参数"""

    code: str | None = Field(None, max_length=16, description='自定义短码(可选)')


class UpdateDwzParam(SchemaBase):
    """更新短网址参数"""

    original_url: str | None = Field(None, max_length=2048, description='原网址')
    title: str | None = Field(None, max_length=128, description='标题')
    remark: str | None = Field(None, max_length=256, description='备注')
    status: int | None = Field(None, ge=0, le=1, description='状态(0停用 1启用)')
    entry_domain: str | None = Field(None, max_length=128, description='入口域名')
    redirect_domain: str | None = Field(None, max_length=128, description='中转域名')
    landing_domain: str | None = Field(None, max_length=128, description='落地域名')
    domain_status: int | None = Field(None, ge=0, le=1, description='域名状态(0异常 1正常)')


class GetDwzDetail(DwzSchemaBase):
    """短网址详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='短网址ID')
    code: str = Field(description='短网址Key')
    clicks: int = Field(description='访问量')
    status: int = Field(description='状态')
    domain_status: int = Field(description='域名状态')
    created_by: int = Field(description='创建者ID')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(None, description='更新时间')


class GetDwzList(SchemaBase):
    """短网址列表项"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='短网址ID')
    code: str = Field(description='短网址Key')
    original_url: str = Field(description='原网址')
    title: str | None = Field(None, description='标题')
    clicks: int = Field(description='访问量')
    status: int = Field(description='状态')
    domain_status: int = Field(description='域名状态')
    created_time: datetime = Field(description='创建时间')
