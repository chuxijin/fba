#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

from pydantic import ConfigDict, Field

from backend.common.schema import SchemaBase


class BiliTemplateSchemaBase(SchemaBase):
    """B 站模板话术基础模型"""

    name: str = Field(description='模板名称')
    template_type: str = Field(description='模板类型(comment/message)')
    content: str = Field(description='模板内容')
    keywords: str | None = Field(None, description='关键词触发条件(JSON 格式)')
    status: int = Field(1, description='状态(0 停用 1 正常)')
    category_id: int | None = Field(None, description='分类关联 ID')


class CreateBiliTemplateParam(BiliTemplateSchemaBase):
    """创建 B 站模板话术参数"""


class UpdateBiliTemplateParam(SchemaBase):
    """更新 B 站模板话术参数"""

    name: str | None = Field(None, description='模板名称')
    template_type: str | None = Field(None, description='模板类型')
    content: str | None = Field(None, description='模板内容')
    keywords: str | None = Field(None, description='关键词触发条件')
    status: int | None = Field(None, description='状态')
    category_id: int | None = Field(None, description='分类关联 ID')


class GetBiliTemplateDetail(BiliTemplateSchemaBase):
    """B 站模板话术详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='ID')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(None, description='更新时间')
