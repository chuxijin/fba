#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.access.constants import GrantMode, ReasonCode
from backend.app.access.engine.evaluators.base import BaseEvaluator
from backend.app.access.engine.snapshot import UserGrantSnapshot
from backend.app.access.model.rule import ResourceRule
from backend.app.access.schema.engine import AccessContext, Decision, ExplanationNode


class SubscriptionAccessEvaluator(BaseEvaluator):
    """订阅准入评估器"""

    name = 'SubscriptionAccessEvaluator'

    async def evaluate(
        self,
        db: AsyncSession,
        ctx: AccessContext,
        rules: Sequence[ResourceRule],
        snapshot: UserGrantSnapshot,
        explanation: list[ExplanationNode],
    ) -> Decision | None:
        """
        若用户通过订阅持有任一 access 规则要求的权益, 即放行

        :param db: 数据库会话
        :param ctx: 决策上下文
        :param rules: 资源规则
        :param snapshot: 用户权益快照
        :param explanation: 决策路径累计
        :return:
        """
        for rule in rules:
            if rule.grant_mode != GrantMode.ACCESS:
                continue
            if snapshot.has_subscription_entitlement(rule.entitlement_code):
                self._log_allow(
                    explanation,
                    self.name,
                    '用户订阅命中准入权益',
                    matched={'entitlement_code': rule.entitlement_code, 'rule_id': rule.id},
                )
                return Decision.allow(
                    reason_code=ReasonCode.SUBSCRIPTION_ACCESS,
                    matched_grant=rule.entitlement_code,
                    explanation=explanation,
                )
        self._log_pass(explanation, self.name, '订阅未命中任何准入权益')
        return None
