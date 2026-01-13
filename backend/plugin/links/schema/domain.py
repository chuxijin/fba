#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

from pydantic import ConfigDict, Field

from backend.common.schema import SchemaBase


class DomainSchemaBase(SchemaBase):
    """域名基础模型"""

    domain: str = Field(max_length=128, description='域名')
    domain_type: int = Field(ge=1, le=3, description='域名类型(1入口域名 2中转域名 3落地域名)')
    remark: str | None = Field(None, max_length=256, description='备注')


class CreateDomainParam(DomainSchemaBase):
    """创建域名参数"""

    pass


class UpdateDomainParam(SchemaBase):
    """更新域名参数"""

    domain: str | None = Field(None, max_length=128, description='域名')
    domain_type: int | None = Field(None, ge=1, le=3, description='域名类型')
    remark: str | None = Field(None, max_length=256, description='备注')


class GetDomainDetail(DomainSchemaBase):
    """域名详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='域名ID')
    created_by: int = Field(description='创建者ID')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(None, description='更新时间')
