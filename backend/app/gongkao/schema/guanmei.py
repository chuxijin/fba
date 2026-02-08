#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import date, datetime

from pydantic import ConfigDict, Field

from backend.common.schema import SchemaBase


class GuanmeiSchemaBase(SchemaBase):
    """官媒学言语基础"""

    daily_date: date | None = Field(None, description='日期')
    left_content: str | None = Field(None, description='左栏内容（文段）')
    right_content: str | None = Field(None, description='右栏内容（解析）')


class GuanmeiParam(SchemaBase):
    """官媒学言语查询参数"""

    daily_date: date | None = Field(None, description='日期')


class CreateGuanmeiParam(GuanmeiSchemaBase):
    """创建官媒学言语参数"""


class UpdateGuanmeiParam(SchemaBase):
    """更新官媒学言语参数"""

    daily_date: date | None = Field(None, description='日期')
    left_content: str | None = Field(None, description='左栏内容（文段）')
    right_content: str | None = Field(None, description='右栏内容（解析）')


class DeleteGuanmeiParam(SchemaBase):
    """删除官媒学言语参数"""

    ids: list[int] = Field(description='ID 列表')


class GetGuanmeiDetail(GuanmeiSchemaBase):
    """官媒学言语详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='ID')
    view_count: int = Field(description='阅读量')
    created_by: int = Field(description='创建者')
    updated_by: int | None = Field(None, description='修改者')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(None, description='更新时间')
