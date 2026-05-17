#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime
from typing import Any

from pydantic import Field, model_validator
from sqlalchemy.dialects.postgresql.ranges import Range

from backend.common.schema import SchemaBase


class TimePeriodInput(SchemaBase):
    """时间段入参"""

    valid_from: datetime = Field(description='开始时间')
    valid_to: datetime | None = Field(default=None, description='结束时间, 空表示永久')

    @model_validator(mode='after')
    def _check_order(self) -> 'TimePeriodInput':
        """校验时间顺序"""
        if self.valid_to is not None and self.valid_to <= self.valid_from:
            raise ValueError('结束时间必须大于开始时间')
        return self

    def to_range(self) -> Range[datetime]:
        """转为 PG TSTZRANGE"""
        return Range(self.valid_from, self.valid_to, bounds='[)')


class TimePeriodOutput(SchemaBase):
    """时间段出参"""

    valid_from: datetime = Field(description='开始时间')
    valid_to: datetime | None = Field(default=None, description='结束时间')

    @model_validator(mode='before')
    @classmethod
    def _parse_range(cls, data: Any) -> Any:
        """自动处理 PG Range 对象"""
        if isinstance(data, Range):
            return {'valid_from': data.lower, 'valid_to': data.upper}
        if hasattr(data, 'lower') and hasattr(data, 'upper'):
            return {'valid_from': data.lower, 'valid_to': data.upper}
        return data

    @classmethod
    def from_range(cls, period: Range[datetime] | None) -> 'TimePeriodOutput | None':
        """
        从 PG Range 转换

        :param period: PG TSTZRANGE 范围
        :return:
        """
        if period is None:
            return None
        return cls(valid_from=period.lower, valid_to=period.upper)
