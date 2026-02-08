#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

from pydantic import ConfigDict, Field

from backend.common.schema import SchemaBase


class DictRegionSchemaBase(SchemaBase):
    """地区字典基础"""

    code: str = Field(description='地区代码')
    name: str = Field(description='地区名称')
    short_name: str | None = Field(None, description='简称')
    level: int = Field(description='级别: 1省 2市 3县/区')
    parent_code: str | None = Field(None, description='父级代码')
    longitude: float | None = Field(None, description='经度')
    latitude: float | None = Field(None, description='纬度')
    is_remote_area: bool = Field(default=False, description='是否艰苦边远地区')
    sort_order: int = Field(default=0, description='排序')


class CreateDictRegionParam(DictRegionSchemaBase):
    """创建地区字典参数"""

    pass


class UpdateDictRegionParam(SchemaBase):
    """更新地区字典参数"""

    name: str | None = Field(None, description='地区名称')
    short_name: str | None = Field(None, description='简称')
    longitude: float | None = Field(None, description='经度')
    latitude: float | None = Field(None, description='纬度')
    is_remote_area: bool | None = Field(None, description='是否艰苦边远地区')
    sort_order: int | None = Field(None, description='排序')


class DictRegionParam(SchemaBase):
    """地区字典查询参数"""

    name: str | None = Field(None, description='地区名称')
    level: int | None = Field(None, description='级别')
    parent_code: str | None = Field(None, description='父级代码')


class GetDictRegionDetail(DictRegionSchemaBase):
    """地区字典详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='ID')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(None, description='更新时间')


class GetDictRegionTree(SchemaBase):
    """地区字典树形结构"""

    model_config = ConfigDict(from_attributes=True)

    code: str = Field(description='地区代码')
    name: str = Field(description='地区名称')
    level: int = Field(description='级别')
    is_remote_area: bool = Field(description='是否艰苦边远地区')
    children: list['GetDictRegionTree'] = Field(default_factory=list, description='子地区')
