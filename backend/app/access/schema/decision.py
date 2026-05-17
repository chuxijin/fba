#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime
from typing import Any

from pydantic import ConfigDict, Field

from backend.app.access.constants import DecisionKind
from backend.common.schema import SchemaBase


class DecisionLogQueryParam(SchemaBase):
    """决策日志查询"""

    user_id: int | None = Field(default=None, description='用户 ID')
    resource_type: str | None = Field(default=None, description='资源类型')
    resource_id: int | None = Field(default=None, description='资源 ID')
    decision: DecisionKind | None = Field(default=None, description='决策结果')
    reason_code: str | None = Field(default=None, description='原因码')
    occurred_from: datetime | None = Field(default=None, description='起始时间')
    occurred_to: datetime | None = Field(default=None, description='结束时间')


class GetDecisionLogDetail(SchemaBase):
    """决策日志详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='日志 ID')
    user_id: int = Field(description='用户 ID')
    resource_type: str = Field(description='资源类型')
    resource_id: int = Field(description='资源 ID')
    action: str = Field(description='动作')
    decision: DecisionKind = Field(description='决策结果')
    reason_code: str = Field(description='原因码')
    matched_grant: str | None = Field(description='匹配的权益编码')
    context: dict[str, Any] = Field(description='上下文')
    occurred_at: datetime = Field(description='决策时间')
