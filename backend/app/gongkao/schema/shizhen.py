#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import date, datetime

from pydantic import ConfigDict, Field

from backend.common.schema import SchemaBase


class ShizhenSchemaBase(SchemaBase):
    """时政基础"""

    daily_date: date | None = Field(None, description='日期')
    original: str | None = Field(None, description='原文')
    summary: str | None = Field(None, description='主要内容')


class ShizhenParam(SchemaBase):
    """时政查询参数"""

    daily_date: date | None = Field(None, description='日期')


class CreateShizhenParam(ShizhenSchemaBase):
    """创建时政参数"""


class UpdateShizhenParam(ShizhenSchemaBase):
    """更新时政参数"""


class DeleteShizhenParam(SchemaBase):
    """删除时政参数"""

    ids: list[int] = Field(description='时政 ID 列表')


class GetShizhenDetail(ShizhenSchemaBase):
    """时政详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='时政 ID')
    created_by: int = Field(description='创建者')
    updated_by: int | None = Field(None, description='修改者')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(None, description='更新时间')
