#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from pydantic import Field, model_validator

from backend.common.schema import SchemaBase


class GrayscaleConfigSchema(SchemaBase):
    """灰度配置 Schema"""

    enabled: bool = Field(default=True, description='总开关')
    whitelist: list[int] = Field(default_factory=list, description='白名单用户 ID 列表')
    ratio: float = Field(default=0.0, ge=0.0, le=1.0, description='灰度比例 0.0~1.0')

    @model_validator(mode='after')
    def check_ratio_precision(self) -> 'GrayscaleConfigSchema':
        """确保 ratio 精度不超过 4 位小数"""
        self.ratio = round(self.ratio, 4)
        return self


class GrayscaleFeatureItem(SchemaBase):
    """灰度功能项"""

    feature: str = Field(description='功能名称')
    enabled: bool = Field(description='总开关')
    whitelist: list[int] = Field(description='白名单用户 ID 列表')
    ratio: float = Field(description='灰度比例')


class GrayscaleListResponse(SchemaBase):
    """灰度配置列表响应"""

    features: list[GrayscaleFeatureItem] = Field(default_factory=list, description='灰度功能列表')