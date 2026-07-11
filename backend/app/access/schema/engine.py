#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime
from typing import Any

from pydantic import Field

from backend.app.access.constants import DecisionKind, ReasonCode
from backend.common.schema import SchemaBase


class AccessContext(SchemaBase):
    """决策上下文(不可变)"""

    user_id: int = Field(description='用户 ID')
    resource_type: str = Field(description='资源类型')
    resource_id: int = Field(description='资源 ID')
    action: str = Field(default='access', description='动作')
    consume_trial: bool = Field(default=True, description='是否允许扣减试看额度')
    scope_key: str = Field(default='global', description='配额范围键')
    source_ref: str | None = Field(default=None, description='来源引用，用于扣减幂等')
    request_ts: datetime | None = Field(default=None, description='请求时间, 空则按服务器当前')
    audience_attrs: dict[str, Any] = Field(default_factory=dict, description='用户画像快照')


class ExplanationNode(SchemaBase):
    """决策路径节点"""

    evaluator: str = Field(description='评估器名')
    outcome: str = Field(description='结果(pass/allow/deny)')
    reason: str = Field(description='原因描述')
    matched: dict[str, Any] | None = Field(default=None, description='匹配明细')


class Decision(SchemaBase):
    """决策结果"""

    allowed: bool = Field(description='是否放行')
    decision: DecisionKind = Field(description='决策枚举')
    reason_code: ReasonCode = Field(description='原因码')
    matched_grant: str | None = Field(default=None, description='匹配的权益编码')
    consumed_ledger_id: int | None = Field(default=None, description='消耗的账本流水 ID')
    explanation: list[ExplanationNode] = Field(default_factory=list, description='决策路径')

    @classmethod
    def allow(
        cls,
        reason_code: ReasonCode,
        *,
        matched_grant: str | None = None,
        consumed_ledger_id: int | None = None,
        explanation: list[ExplanationNode] | None = None,
    ) -> 'Decision':
        """
        构造允许决策

        :param reason_code: 原因码
        :param matched_grant: 匹配的权益编码
        :param consumed_ledger_id: 消耗的账本流水 ID
        :param explanation: 决策路径
        :return:
        """
        return cls(
            allowed=True,
            decision=DecisionKind.ALLOW,
            reason_code=reason_code,
            matched_grant=matched_grant,
            consumed_ledger_id=consumed_ledger_id,
            explanation=explanation or [],
        )

    @classmethod
    def deny(
        cls,
        reason_code: ReasonCode,
        *,
        explanation: list[ExplanationNode] | None = None,
    ) -> 'Decision':
        """
        构造拒绝决策

        :param reason_code: 原因码
        :param explanation: 决策路径
        :return:
        """
        return cls(
            allowed=False,
            decision=DecisionKind.DENY,
            reason_code=reason_code,
            explanation=explanation or [],
        )
