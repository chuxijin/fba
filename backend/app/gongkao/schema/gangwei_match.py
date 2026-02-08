#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from pydantic import Field

from backend.common.schema import SchemaBase


class ConditionCheckItem(SchemaBase):
    """条件检查项"""

    name: str = Field(description='条件名称')
    requirement: str | None = Field(None, description='岗位要求')
    user_value: str | None = Field(None, description='用户条件')
    passed: bool = Field(description='是否通过')
    reason: str | None = Field(None, description='说明')


class CanApplyResult(SchemaBase):
    """能否报考结果"""

    can_apply: bool = Field(description='是否可以报考')
    reasons: list[str] = Field(default_factory=list, description='不能报考的原因列表')
    checks: list[ConditionCheckItem] = Field(default_factory=list, description='各条件检查详情')
