#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Any

from pydantic import Field

from backend.common.schema import SchemaBase


class AccessDebugParam(SchemaBase):
    """权益调试参数"""

    resource_type: str = Field(description='资源类型')
    resource_id: int = Field(description='资源 ID')
    user_id: int | None = Field(default=None, description='用户 ID')
    action: str = Field(default='access', description='动作')
    audience_attrs: dict[str, Any] = Field(default_factory=dict, description='用户画像快照')
