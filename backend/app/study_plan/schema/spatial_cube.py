#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime
from typing import Literal

from pydantic import ConfigDict, Field

from backend.common.schema import SchemaBase

SpatialCubePatternRenderType = Literal['builtin', 'image']


class SpatialCubePatternSchemaBase(SchemaBase):
    """六面体面素材"""

    code: str = Field(min_length=1, max_length=64, description='素材编码')
    name: str = Field(min_length=1, max_length=64, description='素材名称')
    render_type: SpatialCubePatternRenderType = Field(default='builtin', description='渲染类型')
    asset_url: str | None = Field(default=None, max_length=1024, description='远程素材 URL')
    asset_version: str = Field(default='1', min_length=1, max_length=64, description='素材版本')
    rotation_period: Literal[90, 180, 360] = Field(default=360, description='旋转等价周期')
    sort: int = Field(default=0, description='排序')
    is_active: bool = Field(default=True, description='是否启用')


class CreateSpatialCubePatternParam(SpatialCubePatternSchemaBase):
    """创建六面体面素材"""


class UpdateSpatialCubePatternParam(SchemaBase):
    """更新六面体面素材"""

    code: str | None = Field(default=None, min_length=1, max_length=64, description='素材编码')
    name: str | None = Field(default=None, min_length=1, max_length=64, description='素材名称')
    render_type: SpatialCubePatternRenderType | None = Field(default=None, description='渲染类型')
    asset_url: str | None = Field(default=None, max_length=1024, description='远程素材 URL')
    asset_version: str | None = Field(default=None, min_length=1, max_length=64, description='素材版本')
    rotation_period: Literal[90, 180, 360] | None = Field(default=None, description='旋转等价周期')
    sort: int | None = Field(default=None, description='排序')
    is_active: bool | None = Field(default=None, description='是否启用')


class GetSpatialCubePatternDetail(SpatialCubePatternSchemaBase):
    """六面体面素材详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='素材 ID')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(default=None, description='更新时间')


class GetSpatialCubePatternCatalog(SchemaBase):
    """六面体面素材清单"""

    version: str = Field(description='清单版本')
    patterns: list[GetSpatialCubePatternDetail] = Field(default_factory=list, description='启用的面素材')
