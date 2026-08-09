#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime
from typing import Any

from pydantic import ConfigDict, Field, model_validator

from backend.app.access.constants import CommonStatus, GrantMode, TrialMode
from backend.app.access.schema.base import TimePeriodInput, TimePeriodOutput
from backend.common.schema import SchemaBase


class TrialPolicyParam(SchemaBase):
    """试看策略

    试看是资源规则上的降级放行策略, 不是权益凭证, 因此不需要为用户发放任何 entitlement。
    """

    mode: TrialMode = Field(description='试看模式')
    limit: int | None = Field(default=None, ge=1, description='ordinal / daily_count 的次数上限')
    ratio: float | None = Field(default=None, gt=0, le=1, description='fraction 的放行比例')
    chars: int | None = Field(default=None, ge=1, description='excerpt 的可见字数')

    @model_validator(mode='after')
    def _validate_mode_fields(self) -> 'TrialPolicyParam':
        """校验各模式必填字段"""
        if self.mode in (TrialMode.ORDINAL, TrialMode.DAILY_COUNT) and self.limit is None:
            raise ValueError(f'试看模式 {self.mode.value} 必须填写 limit')
        if self.mode == TrialMode.FRACTION and self.ratio is None:
            raise ValueError('试看模式 fraction 必须填写 ratio')
        if self.mode == TrialMode.EXCERPT and self.chars is None:
            raise ValueError('试看模式 excerpt 必须填写 chars')
        return self


class CreateRuleParam(SchemaBase):
    """创建资源规则"""

    resource_type: str = Field(max_length=32, description='资源类型')
    resource_id: int = Field(description='资源 ID')
    entitlement_code: str = Field(max_length=64, description='权益编码')
    grant_mode: GrantMode = Field(description='授权模式')
    priority: int = Field(default=0, description='优先级')
    trial_policy: TrialPolicyParam | None = Field(default=None, description='试看策略, 空表示不允许试看')
    valid_period: TimePeriodInput | None = Field(default=None, description='生效时间段, 空表示永久')
    audience_filter: dict[str, Any] = Field(default_factory=dict, description='受众过滤')
    inherit_to_children: bool = Field(default=True, description='是否级联子资源')
    metadata: dict[str, Any] = Field(default_factory=dict, description='扩展元数据')


class UpdateRuleParam(SchemaBase):
    """更新资源规则"""

    grant_mode: GrantMode | None = Field(default=None, description='授权模式')
    priority: int | None = Field(default=None, description='优先级')
    trial_policy: TrialPolicyParam | None = Field(default=None, description='试看策略')
    valid_period: TimePeriodInput | None = Field(default=None, description='生效时间段')
    audience_filter: dict[str, Any] | None = Field(default=None, description='受众过滤')
    inherit_to_children: bool | None = Field(default=None, description='是否级联子资源')
    metadata: dict[str, Any] | None = Field(default=None, description='扩展元数据')
    status: CommonStatus | None = Field(default=None, description='状态')


class BulkUpsertRulesParam(SchemaBase):
    """按资源类型批量回填规则"""

    resource_type: str = Field(max_length=32, description='资源类型')
    resource_ids: list[int] = Field(description='资源 ID 列表')
    entitlement_code: str = Field(max_length=64, description='权益编码')
    grant_mode: GrantMode = Field(description='授权模式')
    priority: int = Field(default=0, description='优先级')
    trial_policy: TrialPolicyParam | None = Field(default=None, description='试看策略, 空表示不允许试看')
    valid_period: TimePeriodInput | None = Field(default=None, description='生效时间段')


class RuleQueryParam(SchemaBase):
    """规则查询"""

    resource_type: str | None = Field(default=None, description='资源类型')
    resource_id: int | None = Field(default=None, description='资源 ID')
    entitlement_code: str | None = Field(default=None, description='权益编码')
    grant_mode: GrantMode | None = Field(default=None, description='授权模式')
    status: CommonStatus | None = Field(default=None, description='状态')


class GetRuleDetail(SchemaBase):
    """资源规则详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='规则 ID')
    resource_type: str = Field(description='资源类型')
    resource_id: int = Field(description='资源 ID')
    entitlement_code: str = Field(description='权益编码')
    grant_mode: GrantMode = Field(description='授权模式')
    priority: int = Field(description='优先级')
    trial_policy: dict[str, Any] | None = Field(default=None, description='试看策略')
    valid_period: TimePeriodOutput | None = Field(default=None, description='生效时间段')
    audience_filter: dict[str, Any] = Field(description='受众过滤')
    inherit_to_children: bool = Field(description='是否级联子资源')
    status: CommonStatus = Field(description='状态')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(default=None, description='更新时间')
